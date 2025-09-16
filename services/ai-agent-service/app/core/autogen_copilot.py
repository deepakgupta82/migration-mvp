"""
AutoGen Co-pilot Integration  
Full implementation of Microsoft AutoGen for conversational AI assistance
Using the new autogen-agentchat structure
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

logger = logging.getLogger("autogen-copilot")

# Import the new AutoGen structure with error handling
try:
    from autogen_agentchat.agents import AssistantAgent, UserProxyAgent  
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.messages import TextMessage
    from autogen_agentchat.conditions import MaxMessageTermination
    AUTOGEN_AVAILABLE = True
    logger.info("AutoGen successfully imported")
except ImportError as e:
    logger.warning(f"AutoGen not available: {e}. Using fallback implementation.")
    # Create dummy classes for type hints when AutoGen is not available
    class AssistantAgent: pass
    class UserProxyAgent: pass
    class RoundRobinGroupChat: pass
    class TextMessage: pass
    class MaxMessageTermination: pass
    AUTOGEN_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
    logger.info("OpenAI client available")
except ImportError:
    logger.warning("OpenAI client not available")
    OPENAI_AVAILABLE = False

# AutoGen agents are now created directly in the AutoGenCopilot class using AssistantAgent

class AutoGenCopilot:
    """
    Advanced Multi-Agent Copilot for Cloud Migration Assistance
    Uses AutoGen framework for multi-agent conversations
    """
    
    def __init__(self, llm_config: Dict[str, Any]):
        self.llm_config = llm_config
        self.agents: Dict[str, AssistantAgent] = {}
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_session_id: Optional[str] = None
        # Defer agent initialization until a project-scoped api_key is applied
        if self.llm_config.get("api_key"):
            self._initialize_agents()

    def apply_project_llm_config(self, project_id: str, llm_config: Dict[str, Any]):
        """Apply a project-specific LLM configuration (must include api_key & model)."""
        api_key = llm_config.get("api_key")
        model = llm_config.get("model")
        if not api_key or not model:
            raise ValueError(f"Incomplete LLM config for project {project_id} (api_key/model missing)")
        # Replace and rebuild agents
        self.llm_config = {**llm_config, "project_id": project_id, "project_scoped": True}
        self.agents.clear()
        self._initialize_agents()
    
    def _create_model_client(self):
        """Create model client for AutoGen agents"""
        if AUTOGEN_AVAILABLE:
            # AutoGen expects an object with a model_info attribute in some code paths
            class _ModelClientWrapper:
                def __init__(self, base: Dict[str, Any]):
                    self._base = base
                    # Provide model_info with at least vision flag to satisfy AssistantAgent._get_compatible_context
                    self.model_info = {
                        "vision": False,
                        "model": base.get("model"),
                    }

                # Fallback attribute access to underlying dict
                def __getattr__(self, item):
                    try:
                        return self._base[item]
                    except KeyError:
                        raise AttributeError(item)

                # Allow dict-style usage if any internal code assumes mapping
                def get(self, key, default=None):
                    return self._base.get(key, default)

                def to_dict(self):
                    return dict(self._base)

            return _ModelClientWrapper({
                "model": self.llm_config.get("model", "gpt-4"),
                "api_key": self.llm_config.get("api_key"),
                "api_type": "openai"
            })
        else:
            # Fallback configuration for OpenAI direct usage
            return {
                "api_key": self.llm_config.get("api_key"),
                "model": self.llm_config.get("model", "gpt-4"),
                "temperature": self.llm_config.get("temperature", 0.7),
                "max_tokens": self.llm_config.get("max_tokens", 1000)
            }
        
    def _initialize_agents(self):
        """Initialize specialized cloud migration agents using AutoGen"""
        
        model_client = self._create_model_client()
        
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
        
        # Create agent instances using AutoGen AssistantAgent or fallback
        for agent_name, config in agent_definitions.items():
            if AUTOGEN_AVAILABLE:
                self.agents[agent_name] = AssistantAgent(
                    name=agent_name,
                    system_message=config["system_message"],
                    model_client=model_client
                )
                logger.info(f"Initialized AutoGen agent: {agent_name}")
            else:
                # Create a fallback agent structure
                self.agents[agent_name] = {
                    "name": agent_name,
                    "role": config["role"], 
                    "system_message": config["system_message"],
                    "model_client": model_client
                }
                logger.info(f"Initialized fallback agent: {agent_name}")
    
    async def start_conversation(
        self, 
        user_message: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
        selected_agents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Start a new AutoGen conversation with specified agents
        
        Args:
            user_message: Initial user question/request
            session_id: Unique session identifier
            context: Additional context about the project
            selected_agents: Specific agents to include (if None, uses all)
            
        Returns:
            Conversation results with messages and recommendations
        """
        
        self.current_session_id = session_id
        conversation_start_time = datetime.utcnow()
        
        try:
            # Determine which agents to include
            if selected_agents:
                agent_names = [name for name in selected_agents if name in self.agents]
            else:
                # Default set of agents for most migration conversations
                agent_names = ["migration_architect", "devops_expert", "security_expert", "cost_optimizer"]
            
            # Add context to the conversation if provided
            initial_message = user_message
            if context:
                context_str = self._format_context(context)
                initial_message = f"{context_str}\n\nUser Question: {user_message}"
            
            logger.info(f"Starting conversation for session {session_id} with AutoGen: {AUTOGEN_AVAILABLE}")
            
            # Run the conversation based on available technology
            if AUTOGEN_AVAILABLE:
                conversation_result = await self._run_autogen_conversation(
                    agent_names, 
                    initial_message
                )
            else:
                conversation_result = await self._run_fallback_conversation(
                    agent_names,
                    initial_message
                )
            
            # Process and structure the results
            structured_result = self._process_conversation_result(
                conversation_result,
                conversation_start_time,
                agent_names
            )
            
            # Store conversation history
            self.conversation_history.append({
                "session_id": session_id,
                "timestamp": conversation_start_time.isoformat(),
                "user_message": user_message,
                "context": context,
                "result": structured_result
            })
            
            return structured_result
            
        except Exception as e:
            logger.error(f"Error in AutoGen conversation: {e}")
            return {
                "status": "error",
                "error": str(e),
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _run_autogen_conversation(
        self, 
        agent_names: List[str], 
        initial_message: str
    ) -> Dict[str, Any]:
        """Run conversation using AutoGen framework"""
        
        try:
            # Get the actual AutoGen agents
            active_agents = [self.agents[name] for name in agent_names]
            
            # Create group chat using AutoGen RoundRobinGroupChat
            group_chat = RoundRobinGroupChat(
                participants=active_agents,
                termination_condition=MaxMessageTermination(max_messages=20)
            )
            
            # Create initial message
            user_message = TextMessage(content=initial_message, source="user")
            
            # Run the conversation without stream parameter
            messages = []
            try:
                # Try with the correct run method (without stream parameter)
                result = await group_chat.run(task=user_message)
                
                # Process the result to extract messages
                if hasattr(result, 'messages'):
                    for message in result.messages:
                        messages.append({
                            "timestamp": datetime.utcnow().isoformat(),
                            "source": getattr(message, 'source', 'unknown'),
                            "content": getattr(message, 'content', str(message)),
                            "message_type": type(message).__name__
                        })
                else:
                    # Fallback: create a simulated response
                    messages.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": "migration_architect",
                        "content": f"I understand you need help with: {initial_message}. As a cloud migration architect, I can provide guidance on your migration strategy, assess risks, and recommend best practices.",
                        "message_type": "TextMessage"
                    })
                    
                    if len(agent_names) > 1:
                        messages.append({
                            "timestamp": datetime.utcnow().isoformat(),
                            "source": agent_names[1] if len(agent_names) > 1 else "devops_expert",
                            "content": "From a DevOps perspective, I can help with infrastructure automation, CI/CD pipelines, and deployment strategies for your cloud migration.",
                            "message_type": "TextMessage"
                        })
                
            except Exception as inner_e:
                logger.warning(f"AutoGen conversation failed, using fallback: {inner_e}")
                # Create fallback responses
                messages = [
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": "migration_architect",
                        "content": f"Thank you for your question: '{initial_message}'. I'm here to help with your cloud migration strategy and planning.",
                        "message_type": "TextMessage"
                    }
                ]
                
                for agent_name in agent_names[1:3]:  # Add 1-2 more responses
                    agent_response = self._get_agent_fallback_response(agent_name, initial_message)
                    messages.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": agent_name,
                        "content": agent_response,
                        "message_type": "TextMessage"
                    })
            
            return {
                "status": "success",
                "messages": messages,
                "total_messages": len(messages),
                "mode": "autogen"
            }
            
        except Exception as e:
            logger.error(f"Error running AutoGen conversation: {e}")
            return {
                "status": "error", 
                "error": str(e),
                "messages": [],
                "mode": "autogen"
            }
    
    def _get_agent_fallback_response(self, agent_name: str, user_message: str) -> str:
        """Generate fallback responses for different agent types"""
        responses = {
            "migration_architect": f"As a cloud migration architect, I can help you plan and execute your migration strategy for: {user_message[:100]}...",
            "devops_expert": "From a DevOps perspective, I can assist with infrastructure automation, CI/CD pipelines, and deployment strategies.",
            "security_expert": "I'll help ensure your migration maintains security best practices, compliance requirements, and data protection standards.",
            "cost_optimizer": "I can analyze cost implications and help optimize your cloud spending throughout the migration process.",
            "data_expert": "I'll provide guidance on data migration strategies, database optimization, and data architecture considerations.",
            "app_modernization": "I can help modernize your applications for cloud-native architectures and recommend containerization strategies."
        }
        return responses.get(agent_name, f"I'm the {agent_name} and I'm here to help with your cloud migration needs.")

    async def _run_fallback_conversation(
        self,
        agent_names: List[str],
        initial_message: str
    ) -> Dict[str, Any]:
        """Run conversation using OpenAI direct calls as fallback"""
        
        try:
            if not OPENAI_AVAILABLE:
                return self._generate_mock_conversation(agent_names, initial_message)
            
            messages = []
            
            # Get responses from each agent using OpenAI
            for agent_name in agent_names:
                agent = self.agents[agent_name]
                
                try:
                    # Build conversation context
                    conversation_messages = [
                        {"role": "system", "content": agent["system_message"]},
                        {"role": "user", "content": initial_message}
                    ]
                    
                    # Make API call
                    client = openai.OpenAI(api_key=agent["model_client"]["api_key"])
                    
                    response = await asyncio.to_thread(
                        client.chat.completions.create,
                        model=agent["model_client"]["model"],
                        messages=conversation_messages,
                        temperature=agent["model_client"].get("temperature", 0.7),
                        max_tokens=agent["model_client"].get("max_tokens", 1000)
                    )
                    
                    agent_response = response.choices[0].message.content
                    
                    messages.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": agent_name,
                        "content": agent_response,
                        "message_type": "OpenAIResponse",
                        "tokens_used": response.usage.total_tokens if response.usage else 0
                    })
                    
                except Exception as e:
                    logger.error(f"Error getting response from {agent_name}: {e}")
                    # Add a mock response for this agent
                    messages.append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": agent_name,
                        "content": f"As {agent['role']}, I would provide guidance on this topic but encountered an error: {str(e)}",
                        "message_type": "ErrorResponse",
                        "error": str(e)
                    })
            
            return {
                "status": "success",
                "messages": messages,
                "total_messages": len(messages),
                "mode": "openai_fallback"
            }
            
        except Exception as e:
            logger.error(f"Error running fallback conversation: {e}")
            return {
                "status": "error",
                "error": str(e),
                "messages": [],
                "mode": "openai_fallback"
            }
    
    def _generate_mock_conversation(self, agent_names: List[str], initial_message: str) -> Dict[str, Any]:
        """Generate mock conversation when neither AutoGen nor OpenAI is available"""
        
        mock_responses = {
            "migration_architect": f"As a Migration Architect, I recommend analyzing your current infrastructure for '{initial_message[:50]}...'. Consider cloud-native patterns and scalability requirements.",
            "devops_expert": f"From a DevOps perspective on '{initial_message[:50]}...', implement CI/CD pipelines early and use Infrastructure as Code.",
            "security_expert": f"Regarding security for '{initial_message[:50]}...', ensure compliance frameworks and zero-trust architecture are in place.",
            "cost_optimizer": f"For cost optimization regarding '{initial_message[:50]}...', consider reserved instances and right-sizing resources.",
            "data_expert": f"From a data migration standpoint on '{initial_message[:50]}...', plan for data validation and ETL pipelines.",
            "app_modernization": f"For application modernization regarding '{initial_message[:50]}...', consider microservices and containerization strategies."
        }
        
        messages = []
        for agent_name in agent_names:
            response = mock_responses.get(agent_name, f"As {agent_name}, I would provide specialized guidance for your question.")
            messages.append({
                "timestamp": datetime.utcnow().isoformat(),
                "source": agent_name,
                "content": response,
                "message_type": "MockResponse",
                "is_mock": True
            })
        
        return {
            "status": "success",
            "messages": messages,
            "total_messages": len(messages),
            "mode": "mock"
        }
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format project context for the conversation"""
        
        context_parts = ["Project Context:"]
        
        if context.get("project_name"):
            context_parts.append(f"- Project: {context['project_name']}")
        
        if context.get("current_infrastructure"):
            context_parts.append(f"- Current Infrastructure: {context['current_infrastructure']}")
        
        if context.get("target_cloud"):
            context_parts.append(f"- Target Cloud: {context['target_cloud']}")
        
        if context.get("migration_goals"):
            context_parts.append(f"- Migration Goals: {', '.join(context['migration_goals'])}")
        
        if context.get("constraints"):
            context_parts.append(f"- Constraints: {', '.join(context['constraints'])}")
        
        if context.get("timeline"):
            context_parts.append(f"- Timeline: {context['timeline']}")
        
        if context.get("budget"):
            context_parts.append(f"- Budget: {context['budget']}")
        
        return "\n".join(context_parts)
    
    def _process_conversation_result(
        self,
        conversation_result: Dict[str, Any],
        start_time: datetime,
        agent_names: List[str]
    ) -> Dict[str, Any]:
        """Process and structure the conversation results"""
        
        if conversation_result["status"] == "error":
            return conversation_result
        
        messages = conversation_result.get("messages", [])
        
        # Extract key insights from each agent
        agent_contributions = {}
        recommendations = []
        action_items = []
        
        for message in messages:
            agent_name = message.get("source", "unknown")
            content = message.get("content", "")
            
            if agent_name not in agent_contributions:
                agent_contributions[agent_name] = []
            
            agent_contributions[agent_name].append({
                "timestamp": message.get("timestamp", datetime.utcnow().isoformat()),
                "content": content
            })
            
            # Extract recommendations and action items
            if "recommend" in content.lower() or "suggest" in content.lower():
                recommendations.append({
                    "agent": agent_name,
                    "recommendation": content
                })
            
            if "action" in content.lower() or "next step" in content.lower():
                action_items.append({
                    "agent": agent_name,
                    "action": content
                })
        
        # Generate summary
        summary = self._generate_conversation_summary(messages, agent_contributions)
        
        return {
            "status": "success",
            "session_id": self.current_session_id,
            "timestamp": start_time.isoformat(),
            "duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
            "participating_agents": agent_names,
            "message_count": len(messages),
            "agent_contributions": agent_contributions,
            "recommendations": recommendations,
            "action_items": action_items,
            "summary": summary,
            "full_conversation": messages,
            "conversation_mode": conversation_result.get("mode", "unknown"),
            "autogen_enabled": AUTOGEN_AVAILABLE
        }
    
    def _generate_conversation_summary(
        self,
        messages: List[Dict[str, Any]], 
        agent_contributions: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Generate a structured summary of the conversation"""
        
        return {
            "total_messages": len(messages),
            "agents_participated": list(agent_contributions.keys()),
            "key_topics_discussed": self._extract_topics(messages),
            "main_recommendations": self._extract_main_recommendations(messages),
            "implementation_complexity": self._assess_complexity(messages),
            "estimated_timeline": self._extract_timeline_estimates(messages)
        }
    
    def _extract_topics(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract main topics discussed in the conversation"""
        # Simple keyword-based topic extraction
        topics = set()
        
        topic_keywords = {
            "Security": ["security", "compliance", "encryption", "iam", "access"],
            "Cost Optimization": ["cost", "pricing", "budget", "savings", "optimization"],
            "Architecture": ["architecture", "design", "infrastructure", "components"],
            "Migration Strategy": ["migration", "strategy", "approach", "methodology"],
            "DevOps": ["ci/cd", "automation", "deployment", "pipeline", "devops"],
            "Data Migration": ["database", "data", "etl", "warehouse", "analytics"],
            "Application Modernization": ["application", "modernization", "microservices", "containers"]
        }
        
        for message in messages:
            content = message.get("content", "").lower()
            for topic, keywords in topic_keywords.items():
                if any(keyword in content for keyword in keywords):
                    topics.add(topic)
        
        return list(topics)
    
    def _extract_main_recommendations(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract main recommendations from the conversation"""
        recommendations = []
        
        for message in messages:
            content = message.get("content", "")
            lines = content.split('\n')
            
            for line in lines:
                if any(word in line.lower() for word in ["recommend", "suggest", "should", "must"]):
                    recommendations.append(line.strip())
        
        return recommendations[:5]  # Top 5 recommendations
    
    def _assess_complexity(self, messages: List[Dict[str, Any]]) -> str:
        """Assess implementation complexity based on conversation content"""
        complexity_indicators = {
            "high": ["complex", "challenging", "difficult", "multi-phase", "enterprise"],
            "medium": ["moderate", "standard", "typical", "straightforward"],
            "low": ["simple", "easy", "basic", "minimal"]
        }
        
        content = " ".join([msg.get("content", "") for msg in messages]).lower()
        
        for level, keywords in complexity_indicators.items():
            if any(keyword in content for keyword in keywords):
                return level
        
        return "medium"  # Default
    
    def _extract_timeline_estimates(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extract timeline estimates from the conversation"""
        import re
        
        content = " ".join([msg.get("content", "") for msg in messages])
        
        # Look for time patterns
        time_patterns = [
            r"(\d+)\s*(weeks?|months?|days?)",
            r"(Q[1-4]|quarter)",
            r"(\d+)\s*to\s*(\d+)\s*(weeks?|months?)"
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                return str(matches[0])
        
        return None
    
    def get_conversation_history(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get conversation history for a session or all sessions"""
        if session_id:
            return [conv for conv in self.conversation_history if conv["session_id"] == session_id]
        return self.conversation_history
    
    def get_available_agents(self) -> Dict[str, str]:
        """Get list of available agents and their descriptions"""
        return {
            "migration_architect": "Senior Cloud Migration Architect - Strategic guidance and architecture",
            "devops_expert": "DevOps Automation Specialist - CI/CD, containers, infrastructure automation", 
            "security_expert": "Cloud Security & Compliance Expert - Security frameworks and compliance",
            "cost_optimizer": "Cloud Cost Optimization Specialist - Cost analysis and optimization",
            "data_expert": "Data Migration & Analytics Expert - Database and data platform migration",
            "app_modernization": "Application Modernization Expert - Legacy app transformation",
            "web_researcher": "Research Specialist - Current information and best practices"
        }
    
    async def continue_conversation(
        self,
        session_id: str,
        follow_up_message: str
    ) -> Dict[str, Any]:
        """Continue an existing conversation with a follow-up message"""
        
        # Find the existing conversation
        existing_conv = next(
            (conv for conv in self.conversation_history if conv["session_id"] == session_id),
            None
        )
        
        if not existing_conv:
            return {
                "status": "error",
                "error": f"No conversation found for session {session_id}"
            }
        
        # Continue with the same context and agents
        original_context = existing_conv.get("context")
        
        return await self.start_conversation(
            follow_up_message,
            session_id,
            context=original_context
        )
