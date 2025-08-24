"""
AI Agent Orchestration Dashboard Service

This service provides:
1. Real-time AI agent monitoring and control
2. Agent performance analytics and insights
3. Dynamic agent configuration and scaling
4. Agent workflow orchestration and management
5. Advanced agent debugging and diagnostics
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AgentStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"
    STARTING = "starting"
    STOPPING = "stopping"

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentType(str, Enum):
    DISCOVERY_ANALYST = "discovery_analyst"
    CLOUD_ARCHITECT = "cloud_architect"
    RISK_OFFICER = "risk_officer"
    PROGRAM_MANAGER = "program_manager"
    DOCUMENT_RESEARCHER = "document_researcher"
    CONTENT_ARCHITECT = "content_architect"
    QUALITY_REVIEWER = "quality_reviewer"

@dataclass
class AgentMetrics:
    """Agent performance metrics"""
    agent_id: str
    tasks_completed: int
    tasks_failed: int
    average_task_duration: float
    total_tokens_used: int
    total_cost: float
    uptime_hours: float
    last_activity: datetime
    success_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['last_activity'] = self.last_activity.isoformat()
        return data

@dataclass
class AgentInstance:
    """Represents an active agent instance"""
    agent_id: str
    agent_type: AgentType
    status: AgentStatus
    current_task_id: Optional[str]
    project_id: Optional[str]
    created_at: datetime
    last_heartbeat: datetime
    configuration: Dict[str, Any]
    capabilities: List[str]
    resource_usage: Dict[str, float]
    metrics: AgentMetrics
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_heartbeat'] = self.last_heartbeat.isoformat()
        data['metrics'] = self.metrics.to_dict()
        return data

@dataclass
class AgentTask:
    """Represents a task assigned to an agent"""
    task_id: str
    agent_id: str
    project_id: str
    task_type: str
    task_description: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    estimated_duration: Optional[float]
    actual_duration: Optional[float]
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    progress_percentage: float
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.started_at:
            data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data

class AgentOrchestrationManager:
    """Manages AI agent orchestration, monitoring, and control"""
    
    def __init__(self):
        self.agents: Dict[str, AgentInstance] = {}
        self.tasks: Dict[str, AgentTask] = {}
        self.task_queue: List[str] = []
        self.websocket_connections: List[WebSocket] = []
        
        # Service URLs
        self.ai_agent_service_url = os.getenv("AI_AGENT_SERVICE_URL", "http://localhost:8006")
        self.websocket_service_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009")
        self.service_registry_url = os.getenv("SERVICE_REGISTRY_URL", "http://localhost:8011")
        
        logger.info("Agent Orchestration Manager initialized")
    
    async def initialize(self):
        """Initialize the orchestration manager"""
        # Start background tasks
        asyncio.create_task(self._agent_monitoring_loop())
        asyncio.create_task(self._task_scheduling_loop())
        asyncio.create_task(self._metrics_collection_loop())
        
        logger.info("Agent Orchestration Manager started")
    
    async def register_agent(self, agent_type: AgentType, configuration: Dict[str, Any]) -> str:
        """Register a new agent instance"""
        agent_id = str(uuid.uuid4())
        
        # Create agent metrics
        metrics = AgentMetrics(
            agent_id=agent_id,
            tasks_completed=0,
            tasks_failed=0,
            average_task_duration=0.0,
            total_tokens_used=0,
            total_cost=0.0,
            uptime_hours=0.0,
            last_activity=datetime.now(),
            success_rate=100.0
        )
        
        # Create agent instance
        agent = AgentInstance(
            agent_id=agent_id,
            agent_type=agent_type,
            status=AgentStatus.STARTING,
            current_task_id=None,
            project_id=None,
            created_at=datetime.now(),
            last_heartbeat=datetime.now(),
            configuration=configuration,
            capabilities=self._get_agent_capabilities(agent_type),
            resource_usage={"cpu": 0.0, "memory": 0.0, "tokens_per_hour": 0.0},
            metrics=metrics
        )
        
        self.agents[agent_id] = agent
        
        # Notify via WebSocket
        await self._broadcast_agent_update(agent_id, "registered")
        
        logger.info(f"Agent registered: {agent_id} ({agent_type})")
        return agent_id
    
    async def assign_task(self, task_type: str, project_id: str, task_description: str, 
                         input_data: Dict[str, Any], preferred_agent_type: Optional[AgentType] = None) -> str:
        """Assign a task to an available agent"""
        task_id = str(uuid.uuid4())
        
        # Find the best agent for this task
        agent_id = await self._find_best_agent(task_type, preferred_agent_type)
        
        if not agent_id:
            raise HTTPException(status_code=503, detail="No available agents for this task")
        
        # Create task
        task = AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            project_id=project_id,
            task_type=task_type,
            task_description=task_description,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            started_at=None,
            completed_at=None,
            estimated_duration=self._estimate_task_duration(task_type),
            actual_duration=None,
            input_data=input_data,
            output_data=None,
            error_message=None,
            progress_percentage=0.0
        )
        
        self.tasks[task_id] = task
        self.task_queue.append(task_id)
        
        # Update agent status
        agent = self.agents[agent_id]
        agent.status = AgentStatus.BUSY
        agent.current_task_id = task_id
        agent.project_id = project_id
        
        # Notify via WebSocket
        await self._broadcast_task_update(task_id, "assigned")
        
        logger.info(f"Task assigned: {task_id} to agent {agent_id}")
        return task_id
    
    async def _find_best_agent(self, task_type: str, preferred_agent_type: Optional[AgentType] = None) -> Optional[str]:
        """Find the best available agent for a task"""
        available_agents = [
            agent for agent in self.agents.values()
            if agent.status == AgentStatus.IDLE
        ]
        
        if preferred_agent_type:
            available_agents = [
                agent for agent in available_agents
                if agent.agent_type == preferred_agent_type
            ]
        
        if not available_agents:
            return None
        
        # Score agents based on performance metrics and capabilities
        best_agent = None
        best_score = -1
        
        for agent in available_agents:
            score = self._calculate_agent_score(agent, task_type)
            if score > best_score:
                best_score = score
                best_agent = agent
        
        return best_agent.agent_id if best_agent else None
    
    def _calculate_agent_score(self, agent: AgentInstance, task_type: str) -> float:
        """Calculate agent score for task assignment"""
        score = 0.0
        
        # Success rate (40% weight)
        score += agent.metrics.success_rate * 0.4
        
        # Performance (30% weight)
        if agent.metrics.average_task_duration > 0:
            performance_score = min(100.0, 60.0 / agent.metrics.average_task_duration)
            score += performance_score * 0.3
        
        # Experience (20% weight)
        experience_score = min(100.0, agent.metrics.tasks_completed * 2)
        score += experience_score * 0.2
        
        # Resource availability (10% weight)
        resource_score = 100.0 - (agent.resource_usage.get("cpu", 0) + agent.resource_usage.get("memory", 0)) / 2
        score += resource_score * 0.1
        
        return score
    
    def _get_agent_capabilities(self, agent_type: AgentType) -> List[str]:
        """Get capabilities for an agent type"""
        capabilities_map = {
            AgentType.DISCOVERY_ANALYST: [
                "infrastructure_analysis", "dependency_mapping", "risk_assessment",
                "documentation_review", "hybrid_search", "graph_analysis"
            ],
            AgentType.CLOUD_ARCHITECT: [
                "architecture_design", "cloud_services_mapping", "cost_optimization",
                "security_assessment", "scalability_planning", "migration_planning"
            ],
            AgentType.RISK_OFFICER: [
                "compliance_validation", "security_audit", "risk_mitigation",
                "regulatory_assessment", "data_governance", "audit_reporting"
            ],
            AgentType.PROGRAM_MANAGER: [
                "project_planning", "timeline_management", "resource_allocation",
                "stakeholder_communication", "progress_tracking", "delivery_management"
            ],
            AgentType.DOCUMENT_RESEARCHER: [
                "content_research", "information_gathering", "source_validation",
                "fact_checking", "reference_compilation", "knowledge_synthesis"
            ],
            AgentType.CONTENT_ARCHITECT: [
                "document_structuring", "content_organization", "narrative_design",
                "section_planning", "flow_optimization", "template_creation"
            ],
            AgentType.QUALITY_REVIEWER: [
                "content_review", "quality_assurance", "consistency_checking",
                "grammar_review", "technical_accuracy", "final_validation"
            ]
        }
        return capabilities_map.get(agent_type, [])
    
    def _estimate_task_duration(self, task_type: str) -> float:
        """Estimate task duration in minutes"""
        duration_map = {
            "infrastructure_analysis": 15.0,
            "architecture_design": 20.0,
            "risk_assessment": 10.0,
            "document_generation": 12.0,
            "content_review": 8.0,
            "compliance_check": 6.0,
            "cost_analysis": 10.0,
            "migration_planning": 25.0
        }
        return duration_map.get(task_type, 15.0)
    
    async def _agent_monitoring_loop(self):
        """Monitor agent health and status"""
        while True:
            try:
                current_time = datetime.now()
                
                for agent_id, agent in list(self.agents.items()):
                    # Check for stale agents (no heartbeat in 5 minutes)
                    if (current_time - agent.last_heartbeat).total_seconds() > 300:
                        agent.status = AgentStatus.OFFLINE
                        if agent.current_task_id:
                            await self._handle_failed_task(agent.current_task_id, "Agent offline")
                    
                    # Update uptime
                    agent.metrics.uptime_hours = (current_time - agent.created_at).total_seconds() / 3600
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in agent monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _task_scheduling_loop(self):
        """Process pending tasks"""
        while True:
            try:
                if self.task_queue:
                    task_id = self.task_queue.pop(0)
                    task = self.tasks.get(task_id)
                    
                    if task and task.status == TaskStatus.PENDING:
                        await self._execute_task(task)
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in task scheduling loop: {e}")
                await asyncio.sleep(30)
    
    async def _metrics_collection_loop(self):
        """Collect and update agent metrics"""
        while True:
            try:
                for agent in self.agents.values():
                    await self._update_agent_metrics(agent)
                
                # Broadcast metrics update
                await self._broadcast_metrics_update()
                
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(120)
    
    async def _execute_task(self, task: AgentTask):
        """Execute a task using the AI Agent Service"""
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            
            # Call AI Agent Service
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.ai_agent_service_url}/agents/{task.agent_id}/execute",
                    json={
                        "task_id": task.task_id,
                        "task_type": task.task_type,
                        "description": task.task_description,
                        "input_data": task.input_data,
                        "project_id": task.project_id
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    task.output_data = result.get("output_data")
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now()
                    task.progress_percentage = 100.0
                    
                    # Update agent metrics
                    agent = self.agents[task.agent_id]
                    agent.status = AgentStatus.IDLE
                    agent.current_task_id = None
                    agent.metrics.tasks_completed += 1
                    agent.metrics.last_activity = datetime.now()
                    
                    if task.started_at and task.completed_at:
                        duration = (task.completed_at - task.started_at).total_seconds() / 60
                        task.actual_duration = duration
                        
                        # Update average duration
                        total_tasks = agent.metrics.tasks_completed + agent.metrics.tasks_failed
                        if total_tasks > 1:
                            agent.metrics.average_task_duration = (
                                (agent.metrics.average_task_duration * (total_tasks - 1) + duration) / total_tasks
                            )
                        else:
                            agent.metrics.average_task_duration = duration
                    
                else:
                    await self._handle_failed_task(task.task_id, f"AI Agent Service error: {response.status_code}")
                    
        except Exception as e:
            await self._handle_failed_task(task.task_id, str(e))
    
    async def _handle_failed_task(self, task_id: str, error_message: str):
        """Handle a failed task"""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        task.status = TaskStatus.FAILED
        task.error_message = error_message
        task.completed_at = datetime.now()
        
        # Update agent
        agent = self.agents.get(task.agent_id)
        if agent:
            agent.status = AgentStatus.IDLE
            agent.current_task_id = None
            agent.metrics.tasks_failed += 1
            agent.metrics.last_activity = datetime.now()
            
            # Update success rate
            total_tasks = agent.metrics.tasks_completed + agent.metrics.tasks_failed
            agent.metrics.success_rate = (agent.metrics.tasks_completed / total_tasks) * 100 if total_tasks > 0 else 100.0
        
        await self._broadcast_task_update(task_id, "failed")
        logger.error(f"Task {task_id} failed: {error_message}")
    
    async def _update_agent_metrics(self, agent: AgentInstance):
        """Update agent performance metrics"""
        try:
            # Simulate resource usage updates (in real implementation, get from monitoring)
            import random
            agent.resource_usage = {
                "cpu": random.uniform(10, 80) if agent.status == AgentStatus.BUSY else random.uniform(0, 20),
                "memory": random.uniform(20, 70) if agent.status == AgentStatus.BUSY else random.uniform(5, 30),
                "tokens_per_hour": random.uniform(100, 1000) if agent.status == AgentStatus.BUSY else 0
            }
            
            # Update token usage and cost (mock data)
            if agent.status == AgentStatus.BUSY:
                tokens_used = int(random.uniform(50, 500))
                agent.metrics.total_tokens_used += tokens_used
                agent.metrics.total_cost += tokens_used * 0.002  # Mock cost calculation
                
        except Exception as e:
            logger.error(f"Error updating metrics for agent {agent.agent_id}: {e}")
    
    async def _broadcast_agent_update(self, agent_id: str, action: str):
        """Broadcast agent updates via WebSocket"""
        message = {
            "type": "agent_update",
            "agent_id": agent_id,
            "action": action,
            "agent_data": self.agents[agent_id].to_dict() if agent_id in self.agents else None,
            "timestamp": datetime.now().isoformat()
        }
        await self._broadcast_message(message)
    
    async def _broadcast_task_update(self, task_id: str, action: str):
        """Broadcast task updates via WebSocket"""
        message = {
            "type": "task_update",
            "task_id": task_id,
            "action": action,
            "task_data": self.tasks[task_id].to_dict() if task_id in self.tasks else None,
            "timestamp": datetime.now().isoformat()
        }
        await self._broadcast_message(message)
    
    async def _broadcast_metrics_update(self):
        """Broadcast aggregated metrics via WebSocket"""
        total_agents = len(self.agents)
        active_agents = len([a for a in self.agents.values() if a.status in [AgentStatus.BUSY, AgentStatus.IDLE]])
        total_tasks = len(self.tasks)
        completed_tasks = len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED])
        failed_tasks = len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED])
        
        message = {
            "type": "metrics_update",
            "metrics": {
                "total_agents": total_agents,
                "active_agents": active_agents,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "success_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 100.0,
                "average_task_duration": self._calculate_average_task_duration()
            },
            "timestamp": datetime.now().isoformat()
        }
        await self._broadcast_message(message)
    
    def _calculate_average_task_duration(self) -> float:
        """Calculate average task duration across all completed tasks"""
        completed_tasks = [t for t in self.tasks.values() if t.actual_duration is not None]
        if not completed_tasks:
            return 0.0
        return sum(t.actual_duration for t in completed_tasks) / len(completed_tasks)
    
    async def _broadcast_message(self, message: Dict[str, Any]):
        """Broadcast message to all WebSocket connections"""
        if not self.websocket_connections:
            return
        
        disconnected = []
        for websocket in self.websocket_connections:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for ws in disconnected:
            if ws in self.websocket_connections:
                self.websocket_connections.remove(ws)
    
    def get_agent_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data"""
        return {
            "agents": [agent.to_dict() for agent in self.agents.values()],
            "tasks": [task.to_dict() for task in self.tasks.values()],
            "metrics": {
                "total_agents": len(self.agents),
                "active_agents": len([a for a in self.agents.values() if a.status in [AgentStatus.BUSY, AgentStatus.IDLE]]),
                "total_tasks": len(self.tasks),
                "completed_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]),
                "failed_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED]),
                "average_task_duration": self._calculate_average_task_duration()
            },
            "timestamp": datetime.now().isoformat()
        }

