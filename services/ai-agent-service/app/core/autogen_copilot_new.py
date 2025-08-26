"""
AutoGen Co-pilot Implementation with OpenAI Integration
This module provides a multi-agent conversation system for cloud migration assistance
using OpenAI's API with AutoGen-style conversation patterns.
"""

import asyncio
import datetime
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import openai
from openai import AsyncOpenAI

# Configure logging
logger = logging.getLogger(__name__)


class CloudMigrationAgent:
    """
    Individual cloud migration agent using OpenAI API
    Replaces AutoGen agents with direct OpenAI integration
    """
    
    def __init__(self, name: str, role: str, system_message: str, llm_config: Dict[str, Any]):
        self.name = name
        self.role = role
        self.system_message = system_message
        self.llm_config = llm_config
        self.conversation_history: List[Dict[str, str]] = []
        
        # Initialize OpenAI client
        api_key = llm_config.get("api_key") or llm_config.get("openai_api_key")
        if not api_key:
            raise ValueError("OpenAI API key is required")
            
        self.client = AsyncOpenAI(api_key=api_key)
        
        # Default model configuration
        self.model = llm_config.get("model", "gpt-4")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 1500)
    
    async def generate_response(self, user_input: str) -> str:
        """
        Generate response using OpenAI API
        """
        try:
            # Prepare messages for OpenAI API
            messages = [
                {"role": "system", "content": self.system_message}
            ]
            
            # Add conversation history
            for msg in self.conversation_history[-5:]:  # Keep last 5 exchanges for context
                messages.append(msg)
            
            # Add current user input
            messages.append({"role": "user", "content": user_input})
            
            # Make API call
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            # Extract response text
            response_text = response.choices[0].message.content
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": response_text})
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error generating response from {self.name}: {e}")
            # Return fallback response
            return f"I apologize, but I'm currently unable to provide a detailed response due to a technical issue. As a {self.role}, I recommend consulting the official documentation for your specific cloud migration requirements."


