"""
LLM Configuration Management Router
Provides APIs for managing process-specific LLM configurations
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import json

from app.core.project_service import get_project_service
from app.core.llm_factory import llm_factory, LLMProcessType

logger = logging.getLogger("platform.llm_config_router")
router = APIRouter()

# Pydantic models for API
class LLMConfigRequest(BaseModel):
    provider: str
    model: str
    api_key_id: Optional[str] = None
    temperature: Optional[float] = 0.1
    max_tokens: Optional[int] = 4000

class ProcessLLMConfigRequest(BaseModel):
    entity_extraction: Optional[LLMConfigRequest] = None
    crew_assessment: Optional[LLMConfigRequest] = None
    crew_documentation: Optional[LLMConfigRequest] = None
    rag_synthesis: Optional[LLMConfigRequest] = None
    hybrid_search: Optional[LLMConfigRequest] = None
    conversation: Optional[LLMConfigRequest] = None

class ProcessLLMConfigResponse(BaseModel):
    project_id: str
    entity_extraction: Optional[Dict[str, Any]] = None
    crew_assessment: Optional[Dict[str, Any]] = None
    crew_documentation: Optional[Dict[str, Any]] = None
    rag_synthesis: Optional[Dict[str, Any]] = None
    hybrid_search: Optional[Dict[str, Any]] = None
    conversation: Optional[Dict[str, Any]] = None

class LLMRecommendationsResponse(BaseModel):
    process_type: str
    recommendations: Dict[str, List[str]]
    description: str

@router.get("/{project_id}/llm-process-configs", response_model=ProcessLLMConfigResponse)
async def get_project_process_llm_configs(project_id: str):
    """Get all process-specific LLM configurations for a project"""
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Extract process-specific configurations
        configs = {}
        for process_type in LLMProcessType:
            config_field = f"{process_type.value}_llm_config"
            if hasattr(project, config_field):
                config_json = getattr(project, config_field)
                if config_json:
                    try:
                        configs[process_type.value] = json.loads(config_json) if isinstance(config_json, str) else config_json
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in {config_field} for project {project_id}")
        
        # Also check nested configuration
        if hasattr(project, 'llm_process_configs') and project.llm_process_configs:
            try:
                nested_configs = json.loads(project.llm_process_configs) if isinstance(project.llm_process_configs, str) else project.llm_process_configs
                configs.update(nested_configs)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in llm_process_configs for project {project_id}")
        
        return ProcessLLMConfigResponse(
            project_id=project_id,
            entity_extraction=configs.get('entity_extraction'),
            crew_assessment=configs.get('crew_assessment'),
            crew_documentation=configs.get('crew_documentation'),
            rag_synthesis=configs.get('rag_synthesis'),
            hybrid_search=configs.get('hybrid_search'),
            conversation=configs.get('conversation')
        )
        
    except Exception as e:
        logger.error(f"Error getting process LLM configs for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{project_id}/llm-process-configs")
async def update_project_process_llm_configs(project_id: str, config_request: ProcessLLMConfigRequest):
    """Update process-specific LLM configurations for a project"""
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Prepare update data
        update_data = {}
        
        # Convert request to individual config fields
        if config_request.entity_extraction:
            update_data['entity_extraction_llm_config'] = json.dumps(config_request.entity_extraction.dict())
        
        if config_request.crew_assessment:
            update_data['crew_assessment_llm_config'] = json.dumps(config_request.crew_assessment.dict())
        
        if config_request.crew_documentation:
            update_data['crew_documentation_llm_config'] = json.dumps(config_request.crew_documentation.dict())
        
        if config_request.rag_synthesis:
            update_data['rag_synthesis_llm_config'] = json.dumps(config_request.rag_synthesis.dict())
        
        if config_request.hybrid_search:
            update_data['hybrid_search_llm_config'] = json.dumps(config_request.hybrid_search.dict())
        
        if config_request.conversation:
            update_data['conversation_llm_config'] = json.dumps(config_request.conversation.dict())
        
        # Also update nested configuration for compatibility
        nested_config = {}
        for process_name, config in [
            ('entity_extraction', config_request.entity_extraction),
            ('crew_assessment', config_request.crew_assessment),
            ('crew_documentation', config_request.crew_documentation),
            ('rag_synthesis', config_request.rag_synthesis),
            ('hybrid_search', config_request.hybrid_search),
            ('conversation', config_request.conversation)
        ]:
            if config:
                nested_config[process_name] = config.dict()
        
        if nested_config:
            update_data['llm_process_configs'] = json.dumps(nested_config)
        
        # Update project
        project_service.update_project(project_id, update_data)
        
        logger.info(f"Updated process LLM configs for project {project_id}")
        return {"status": "success", "message": "Process LLM configurations updated"}
        
    except Exception as e:
        logger.error(f"Error updating process LLM configs for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{project_id}/llm-process-configs/{process_type}")
async def delete_process_llm_config(project_id: str, process_type: str):
    """Delete a specific process LLM configuration"""
    try:
        # Validate process type
        try:
            process_enum = LLMProcessType(process_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid process type: {process_type}")
        
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Clear the specific configuration
        config_field = f"{process_type}_llm_config"
        update_data = {config_field: None}
        
        # Also update nested configuration
        if hasattr(project, 'llm_process_configs') and project.llm_process_configs:
            try:
                nested_configs = json.loads(project.llm_process_configs) if isinstance(project.llm_process_configs, str) else project.llm_process_configs
                if process_type in nested_configs:
                    del nested_configs[process_type]
                    update_data['llm_process_configs'] = json.dumps(nested_configs) if nested_configs else None
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in llm_process_configs for project {project_id}")
        
        project_service.update_project(project_id, update_data)
        
        logger.info(f"Deleted {process_type} LLM config for project {project_id}")
        return {"status": "success", "message": f"Deleted {process_type} LLM configuration"}
        
    except Exception as e:
        logger.error(f"Error deleting {process_type} LLM config for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel
from typing import Optional

class ProcessLLMTestRequest(BaseModel):
    use_project_default: Optional[bool] = False
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = 0.1
    api_key: Optional[str] = None
    query: Optional[str] = "Hello, please respond with 'OK' to confirm you're working."

@router.post("/{project_id}/process-llm-config/{process_key}/test")
async def test_process_llm_config_post(project_id: str, process_key: str, request: ProcessLLMTestRequest):
    """Test a specific process LLM configuration with POST request"""
    try:
        # Validate process type
        try:
            process_enum = LLMProcessType(process_key)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid process type: {process_key}")
        
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Determine configuration to use
        if request.use_project_default:
            # Use project's default LLM configuration
            if not project.llm_api_key_id:
                return {
                    "success": False,
                    "status": "error",
                    "error": "Project does not have a default LLM configuration set"
                }
            
            # Get the LLM configuration from database
            try:
                from app.core.project_service import get_llm_configurations_from_db
                llm_configs = get_llm_configurations_from_db()
                llm_config = llm_configs.get(project.llm_api_key_id)
                
                if not llm_config:
                    return {
                        "success": False,
                        "status": "error",
                        "error": f"LLM configuration '{project.llm_api_key_id}' not found in database"
                    }
                
                # Extract configuration details
                provider = llm_config.get('provider')
                model = llm_config.get('model')
                api_key = llm_config.get('api_key')
                temperature = llm_config.get('temperature', 0.1)
                
                if not provider or not model:
                    return {
                        "success": False,
                        "status": "error",
                        "error": f"Invalid LLM configuration: missing provider or model"
                    }
                    
            except Exception as e:
                logger.error(f"Error loading project LLM config: {e}")
                return {
                    "success": False,
                    "status": "error",
                    "error": f"Failed to load project LLM configuration: {str(e)}"
                }
        else:
            # Use provided process-specific configuration
            if not request.provider or not request.model:
                return {
                    "success": False,
                    "error": "Provider and model are required when not using project default"
                }
            
            provider = request.provider
            model = request.model
            api_key = request.api_key
            temperature = request.temperature or 0.1
        
        try:
            # Create LLM instance from the configuration
            llm = llm_factory._instantiate_llm(
                provider=provider,
                model=model,
                api_key=api_key,
                temperature=temperature,
                max_tokens=100
            )
            if not llm:
                return {
                    "success": False,
                    "error": f"Failed to create LLM instance for {provider}/{model}"
                }
            
            # Special handling for Ollama to provide better error messages
            if provider.lower() == 'ollama':
                from app.services.ollama_service import ollama_service
                test_result = await ollama_service.test_model(
                    model_name=model,
                    prompt=request.query or "Hello, please respond with 'OK' to confirm you're working."
                )
                
                if not test_result["success"]:
                    return {
                        "success": False,
                        "status": "error",
                        "error": test_result["error"],
                        "suggestion": test_result.get("suggestion", "")
                    }
                
                return {
                    "success": True,
                    "status": "success", 
                    "message": f"{process_key} LLM is working correctly",
                    "test_response": test_result["response"],
                    "llm_provider": provider,
                    "llm_model": model,
                    "query": request.query or "Hello, please respond with 'OK' to confirm you're working.",
                    "duration_ms": test_result.get("total_duration", 0) / 1000000 if test_result.get("total_duration") else None
                }
            
            # Test the LLM with the provided query (for non-Ollama providers)
            from langchain.schema import HumanMessage
            test_message = request.query or "Hello, please respond with 'OK' to confirm you're working."
            response = llm.invoke([HumanMessage(content=test_message)])
            
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            return {
                "success": True,
                "status": "success", 
                "message": f"{process_key} LLM is working correctly",
                "test_response": response_content[:100] + "..." if len(response_content) > 100 else response_content,
                "llm_provider": provider,
                "llm_model": model,
                "query": test_message
            }
            
        except Exception as llm_error:
            return {
                "success": False,
                "status": "error",
                "error": f"LLM test failed: {str(llm_error)}",
                "error_type": type(llm_error).__name__
            }
        
    except Exception as e:
        logger.error(f"Error testing {process_key} LLM for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/test-process-llm/{process_type}")
async def test_process_llm_config(project_id: str, process_type: str):
    """Test a specific process LLM configuration"""
    try:
        # Validate process type
        try:
            process_enum = LLMProcessType(process_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid process type: {process_type}")
        
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get process-specific LLM
        try:
            llm = llm_factory.get_process_llm(project, process_enum, fallback_to_project_default=False)
            if not llm:
                return {"status": "not_configured", "message": f"No LLM configured for {process_type}"}
            
            # Test the LLM with a simple query
            from langchain.schema import HumanMessage
            test_message = "Hello, please respond with 'OK' to confirm you're working."
            response = llm.invoke([HumanMessage(content=test_message)])
            
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            return {
                "status": "success", 
                "message": f"{process_type} LLM is working correctly",
                "test_response": response_content[:100] + "..." if len(response_content) > 100 else response_content,
                "llm_provider": type(llm).__name__,
                "llm_model": getattr(llm, "model", None) or getattr(llm, "model_name", "unknown")
            }
            
        except Exception as llm_error:
            return {
                "status": "error",
                "message": f"LLM test failed: {str(llm_error)}",
                "error_type": type(llm_error).__name__
            }
        
    except Exception as e:
        logger.error(f"Error testing {process_type} LLM for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/{process_type}", response_model=LLMRecommendationsResponse)
async def get_llm_recommendations(process_type: str):
    """Get recommended LLM models for a specific process type"""
    try:
        # Validate process type
        try:
            process_enum = LLMProcessType(process_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid process type: {process_type}")
        
        recommendations = llm_factory.get_recommended_models(process_enum)
        
        # Process descriptions
        descriptions = {
            LLMProcessType.ENTITY_EXTRACTION: "Extract infrastructure entities and relationships from documents. Requires good JSON formatting and technical understanding.",
            LLMProcessType.CREW_ASSESSMENT: "Multi-agent infrastructure assessment and migration planning. Requires advanced reasoning and domain expertise.",
            LLMProcessType.CREW_DOCUMENTATION: "Generate professional documentation and reports. Requires excellent writing and formatting capabilities.",
            LLMProcessType.RAG_SYNTHESIS: "Synthesize search results into coherent responses. Requires good summarization and context understanding.",
            LLMProcessType.HYBRID_SEARCH: "Generate Cypher queries for graph databases. Requires technical precision and query understanding."
        }
        
        return LLMRecommendationsResponse(
            process_type=process_type,
            recommendations=recommendations,
            description=descriptions.get(process_enum, "No description available")
        )
        
    except Exception as e:
        logger.error(f"Error getting recommendations for {process_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/llm-usage-summary")
async def get_project_llm_usage_summary(project_id: str):
    """Get summary of LLM usage across all processes for a project"""
    try:
        project_service = get_project_service()
        project = project_service.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        summary = {
            "project_id": project_id,
            "default_llm": {
                "provider": getattr(project, "llm_provider", None),
                "model": getattr(project, "llm_model", None),
                "api_key_id": getattr(project, "llm_api_key_id", None)
            },
            "process_specific": {},
            "fallback_usage": []
        }
        
        # Check each process type
        for process_type in LLMProcessType:
            try:
                llm = llm_factory.get_process_llm(project, process_type, fallback_to_project_default=False)
                if llm:
                    summary["process_specific"][process_type.value] = {
                        "configured": True,
                        "provider": type(llm).__name__,
                        "model": getattr(llm, "model", None) or getattr(llm, "model_name", "unknown")
                    }
                else:
                    summary["process_specific"][process_type.value] = {"configured": False}
                    summary["fallback_usage"].append(process_type.value)
            except Exception as e:
                summary["process_specific"][process_type.value] = {
                    "configured": False,
                    "error": str(e)
                }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting LLM usage summary for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