# Global orchestration manager
orchestration_manager = AgentOrchestrationManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    await orchestration_manager.initialize()
    logger.info("AI Agent Orchestration Dashboard started successfully")
    
    yield
    
    # Shutdown
    logger.info("AI Agent Orchestration Dashboard shut down successfully")

# FastAPI app
app = FastAPI(
    title="AI Agent Orchestration Dashboard",
    description="Real-time AI agent monitoring, control, and orchestration for Nagarro Ascent Platform",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class AgentRegistrationRequest(BaseModel):
    agent_type: AgentType
    configuration: Dict[str, Any] = Field(default_factory=dict)

class TaskAssignmentRequest(BaseModel):
    task_type: str
    project_id: str
    task_description: str
    input_data: Dict[str, Any]
    preferred_agent_type: Optional[AgentType] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "3.0.0"
    service: str = "agent-orchestration-service"

# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )

@app.post("/agents/register")
async def register_agent(request: AgentRegistrationRequest):
    """Register a new agent instance"""
    agent_id = await orchestration_manager.register_agent(request.agent_type, request.configuration)
    return {"agent_id": agent_id, "message": "Agent registered successfully"}

@app.post("/tasks/assign")
async def assign_task(request: TaskAssignmentRequest):
    """Assign a task to an available agent"""
    task_id = await orchestration_manager.assign_task(
        request.task_type,
        request.project_id,
        request.task_description,
        request.input_data,
        request.preferred_agent_type
    )
    return {"task_id": task_id, "message": "Task assigned successfully"}

@app.get("/dashboard")
async def get_dashboard_data():
    """Get comprehensive dashboard data"""
    return orchestration_manager.get_agent_dashboard_data()

@app.get("/agents")
async def get_all_agents():
    """Get all registered agents"""
    return {
        "agents": [agent.to_dict() for agent in orchestration_manager.agents.values()],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get specific agent details"""
    agent = orchestration_manager.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {"agent": agent.to_dict()}

@app.get("/tasks")
async def get_all_tasks():
    """Get all tasks"""
    return {
        "tasks": [task.to_dict() for task in orchestration_manager.tasks.values()],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get specific task details"""
    task = orchestration_manager.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"task": task.to_dict()}

@app.get("/metrics")
async def get_metrics():
    """Get orchestration metrics"""
    dashboard_data = orchestration_manager.get_agent_dashboard_data()
    return {"metrics": dashboard_data["metrics"]}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    orchestration_manager.websocket_connections.append(websocket)
    
    try:
        # Send initial dashboard data
        initial_data = orchestration_manager.get_agent_dashboard_data()
        await websocket.send_text(json.dumps({
            "type": "initial_data",
            "data": initial_data
        }))
        
        # Keep connection alive
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in orchestration_manager.websocket_connections:
            orchestration_manager.websocket_connections.remove(websocket)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8013,
        reload=True,
        log_level="info"
    )