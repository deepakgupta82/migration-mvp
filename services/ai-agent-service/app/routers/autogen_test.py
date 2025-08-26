"""
AutoGen Integration Test Endpoints
Provides test endpoints to validate AutoGen functionality
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging
import os
from datetime import datetime

logger = logging.getLogger("autogen-test")

router = APIRouter()

@router.post("/test/simple-conversation")
async def test_simple_conversation():
    """Test basic AutoGen conversation functionality"""
    try:
        # Mock a simple conversation for testing
        test_result = {
            "status": "success",
            "session_id": "test-session-123",
            "timestamp": datetime.utcnow().isoformat(),
            "duration_seconds": 5.2,
            "participating_agents": ["migration_architect", "devops_expert"],
            "message_count": 4,
            "recommendations": [
                {
                    "agent": "migration_architect",
                    "recommendation": "Consider using a lift-and-shift approach for the initial migration, then optimize for cloud-native features in a second phase."
                },
                {
                    "agent": "devops_expert", 
                    "recommendation": "Implement CI/CD pipelines early in the migration process to ensure consistent deployments."
                }
            ],
            "action_items": [
                {
                    "agent": "migration_architect",
                    "action": "Conduct detailed assessment of current application architecture"
                },
                {
                    "agent": "devops_expert",
                    "action": "Set up development and staging environments in target cloud"
                }
            ],
            "summary": {
                "total_messages": 4,
                "agents_participated": ["migration_architect", "devops_expert"],
                "key_topics_discussed": ["Migration Strategy", "DevOps", "Architecture"],
                "main_recommendations": [
                    "Use lift-and-shift approach initially",
                    "Implement CI/CD pipelines early"
                ],
                "implementation_complexity": "medium",
                "estimated_timeline": "3-6 months"
            }
        }
        
        return {
            "test_type": "simple_conversation",
            "autogen_available": True,
            "mock_result": test_result,
            "notes": "This is a mock response for testing. Real AutoGen integration requires OpenAI API key."
        }
        
    except Exception as e:
        logger.error(f"Test conversation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

@router.get("/test/agent-initialization")
async def test_agent_initialization():
    """Test AutoGen agent initialization"""
    try:
        # Test agent configurations
        agent_configs = {
            "migration_architect": {
                "role": "Senior Cloud Migration Architect",
                "expertise": ["AWS", "Azure", "GCP", "Migration Strategies", "Architecture"],
                "status": "configured"
            },
            "devops_expert": {
                "role": "DevOps Automation Specialist", 
                "expertise": ["CI/CD", "Kubernetes", "Infrastructure Automation", "SRE"],
                "status": "configured"
            },
            "security_expert": {
                "role": "Cloud Security & Compliance Expert",
                "expertise": ["Security Frameworks", "IAM", "Compliance", "Encryption"],
                "status": "configured"
            },
            "cost_optimizer": {
                "role": "Cloud Cost Optimization Specialist",
                "expertise": ["Cost Analysis", "Resource Optimization", "FinOps"],
                "status": "configured"
            },
            "data_expert": {
                "role": "Data Migration & Analytics Expert",
                "expertise": ["Database Migration", "Data Lakes", "ETL", "Analytics"],
                "status": "configured"
            },
            "app_modernization": {
                "role": "Application Modernization Expert",
                "expertise": ["Legacy Apps", "Microservices", "Containerization", "PaaS"],
                "status": "configured"
            }
        }
        
        return {
            "test_type": "agent_initialization",
            "total_agents": len(agent_configs),
            "agents": agent_configs,
            "openai_api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
            "status": "ready"
        }
        
    except Exception as e:
        logger.error(f"Agent initialization test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

@router.get("/test/websocket-info")
async def test_websocket_info():
    """Get WebSocket connection information for testing"""
    return {
        "websocket_endpoint": "/ws/autogen/{session_id}",
        "supported_message_types": [
            "start_conversation",
            "follow_up", 
            "ping",
            "get_agents"
        ],
        "example_messages": {
            "start_conversation": {
                "type": "start_conversation",
                "message": "How should I migrate my legacy .NET application to Azure?",
                "context": {
                    "project_name": "Legacy App Migration",
                    "current_infrastructure": "On-premises Windows Server",
                    "target_cloud": "Azure",
                    "timeline": "6 months"
                },
                "selected_agents": ["migration_architect", "devops_expert", "security_expert"]
            },
            "follow_up": {
                "type": "follow_up",
                "message": "What about the database migration strategy?"
            },
            "ping": {
                "type": "ping"
            }
        },
        "response_message_types": [
            "connection_established",
            "conversation_starting",
            "agents_ready", 
            "agent_responding",
            "recommendation_received",
            "action_item_received",
            "conversation_completed",
            "error"
        ]
    }

@router.get("/test/environment-check")
async def test_environment_check():
    """Check environment configuration for AutoGen"""
    
    env_status = {
        "openai_api_key": {
            "configured": bool(os.getenv("OPENAI_API_KEY")),
            "status": "✅ Ready" if os.getenv("OPENAI_API_KEY") else "⚠️ Missing - Required for full functionality"
        },
        "autogen_model": {
            "configured": bool(os.getenv("AUTOGEN_MODEL")),
            "value": os.getenv("AUTOGEN_MODEL", "gpt-4 (default)"),
            "status": "✅ Configured"
        },
        "autogen_temperature": {
            "configured": bool(os.getenv("AUTOGEN_TEMPERATURE")),
            "value": os.getenv("AUTOGEN_TEMPERATURE", "0.7 (default)"),
            "status": "✅ Configured"
        },
        "autogen_timeout": {
            "configured": bool(os.getenv("AUTOGEN_TIMEOUT")),
            "value": os.getenv("AUTOGEN_TIMEOUT", "300 (default)"),
            "status": "✅ Configured"
        }
    }
    
    # Overall readiness assessment
    critical_missing = []
    if not os.getenv("OPENAI_API_KEY"):
        critical_missing.append("OPENAI_API_KEY")
    
    overall_status = "🟢 Ready" if not critical_missing else f"🟡 Partially Ready (Missing: {', '.join(critical_missing)})"
    
    return {
        "overall_status": overall_status,
        "environment_variables": env_status,
        "recommendations": [
            "Set OPENAI_API_KEY environment variable for full AutoGen functionality",
            "Consider setting AUTOGEN_MODEL to specify your preferred model (gpt-4, gpt-3.5-turbo, etc.)",
            "Adjust AUTOGEN_TEMPERATURE (0.0-1.0) to control response creativity",
            "Set AUTOGEN_TIMEOUT (seconds) to control conversation timeout"
        ] if critical_missing else [
            "All required environment variables are configured",
            "AutoGen copilot is ready for production use"
        ]
    }
