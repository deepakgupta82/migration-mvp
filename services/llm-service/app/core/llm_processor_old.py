#!/usr/bin/env python3
"""
LLM Orchestration Service - Core Processing Logic
Extracted from backend LLM management components

Handles:
- LLM provider management (OpenAI, Anthropic, Gemini, Ollama)
- Configuration storage and retrieval
- LLM testing and validation
- Rate limiting and caching
- Process-specific LLM assignment
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib
import os

import redis
import psycopg2
from psycopg2.extras import RealDictCursor
import openai
from anthropic import Anthropic
import google.generativeai as genai
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm-service")

class LLMProcessor:
    """Core LLM orchestration logic extracted from backend"""
    
    def __init__(self):
        self.redis_client = None
        self.db_connection = None
        self._initialize_connections()
        
    def _initialize_connections(self):
        """Initialize Redis and PostgreSQL connections"""
        try:
            # Redis for caching and rate limiting (DB 3 for LLM service)
            self.redis_client = redis.Redis(
                host='localhost', 
                port=6379, 
                db=3,
                decode_responses=True
            )
            
            # PostgreSQL for LLM configurations
            self.db_connection = psycopg2.connect(
                host="localhost",
                database="projectdb",
                user="projectuser", 
                password="projectpass",
                cursor_factory=RealDictCursor
            )
            
            logger.info("LLM service connections initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize connections: {e}")
            
    async def verify_dependencies(self) -> Dict[str, bool]:
        """Verify all LLM service dependencies"""
        dependencies = {}
        
        # Redis connection
        try:
            self.redis_client.ping()
            dependencies['redis'] = True
            logger.info("✓ Redis connection verified")
        except Exception as e:
            dependencies['redis'] = False
            logger.error(f"✗ Redis connection failed: {e}")
            
        # PostgreSQL connection  
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            dependencies['postgresql'] = True
            logger.info("✓ PostgreSQL connection verified")
        except Exception as e:
            dependencies['postgresql'] = False
            logger.error(f"✗ PostgreSQL connection failed: {e}")
            
        return dependencies
        
    async def get_llm_providers(self) -> List[Dict[str, Any]]:
        """Get available LLM providers with status"""
        providers = [
            {
                "provider": "openai",
                "name": "OpenAI",
                "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
                "supports_streaming": True,
                "rate_limit": "10000/min"
            },
            {
                "provider": "anthropic", 
                "name": "Anthropic Claude",
                "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
                "supports_streaming": True,
                "rate_limit": "5000/min"
            },
            {
                "provider": "gemini",
                "name": "Google Gemini", 
                "models": ["gemini-pro", "gemini-1.5-flash"],
                "supports_streaming": True,
                "rate_limit": "60/min"
            },
            {
                "provider": "azure",
                "name": "Azure OpenAI",
                "models": ["gpt-4", "gpt-35-turbo"],
                "supports_streaming": True, 
                "rate_limit": "custom"
            },
            {
                "provider": "ollama",
                "name": "Ollama Local",
                "models": ["llama2", "mistral", "codellama"],
                "supports_streaming": True,
                "rate_limit": "unlimited"
            }
        ]
        
        # Check which providers have valid configurations
        for provider in providers:
            provider['configured'] = await self._check_provider_config(provider['provider'])
            
        return providers
        
    async def _check_provider_config(self, provider: str) -> bool:
        """Check if provider has valid configuration in database"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM llm_configurations WHERE provider = %s AND is_active = true",
                (provider,)
            )
            count = cursor.fetchone()['count']
            return count > 0
        except Exception as e:
            logger.error(f"Error checking provider config for {provider}: {e}")
            return False
            
    async def get_provider_models(self, provider: str) -> List[Dict[str, Any]]:
        """Get available models for specific provider"""
        try:
            if provider == "openai":
                return await self._get_openai_models()
            elif provider == "anthropic":
                return await self._get_anthropic_models()
            elif provider == "gemini":
                return await self._get_gemini_models()
            elif provider == "ollama":
                return await self._get_ollama_models()
            else:
                return []
        except Exception as e:
            logger.error(f"Error getting models for {provider}: {e}")
            return []
            
    async def _get_openai_models(self) -> List[Dict[str, Any]]:
        """Get OpenAI models with metadata"""
        models = [
            {"id": "gpt-4", "max_tokens": 8192, "context_length": 128000, "cost_per_1k_tokens": 0.03},
            {"id": "gpt-4-turbo", "max_tokens": 4096, "context_length": 128000, "cost_per_1k_tokens": 0.01},
            {"id": "gpt-3.5-turbo", "max_tokens": 4096, "context_length": 16385, "cost_per_1k_tokens": 0.002}
        ]
        return models
        
    async def _get_anthropic_models(self) -> List[Dict[str, Any]]:
        """Get Anthropic models with metadata"""
        models = [
            {"id": "claude-3-opus-20240229", "max_tokens": 4096, "context_length": 200000, "cost_per_1k_tokens": 0.015},
            {"id": "claude-3-sonnet-20240229", "max_tokens": 4096, "context_length": 200000, "cost_per_1k_tokens": 0.003},
            {"id": "claude-3-haiku-20240307", "max_tokens": 4096, "context_length": 200000, "cost_per_1k_tokens": 0.00025}
        ]
        return models
        
    async def _get_gemini_models(self) -> List[Dict[str, Any]]:
        """Get Gemini models with metadata"""
        models = [
            {"id": "gemini-pro", "max_tokens": 2048, "context_length": 32000, "cost_per_1k_tokens": 0.0005},
            {"id": "gemini-1.5-flash", "max_tokens": 8192, "context_length": 32000, "cost_per_1k_tokens": 0.0002}
        ]
        return models
        
    async def _get_ollama_models(self) -> List[Dict[str, Any]]:
        """Get locally available Ollama models"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:11434/api/tags", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    return [
                        {
                            "id": model["name"], 
                            "size": model.get("size", 0),
                            "modified_at": model.get("modified_at", ""),
                            "cost_per_1k_tokens": 0.0  # Local models are free
                        } 
                        for model in data.get("models", [])
                    ]
        except Exception as e:
            logger.warning(f"Could not connect to Ollama: {e}")
        return []
        
    async def test_llm_configuration(self, provider: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test LLM configuration with actual API call"""
        test_result = {
            "provider": provider,
            "status": "unknown",
            "response_time_ms": 0,
            "error": None,
            "test_response": None
        }
        
        start_time = datetime.now()
        
        try:
            # Simple test prompt
            test_prompt = "Hello! Please respond with 'Test successful' to confirm the connection."
            
            if provider == "openai":
                result = await self._test_openai(config, test_prompt)
            elif provider == "anthropic":
                result = await self._test_anthropic(config, test_prompt) 
            elif provider == "gemini":
                result = await self._test_gemini(config, test_prompt)
            elif provider == "ollama":
                result = await self._test_ollama(config, test_prompt)
            else:
                result = {"status": "unsupported", "error": f"Provider {provider} not supported"}
                
            test_result.update(result)
            
        except Exception as e:
            test_result.update({
                "status": "error",
                "error": str(e)
            })
            
        end_time = datetime.now()
        test_result["response_time_ms"] = int((end_time - start_time).total_seconds() * 1000)
        
        return test_result
        
    async def _test_openai(self, config: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Test OpenAI configuration"""
        client = openai.AsyncOpenAI(api_key=config.get("api_key"))
        
        response = await client.chat.completions.create(
            model=config.get("model", "gpt-3.5-turbo"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.1
        )
        
        return {
            "status": "success",
            "test_response": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens
        }
        
    async def _test_anthropic(self, config: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Test Anthropic configuration"""
        client = Anthropic(api_key=config.get("api_key"))
        
        response = await client.messages.create(
            model=config.get("model", "claude-3-haiku-20240307"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50
        )
        
        return {
            "status": "success",
            "test_response": response.content[0].text,
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens
        }
        
    async def _test_gemini(self, config: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Test Gemini configuration"""
        genai.configure(api_key=config.get("api_key"))
        model = genai.GenerativeModel(config.get("model", "gemini-pro"))
        
        response = await model.generate_content_async(prompt)
        
        return {
            "status": "success", 
            "test_response": response.text,
            "tokens_used": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
        }
        
    async def _test_ollama(self, config: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """Test Ollama local configuration"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": config.get("model", "llama2"),
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "success",
                    "test_response": data.get("response", ""),
                    "tokens_used": 0  # Ollama doesn't provide token counts
                }
            else:
                return {
                    "status": "error",
                    "error": f"Ollama API returned {response.status_code}"
                }
                
    async def save_llm_configuration(self, project_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Save LLM configuration to database"""
        try:
            cursor = self.db_connection.cursor()
            
            # Check if configuration exists
            cursor.execute("""
                SELECT id FROM llm_configurations 
                WHERE project_id = %s AND provider = %s
            """, (project_id, config.get("provider")))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing configuration
                cursor.execute("""
                    UPDATE llm_configurations SET 
                        model = %s, api_key = %s, temperature = %s, max_tokens = %s, 
                        is_active = %s, updated_at = NOW()
                    WHERE project_id = %s AND provider = %s
                    RETURNING id
                """, (
                    config.get("model"), 
                    config.get("api_key"),
                    config.get("temperature", 0.7),
                    config.get("max_tokens", 1000),
                    config.get("is_active", True),
                    project_id,
                    config.get("provider")
                ))
            else:
                # Insert new configuration
                cursor.execute("""
                    INSERT INTO llm_configurations 
                    (project_id, provider, model, api_key, temperature, max_tokens, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING id
                """, (
                    project_id,
                    config.get("provider"),
                    config.get("model"), 
                    config.get("api_key"),
                    config.get("temperature", 0.7),
                    config.get("max_tokens", 1000),
                    config.get("is_active", True)
                ))
            
            config_id = cursor.fetchone()['id']
            self.db_connection.commit()
            
            # Clear cache for this project
            cache_key = f"llm_config:{project_id}"
            self.redis_client.delete(cache_key)
            
            logger.info(f"LLM configuration saved for project {project_id}, provider {config.get('provider')}")
            
            return {
                "success": True,
                "config_id": config_id,
                "message": "Configuration saved successfully"
            }
            
        except Exception as e:
            self.db_connection.rollback()
            logger.error(f"Error saving LLM configuration: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def get_llm_configurations(self, project_id: str) -> List[Dict[str, Any]]:
        """Get LLM configurations for project"""
        try:
            # Check cache first
            cache_key = f"llm_config:{project_id}"
            cached = self.redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
                
            # Query database
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT id, provider, model, temperature, max_tokens, is_active, 
                       created_at, updated_at
                FROM llm_configurations 
                WHERE project_id = %s
                ORDER BY created_at DESC
            """, (project_id,))
            
            configs = []
            for row in cursor.fetchall():
                configs.append({
                    "id": row["id"],
                    "provider": row["provider"],
                    "model": row["model"],
                    "temperature": float(row["temperature"]) if row["temperature"] else 0.7,
                    "max_tokens": row["max_tokens"],
                    "is_active": row["is_active"],
                    "created_at": row["created_at"].isoformat(),
                    "updated_at": row["updated_at"].isoformat()
                })
                
            # Cache results for 5 minutes
            self.redis_client.setex(cache_key, 300, json.dumps(configs))
            
            return configs
            
        except Exception as e:
            logger.error(f"Error getting LLM configurations: {e}")
            return []
            
    async def get_rate_limit_status(self, provider: str, project_id: str) -> Dict[str, Any]:
        """Get current rate limit status"""
        rate_limit_key = f"rate_limit:{provider}:{project_id}"
        
        try:
            current_count = self.redis_client.get(rate_limit_key)
            ttl = self.redis_client.ttl(rate_limit_key)
            
            return {
                "provider": provider,
                "project_id": project_id,
                "current_usage": int(current_count) if current_count else 0,
                "reset_in_seconds": ttl if ttl > 0 else 0,
                "limit_reached": False  # Would implement actual limits based on provider
            }
            
        except Exception as e:
            logger.error(f"Error getting rate limit status: {e}")
            return {"error": str(e)}
            
    async def get_llm_statistics(self) -> Dict[str, Any]:
        """Get LLM usage statistics"""
        try:
            cursor = self.db_connection.cursor()
            
            # Get configuration counts by provider
            cursor.execute("""
                SELECT provider, COUNT(*) as count, 
                       SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active_count
                FROM llm_configurations 
                GROUP BY provider
            """)
            
            provider_stats = {}
            for row in cursor.fetchall():
                provider_stats[row["provider"]] = {
                    "total_configs": row["count"],
                    "active_configs": row["active_count"]
                }
            
            # Get total project count
            cursor.execute("SELECT COUNT(DISTINCT project_id) as project_count FROM llm_configurations")
            project_count = cursor.fetchone()["project_count"]
            
            return {
                "total_projects": project_count,
                "provider_stats": provider_stats,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting LLM statistics: {e}")
            return {"error": str(e)}