class AutoGenCopilot:
    """
    Advanced Multi-Agent Copilot for Cloud Migration Assistance
    Provides AutoGen-style conversations using OpenAI with specialized agents
    """
    
    def __init__(self, llm_config: Dict[str, Any]):
        self.llm_config = llm_config
        self.agents: Dict[str, CloudMigrationAgent] = {}
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_session_id: Optional[str] = None
        
        # Initialize specialized agents
        self._initialize_agents()
        
    def _initialize_agents(self):
        """Initialize specialized cloud migration agents"""
        
        agent_definitions = {
            "migration_architect": {
                "role": "Senior Cloud Migration Architect",
                "system_message": """You are a Senior Cloud Migration Architect with deep expertise in:
                - AWS, Azure, and GCP migration strategies
                - Application modernization and containerization  
                - Infrastructure as Code (Terraform, CloudFormation)
                - Database migration and data lake architecture
                - Security and compliance during migration
                
                Your role is to provide strategic guidance on cloud migration projects.
                Always consider cost optimization, security, scalability, and business continuity.
                Provide detailed architectural recommendations with clear rationale.
                Keep responses focused, practical, and actionable."""
            },
            
            "devops_expert": {
                "role": "DevOps Automation Specialist",
                "system_message": """You are a DevOps automation specialist focusing on:
                - CI/CD pipeline design and implementation
                - Kubernetes and container orchestration
                - Infrastructure automation and monitoring
                - Site reliability engineering (SRE) practices
                - Cloud-native application deployment
                
                Provide practical implementation guidance, code snippets, and automation scripts.
                Focus on best practices for deployment, scaling, and operational excellence.
                Always consider automation, monitoring, and reliability."""
            },
            
            "security_expert": {
                "role": "Cloud Security & Compliance Expert",
                "system_message": """You are a Cloud Security and Compliance expert specializing in:
                - Cloud security frameworks (AWS Well-Architected, Azure Security Center)
                - Identity and Access Management (IAM) design
                - Data encryption and key management
                - Compliance standards (SOC 2, GDPR, HIPAA, ISO 27001)
                - Security monitoring and incident response
                
                Ensure all recommendations meet security best practices and compliance requirements.
                Identify potential security risks and provide concrete mitigation strategies.
                Focus on zero-trust principles and defense in depth."""
            },
            
            "cost_optimizer": {
                "role": "Cloud Cost Optimization Specialist",
                "system_message": """You are a Cloud Cost Optimization specialist focused on:
                - Cloud resource rightsizing and cost analysis
                - Reserved instances and savings plans optimization
                - Multi-cloud cost comparison and strategy
                - FinOps practices and cost governance
                - Resource lifecycle management
                
                Analyze costs throughout migration planning and provide optimization recommendations.
                Consider both immediate migration costs and long-term operational expenses.
                Provide specific cost-saving strategies with quantifiable benefits."""
            },
            
            "data_expert": {
                "role": "Data Migration & Analytics Expert", 
                "system_message": """You are a Data Migration and Analytics expert specializing in:
                - Database migration strategies (rehost, replatform, refactor)
                - Data lake and warehouse architecture
                - ETL/ELT pipeline design and optimization
                - Big data technologies (Spark, Hadoop, streaming)
                - Data governance and quality assurance
                
                Focus on data architecture, migration patterns, and analytics platform design.
                Ensure data integrity, performance, and accessibility throughout migration.
                Consider data lineage, quality, and governance requirements."""
            },
            
            "app_modernization": {
                "role": "Application Modernization Expert",
                "system_message": """You are an Application Modernization specialist focusing on:
                - Legacy application assessment and refactoring strategies
                - Microservices architecture and API design
                - Serverless and event-driven architectures
                - Application performance optimization
                - Technology stack modernization (containerization, PaaS adoption)
                
                Provide guidance on application transformation, technology choices, and implementation approaches.
                Consider maintainability, scalability, and developer productivity.
                Focus on practical modernization patterns and best practices."""
            }
        }
        
        # Create agent instances
        for agent_name, config in agent_definitions.items():
            self.agents[agent_name] = CloudMigrationAgent(
                name=agent_name,
                role=config["role"],
                system_message=config["system_message"],
                llm_config=self.llm_config
            )
    
    async def start_conversation(
        self, 
        message: str, 
        selected_agents: Optional[List[str]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start a new conversation with selected agents using OpenAI-based implementation
        """
        try:
            # Generate session ID if not provided
            if session_id is None:
                session_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            self.current_session_id = session_id
            
            # Use all agents if none selected
            if selected_agents is None:
                selected_agents = list(self.agents.keys())
            
            # Validate selected agents
            invalid_agents = [agent for agent in selected_agents if agent not in self.agents]
            if invalid_agents:
                raise ValueError(f"Invalid agents selected: {invalid_agents}")
            
            # Initialize conversation history for this session
            conversation_entry = {
                "session_id": session_id,
                "timestamp": datetime.datetime.now().isoformat(),
                "user_message": message,
                "selected_agents": selected_agents,
                "agent_responses": [],
                "status": "started"
            }
            
            # Get responses from each selected agent
            agent_responses = []
            
            for agent_name in selected_agents:
                agent = self.agents[agent_name]
                
                try:
                    # Create conversation context with user message
                    conversation_context = f"User Query: {message}\n\nPlease provide your expert perspective based on your specialization."
                    
                    # Generate response from agent
                    response = await agent.generate_response(conversation_context)
                    
                    agent_response = {
                        "agent_name": agent_name,
                        "agent_role": agent.role,
                        "response": response,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "status": "completed"
                    }
                    
                    agent_responses.append(agent_response)
                    
                    logger.info(f"Agent {agent_name} provided response for session {session_id}")
                    
                except Exception as e:
                    logger.error(f"Error getting response from agent {agent_name}: {e}")
                    agent_response = {
                        "agent_name": agent_name,
                        "agent_role": agent.role,
                        "response": f"I apologize, but I encountered an error while processing your request. Please try again.",
                        "timestamp": datetime.datetime.now().isoformat(),
                        "status": "error",
                        "error": str(e)
                    }
                    agent_responses.append(agent_response)
            
            # Update conversation entry
            conversation_entry["agent_responses"] = agent_responses
            conversation_entry["status"] = "completed"
            
            # Add to conversation history
            self.conversation_history.append(conversation_entry)
            
            # Prepare response
            result = {
                "session_id": session_id,
                "status": "success",
                "user_message": message,
                "agent_responses": agent_responses,
                "total_agents": len(selected_agents),
                "successful_responses": len([r for r in agent_responses if r["status"] == "completed"]),
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            logger.info(f"Conversation started successfully: {session_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error starting conversation: {e}")
            raise RuntimeError(f"Failed to start conversation: {str(e)}")
    
    async def continue_conversation(
        self, 
        message: str, 
        session_id: str,
        selected_agents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Continue an existing conversation with follow-up message
        """
        try:
            # Find existing session
            session_history = None
            for conv in self.conversation_history:
                if conv["session_id"] == session_id:
                    session_history = conv
                    break
            
            if session_history is None:
                raise ValueError(f"Session {session_id} not found")
            
            # Use previously selected agents if none specified
            if selected_agents is None:
                selected_agents = session_history["selected_agents"]
            
            # Build conversation context from history
            context_messages = []
            context_messages.append(f"Original Query: {session_history['user_message']}")
            
            # Add previous agent responses for context
            for response in session_history.get("agent_responses", []):
                context_messages.append(f"{response['agent_role']}: {response['response'][:500]}...")
            
            # Add new follow-up question
            context_messages.append(f"Follow-up Question: {message}")
            
            conversation_context = "\n\n".join(context_messages)
            
            # Get responses from selected agents
            agent_responses = []
            
            for agent_name in selected_agents:
                if agent_name not in self.agents:
                    continue
                    
                agent = self.agents[agent_name]
                
                try:
                    response = await agent.generate_response(conversation_context)
                    
                    agent_response = {
                        "agent_name": agent_name,
                        "agent_role": agent.role,
                        "response": response,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "status": "completed"
                    }
                    
                    agent_responses.append(agent_response)
                    
                except Exception as e:
                    logger.error(f"Error getting follow-up response from agent {agent_name}: {e}")
                    agent_response = {
                        "agent_name": agent_name,
                        "agent_role": agent.role,
                        "response": f"I encountered an error while processing your follow-up question. Please try again.",
                        "timestamp": datetime.datetime.now().isoformat(),
                        "status": "error",
                        "error": str(e)
                    }
                    agent_responses.append(agent_response)
            
            # Create follow-up entry
            follow_up_entry = {
                "session_id": session_id,
                "timestamp": datetime.datetime.now().isoformat(),
                "user_message": message,
                "selected_agents": selected_agents,
                "agent_responses": agent_responses,
                "status": "completed",
                "type": "follow_up"
            }
            
            # Add to conversation history
            self.conversation_history.append(follow_up_entry)
            
            # Prepare response
            result = {
                "session_id": session_id,
                "status": "success",
                "user_message": message,
                "agent_responses": agent_responses,
                "total_agents": len(selected_agents),
                "successful_responses": len([r for r in agent_responses if r["status"] == "completed"]),
                "timestamp": datetime.datetime.now().isoformat(),
                "type": "follow_up"
            }
            
            logger.info(f"Conversation continued successfully: {session_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error continuing conversation: {e}")
            raise RuntimeError(f"Failed to continue conversation: {str(e)}")
            
    def get_conversation_history(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get conversation history for a specific session or all sessions
        """
        if session_id is None:
            return self.conversation_history
        
        return [conv for conv in self.conversation_history if conv["session_id"] == session_id]
    
    def get_available_agents(self) -> List[Dict[str, str]]:
        """
        Get list of available agents with their roles
        """
        return [
            {
                "name": agent_name,
                "role": agent.role,
                "description": agent.system_message[:200] + "..." if len(agent.system_message) > 200 else agent.system_message
            }
            for agent_name, agent in self.agents.items()
        ]
    
    def clear_conversation_history(self, session_id: Optional[str] = None):
        """
        Clear conversation history for a specific session or all sessions
        """
        if session_id is None:
            self.conversation_history.clear()
            logger.info("All conversation history cleared")
        else:
            self.conversation_history = [
                conv for conv in self.conversation_history 
                if conv["session_id"] != session_id
            ]
            logger.info(f"Conversation history cleared for session: {session_id}")
    
    def export_conversation(self, session_id: str, format: str = "json") -> str:
        """
        Export conversation history in specified format
        """
        session_data = self.get_conversation_history(session_id)
        
        if not session_data:
            raise ValueError(f"No conversation found for session: {session_id}")
        
        if format.lower() == "json":
            return json.dumps(session_data, indent=2, default=str)
        
        elif format.lower() == "markdown":
            markdown_content = []
            markdown_content.append(f"# Cloud Migration Conversation - {session_id}\n")
            
            for conv in session_data:
                markdown_content.append(f"## {conv.get('type', 'Initial').title()} Query")
                markdown_content.append(f"**Timestamp:** {conv['timestamp']}")
                markdown_content.append(f"**User Message:** {conv['user_message']}\n")
                
                markdown_content.append("### Agent Responses\n")
                
                for response in conv.get("agent_responses", []):
                    markdown_content.append(f"#### {response['agent_role']}")
                    markdown_content.append(f"**Agent:** {response['agent_name']}")
                    markdown_content.append(f"**Status:** {response['status']}")
                    markdown_content.append(f"**Response:**\n{response['response']}\n")
                    markdown_content.append("---\n")
            
            return "\n".join(markdown_content)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")


class StreamingAutoGenCopilot(AutoGenCopilot):
    """
    Streaming version of AutoGenCopilot for real-time WebSocket communication
    """
    
    def __init__(self, llm_config: Dict[str, Any]):
        super().__init__(llm_config)
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def stream_conversation(
        self,
        websocket,
        message: str,
        selected_agents: Optional[List[str]] = None,
        session_id: Optional[str] = None
    ):
        """
        Stream conversation responses in real-time via WebSocket
        """
        try:
            # Generate session ID if not provided
            if session_id is None:
                session_id = f"stream_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # Send session start message
            await websocket.send_text(json.dumps({
                "type": "session_start",
                "session_id": session_id,
                "timestamp": datetime.datetime.now().isoformat()
            }))
            
            # Use all agents if none selected
            if selected_agents is None:
                selected_agents = list(self.agents.keys())
            
            # Send agent list
            await websocket.send_text(json.dumps({
                "type": "agents_selected",
                "session_id": session_id,
                "agents": selected_agents,
                "total_agents": len(selected_agents)
            }))
            
            # Process each agent and stream responses
            agent_responses = []
            
            for i, agent_name in enumerate(selected_agents):
                if agent_name not in self.agents:
                    continue
                
                agent = self.agents[agent_name]
                
                # Send agent start message
                await websocket.send_text(json.dumps({
                    "type": "agent_start",
                    "session_id": session_id,
                    "agent_name": agent_name,
                    "agent_role": agent.role,
                    "agent_index": i + 1,
                    "total_agents": len(selected_agents)
                }))
                
                try:
                    # Create conversation context
                    conversation_context = f"User Query: {message}\n\nPlease provide your expert perspective based on your specialization."
                    
                    # Generate response from agent
                    response = await agent.generate_response(conversation_context)
                    
                    # Send agent response
                    agent_response = {
                        "agent_name": agent_name,
                        "agent_role": agent.role,
                        "response": response,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "status": "completed"
                    }
                    
                    await websocket.send_text(json.dumps({
                        "type": "agent_response",
                        "session_id": session_id,
                        **agent_response
                    }))
                    
                    agent_responses.append(agent_response)
                    
                except Exception as e:
                    logger.error(f"Error streaming response from agent {agent_name}: {e}")
                    
                    error_response = {
                        "agent_name": agent_name,
                        "agent_role": agent.role,
                        "response": f"I encountered an error while processing your request. Please try again.",
                        "timestamp": datetime.datetime.now().isoformat(),
                        "status": "error",
                        "error": str(e)
                    }
                    
                    await websocket.send_text(json.dumps({
                        "type": "agent_error",
                        "session_id": session_id,
                        **error_response
                    }))
                    
                    agent_responses.append(error_response)
            
            # Store conversation in history
            conversation_entry = {
                "session_id": session_id,
                "timestamp": datetime.datetime.now().isoformat(),
                "user_message": message,
                "selected_agents": selected_agents,
                "agent_responses": agent_responses,
                "status": "completed",
                "type": "streaming"
            }
            
            self.conversation_history.append(conversation_entry)
            
            # Send completion message
            await websocket.send_text(json.dumps({
                "type": "conversation_complete",
                "session_id": session_id,
                "total_agents": len(selected_agents),
                "successful_responses": len([r for r in agent_responses if r["status"] == "completed"]),
                "timestamp": datetime.datetime.now().isoformat()
            }))
            
            logger.info(f"Streaming conversation completed: {session_id}")
            
        except Exception as e:
            logger.error(f"Error in streaming conversation: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "session_id": session_id,
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }))


# Utility function for easy initialization
def create_autogen_copilot(llm_config: Dict[str, Any], streaming: bool = False) -> AutoGenCopilot:
    """
    Factory function to create AutoGen copilot instance
    
    Args:
        llm_config: OpenAI configuration dictionary
        streaming: Whether to create streaming version for WebSocket usage
        
    Returns:
        AutoGenCopilot or StreamingAutoGenCopilot instance
    """
    if streaming:
        return StreamingAutoGenCopilot(llm_config)
    return AutoGenCopilot(llm_config)
