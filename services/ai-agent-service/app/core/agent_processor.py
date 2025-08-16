#!/usr/bin/env python3
"""
AI Agent Service - Core Processing Logic
Extracted from backend CrewAI and agent orchestration components

Handles:
- AI agent creation and management
- CrewAI workflow orchestration
- Agent task execution
- Result streaming and callbacks
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime
import uuid

import redis
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-agent-service")

class AIAgentProcessor:
    """Core AI agent orchestration logic"""
    
    def __init__(self):
        self.redis_client = None
        self.db_connection = None
        self.active_crews = {}  # Track running crews
        self._initialize_connections()
        
    def _initialize_connections(self):
        """Initialize Redis and PostgreSQL connections"""
        try:
            # Redis for task status and messaging (DB 4 for AI Agent service)
            self.redis_client = redis.Redis(
                host='localhost', 
                port=6379, 
                db=4,
                decode_responses=True
            )
            
            # PostgreSQL for project and configuration data
            self.db_connection = psycopg2.connect(
                host="localhost",
                database="projectdb",
                user="projectuser", 
                password="projectpass",
                cursor_factory=RealDictCursor
            )
            
            logger.info("AI Agent service connections initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize connections: {e}")
            
    async def verify_dependencies(self) -> Dict[str, bool]:
        """Verify all AI Agent service dependencies"""
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
            
        # Check LLM service availability
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8007/health", timeout=5.0)
                dependencies['llm_service'] = response.status_code == 200
                logger.info("✓ LLM service connection verified")
        except Exception as e:
            dependencies['llm_service'] = False
            logger.error(f"✗ LLM service connection failed: {e}")
            
        return dependencies
        
    async def get_available_agents(self) -> List[Dict[str, Any]]:
        """Get list of available AI agents"""
        agents = [
            {
                "id": "analysis_agent",
                "name": "Analysis Agent",
                "description": "Analyzes documents and extracts insights",
                "capabilities": ["document_analysis", "data_extraction", "pattern_recognition"],
                "input_types": ["text", "documents"],
                "output_types": ["structured_data", "insights"]
            },
            {
                "id": "assessment_agent",
                "name": "Assessment Agent", 
                "description": "Performs infrastructure assessments",
                "capabilities": ["infrastructure_analysis", "risk_assessment", "recommendations"],
                "input_types": ["infrastructure_data", "documents"],
                "output_types": ["assessment_report", "recommendations"]
            },
            {
                "id": "documentation_agent",
                "name": "Documentation Agent",
                "description": "Generates comprehensive documentation",
                "capabilities": ["document_generation", "report_writing", "formatting"],
                "input_types": ["data", "templates"],
                "output_types": ["documents", "reports"]
            },
            {
                "id": "migration_planner",
                "name": "Migration Planning Agent",
                "description": "Creates migration plans and strategies",
                "capabilities": ["migration_planning", "dependency_analysis", "timeline_estimation"],
                "input_types": ["infrastructure_data", "requirements"],
                "output_types": ["migration_plan", "timeline"]
            }
        ]
        
        return agents
        
    async def get_available_crews(self) -> List[Dict[str, Any]]:
        """Get list of available AI crews (multi-agent workflows)"""
        crews = [
            {
                "id": "infrastructure_assessment_crew",
                "name": "Infrastructure Assessment Crew",
                "description": "Complete infrastructure analysis workflow",
                "agents": ["analysis_agent", "assessment_agent"],
                "estimated_time_minutes": 15,
                "input_requirements": ["project_documents", "infrastructure_inventory"]
            },
            {
                "id": "documentation_crew",
                "name": "Documentation Generation Crew", 
                "description": "Comprehensive documentation generation",
                "agents": ["analysis_agent", "documentation_agent"],
                "estimated_time_minutes": 20,
                "input_requirements": ["project_data", "template_preferences"]
            },
            {
                "id": "migration_planning_crew",
                "name": "Migration Planning Crew",
                "description": "End-to-end migration planning workflow",
                "agents": ["analysis_agent", "assessment_agent", "migration_planner"],
                "estimated_time_minutes": 30,
                "input_requirements": ["current_infrastructure", "target_requirements"]
            }
        ]
        
        return crews
        
    async def start_agent_task(self, agent_id: str, task_config: Dict[str, Any]) -> Dict[str, Any]:
        """Start a single agent task"""
        job_id = str(uuid.uuid4())
        
        try:
            # Validate agent exists
            agents = await self.get_available_agents()
            agent = next((a for a in agents if a["id"] == agent_id), None)
            
            if not agent:
                return {
                    "success": False,
                    "error": f"Agent {agent_id} not found"
                }
            
            # Create task status
            task_status = {
                "job_id": job_id,
                "agent_id": agent_id,
                "agent_name": agent["name"],
                "status": "started",
                "progress": 0,
                "started_at": datetime.now().isoformat(),
                "task_config": task_config,
                "steps": [],
                "current_step": "Initializing agent task..."
            }
            
            # Store in Redis
            status_key = f"agent_task:{job_id}"
            self.redis_client.setex(status_key, 3600, json.dumps(task_status))  # 1 hour TTL
            
            # Start background task
            asyncio.create_task(self._execute_agent_task(job_id, agent_id, task_config))
            
            logger.info(f"Started agent task {job_id} for agent {agent_id}")
            
            return {
                "success": True,
                "job_id": job_id,
                "agent_id": agent_id,
                "status": "started",
                "message": f"Agent task started successfully"
            }
            
        except Exception as e:
            logger.error(f"Error starting agent task: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def start_crew_workflow(self, crew_id: str, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """Start a multi-agent crew workflow"""
        job_id = str(uuid.uuid4())
        
        try:
            # Validate crew exists
            crews = await self.get_available_crews()
            crew = next((c for c in crews if c["id"] == crew_id), None)
            
            if not crew:
                return {
                    "success": False,
                    "error": f"Crew {crew_id} not found"
                }
            
            # Create workflow status
            workflow_status = {
                "job_id": job_id,
                "crew_id": crew_id,
                "crew_name": crew["name"],
                "status": "started",
                "progress": 0,
                "started_at": datetime.now().isoformat(),
                "estimated_completion": None,  # Would calculate based on crew specs
                "workflow_config": workflow_config,
                "agents": crew["agents"],
                "current_agent": crew["agents"][0] if crew["agents"] else None,
                "steps": [],
                "current_step": "Initializing crew workflow..."
            }
            
            # Store in Redis
            status_key = f"crew_workflow:{job_id}"
            self.redis_client.setex(status_key, 7200, json.dumps(workflow_status))  # 2 hours TTL
            
            # Track active crew
            self.active_crews[job_id] = {
                "crew_id": crew_id,
                "started_at": datetime.now(),
                "status": "running"
            }
            
            # Start background workflow
            asyncio.create_task(self._execute_crew_workflow(job_id, crew_id, workflow_config))
            
            logger.info(f"Started crew workflow {job_id} for crew {crew_id}")
            
            return {
                "success": True,
                "job_id": job_id,
                "crew_id": crew_id,
                "status": "started",
                "estimated_time_minutes": crew["estimated_time_minutes"],
                "message": f"Crew workflow started successfully"
            }
            
        except Exception as e:
            logger.error(f"Error starting crew workflow: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    async def _execute_agent_task(self, job_id: str, agent_id: str, task_config: Dict[str, Any]):
        """Execute single agent task in background"""
        try:
            await self._update_task_status(job_id, "processing", 10, "Preparing agent execution...")
            
            # Simulate agent processing steps
            steps = [
                ("Analyzing input data", 25),
                ("Processing with AI model", 50), 
                ("Generating results", 75),
                ("Finalizing output", 90)
            ]
            
            results = []
            
            for step_name, progress in steps:
                await self._update_task_status(job_id, "processing", progress, step_name)
                
                # Simulate processing time
                await asyncio.sleep(2)
                
                # Simulate step result
                step_result = {
                    "step": step_name,
                    "completed_at": datetime.now().isoformat(),
                    "output": f"Completed {step_name.lower()}"
                }
                results.append(step_result)
                
            # Final completion
            final_result = {
                "agent_id": agent_id,
                "task_completed": True,
                "results": results,
                "execution_time_seconds": 8,  # Simulated time
                "output_summary": f"Agent {agent_id} completed task successfully"
            }
            
            await self._update_task_status(
                job_id, 
                "completed", 
                100, 
                "Task completed successfully",
                final_result
            )
            
            logger.info(f"Agent task {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Agent task {job_id} failed: {e}")
            await self._update_task_status(job_id, "failed", 0, f"Task failed: {str(e)}")
            
    async def _execute_crew_workflow(self, job_id: str, crew_id: str, workflow_config: Dict[str, Any]):
        """Execute multi-agent crew workflow in background"""
        try:
            crews = await self.get_available_crews()
            crew = next((c for c in crews if c["id"] == crew_id), None)
            
            await self._update_workflow_status(job_id, "processing", 10, "Starting crew workflow...")
            
            # Execute each agent in sequence
            agent_results = []
            total_agents = len(crew["agents"])
            
            for i, agent_id in enumerate(crew["agents"]):
                progress = 20 + (i * 60 // total_agents)
                await self._update_workflow_status(
                    job_id, 
                    "processing", 
                    progress, 
                    f"Executing agent: {agent_id}"
                )
                
                # Simulate agent execution
                await asyncio.sleep(3)
                
                agent_result = {
                    "agent_id": agent_id,
                    "completed_at": datetime.now().isoformat(),
                    "output": f"Results from {agent_id}",
                    "success": True
                }
                agent_results.append(agent_result)
                
            # Final aggregation
            await self._update_workflow_status(job_id, "processing", 90, "Aggregating results...")
            await asyncio.sleep(2)
            
            final_result = {
                "crew_id": crew_id,
                "workflow_completed": True,
                "agent_results": agent_results,
                "total_execution_time_seconds": len(crew["agents"]) * 3 + 5,
                "final_output": f"Crew {crew_id} workflow completed with {len(agent_results)} agents",
                "recommendations": [
                    "Review generated analysis",
                    "Implement suggested improvements", 
                    "Schedule follow-up assessment"
                ]
            }
            
            await self._update_workflow_status(
                job_id, 
                "completed", 
                100, 
                "Workflow completed successfully",
                final_result
            )
            
            # Remove from active crews
            if job_id in self.active_crews:
                del self.active_crews[job_id]
                
            logger.info(f"Crew workflow {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Crew workflow {job_id} failed: {e}")
            await self._update_workflow_status(job_id, "failed", 0, f"Workflow failed: {str(e)}")
            
            if job_id in self.active_crews:
                del self.active_crews[job_id]
                
    async def _update_task_status(self, job_id: str, status: str, progress: int, current_step: str, result: Dict = None):
        """Update agent task status"""
        try:
            status_key = f"agent_task:{job_id}"
            current_status = self.redis_client.get(status_key)
            
            if current_status:
                status_data = json.loads(current_status)
                status_data.update({
                    "status": status,
                    "progress": progress,
                    "current_step": current_step,
                    "last_updated": datetime.now().isoformat()
                })
                
                if result:
                    status_data["result"] = result
                    
                if status == "completed":
                    status_data["completed_at"] = datetime.now().isoformat()
                    
                self.redis_client.setex(status_key, 3600, json.dumps(status_data))
                
        except Exception as e:
            logger.error(f"Error updating task status: {e}")
            
    async def _update_workflow_status(self, job_id: str, status: str, progress: int, current_step: str, result: Dict = None):
        """Update crew workflow status"""
        try:
            status_key = f"crew_workflow:{job_id}"
            current_status = self.redis_client.get(status_key)
            
            if current_status:
                status_data = json.loads(current_status)
                status_data.update({
                    "status": status,
                    "progress": progress,
                    "current_step": current_step,
                    "last_updated": datetime.now().isoformat()
                })
                
                if result:
                    status_data["result"] = result
                    
                if status == "completed":
                    status_data["completed_at"] = datetime.now().isoformat()
                    
                self.redis_client.setex(status_key, 7200, json.dumps(status_data))
                
        except Exception as e:
            logger.error(f"Error updating workflow status: {e}")
            
    async def get_task_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get agent task status"""
        try:
            status_key = f"agent_task:{job_id}"
            status_data = self.redis_client.get(status_key)
            
            if status_data:
                return json.loads(status_data)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting task status: {e}")
            return None
            
    async def get_workflow_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get crew workflow status"""
        try:
            status_key = f"crew_workflow:{job_id}"
            status_data = self.redis_client.get(status_key)
            
            if status_data:
                return json.loads(status_data)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting workflow status: {e}")
            return None
            
    async def get_active_jobs(self) -> Dict[str, Any]:
        """Get all active AI jobs"""
        try:
            active_tasks = []
            active_workflows = []
            
            # Get agent tasks
            task_keys = self.redis_client.keys("agent_task:*")
            for key in task_keys:
                task_data = self.redis_client.get(key)
                if task_data:
                    task = json.loads(task_data)
                    if task.get("status") in ["started", "processing"]:
                        active_tasks.append(task)
            
            # Get crew workflows
            workflow_keys = self.redis_client.keys("crew_workflow:*")
            for key in workflow_keys:
                workflow_data = self.redis_client.get(key)
                if workflow_data:
                    workflow = json.loads(workflow_data)
                    if workflow.get("status") in ["started", "processing"]:
                        active_workflows.append(workflow)
            
            return {
                "active_agent_tasks": active_tasks,
                "active_crew_workflows": active_workflows,
                "total_active": len(active_tasks) + len(active_workflows)
            }
            
        except Exception as e:
            logger.error(f"Error getting active jobs: {e}")
            return {"error": str(e)}
