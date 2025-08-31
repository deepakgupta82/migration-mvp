"""
Streaming wrappers for CrewAI components.
Provides StreamingCrewExecutor and StreamingAgent wrappers to hook into CrewAI execution.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Callable
from contextlib import asynccontextmanager

from crewai import Crew, Agent, Task, Process
from .crewai_streamer import crewai_streamer, CrewAIEventType
from .crew_interaction_logger import CrewInteractionLogger

logger = logging.getLogger(__name__)

class StreamingAgent:
    """
    Wrapper for CrewAI Agent with streaming capabilities.
    Provides real-time updates during agent execution.
    """

    def __init__(self, agent: Agent, stream_id: str, project_id: str, correlation_id: str):
        self.agent = agent
        self.stream_id = stream_id
        self.project_id = project_id
        self.correlation_id = correlation_id
        self.logger = CrewInteractionLogger(stream_id, project_id, correlation_id)
        self.execution_count = 0
        self.success_count = 0
        self.error_count = 0

    async def execute_task(self, task: Task) -> Any:
        """Execute a task with streaming updates"""
        task_name = getattr(task, 'description', 'Unknown Task')[:100]
        agent_name = getattr(self.agent, 'role', 'Unknown Agent')

        try:
            self.execution_count += 1

            # Log task start
            await self.logger.log_task_start(task_name, getattr(task, 'description', ''), agent_name)

            # Log agent start
            await self.logger.log_agent_start(
                agent_name,
                getattr(self.agent, 'role', ''),
                getattr(self.agent, 'goal', ''),
                getattr(self.agent, 'backstory', '')
            )

            # Execute the task (this would be the actual CrewAI execution)
            # For now, simulate execution
            start_time = datetime.now()

            # Simulate task execution with progress updates
            await self._simulate_task_execution(task)

            execution_time = (datetime.now() - start_time).total_seconds()

            # Log successful completion
            self.success_count += 1
            result = f"Task completed by {agent_name} in {execution_time:.2f}s"

            await self.logger.log_task_complete(task_name, True, result)
            await self.logger.log_agent_complete(agent_name, True, result)

            return result

        except Exception as e:
            self.error_count += 1
            error_msg = f"Task execution failed: {str(e)}"

            await self.logger.log_task_complete(task_name, False, error=error_msg)
            await self.logger.log_agent_complete(agent_name, False, error=error_msg)

            raise

    async def _simulate_task_execution(self, task: Task):
        """Simulate task execution with progress updates"""
        steps = [
            "Analyzing task requirements",
            "Gathering necessary information",
            "Processing data",
            "Generating response",
            "Finalizing output"
        ]

        for i, step in enumerate(steps):
            progress = (i + 1) / len(steps) * 100
            await self.logger.log_progress_update(
                progress,
                step,
                task_step=i+1,
                total_steps=len(steps)
            )

            # Simulate processing time
            await asyncio.sleep(0.5)

    def get_metrics(self) -> Dict[str, Any]:
        """Get execution metrics for this agent"""
        return {
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0,
            "agent_name": getattr(self.agent, 'role', 'Unknown'),
            "agent_goal": getattr(self.agent, 'goal', '')
        }

    # Delegate other attributes to the wrapped agent
    def __getattr__(self, name):
        return getattr(self.agent, name)

class StreamingCrewExecutor:
    """
    Wrapper for CrewAI Crew with streaming capabilities.
    Provides real-time updates during crew execution.
    """

    def __init__(self, crew: Crew, project_id: str, correlation_id: str):
        self.crew = crew
        self.project_id = project_id
        self.correlation_id = correlation_id
        self.stream_id = None
        self.logger = None
        self.streaming_agents = []
        self.execution_start_time = None
        self.is_executing = False

        # Setup streaming agents
        self._setup_streaming_agents()

    def _setup_streaming_agents(self):
        """Setup streaming wrappers for all agents in the crew"""
        self.streaming_agents = []
        for agent in self.crew.agents:
            # We'll set stream_id later when execution starts
            streaming_agent = StreamingAgent(agent, "", self.project_id, self.correlation_id)
            self.streaming_agents.append(streaming_agent)

    async def execute(self, inputs: Optional[Dict[str, Any]] = None) -> Any:
        """Execute the crew with streaming updates"""
        if self.is_executing:
            raise RuntimeError("Crew is already executing")

        try:
            self.is_executing = True
            self.execution_start_time = datetime.now()

            # Start streaming session
            crew_id = f"crew_{self.execution_start_time.strftime('%Y%m%d_%H%M%S')}"
            self.stream_id = await crewai_streamer.start_stream(
                self.project_id,
                self.correlation_id,
                crew_id
            )

            # Update streaming agents with stream_id
            for streaming_agent in self.streaming_agents:
                streaming_agent.stream_id = self.stream_id
                streaming_agent.logger = CrewInteractionLogger(
                    self.stream_id, self.project_id, self.correlation_id
                )

            # Initialize logger
            self.logger = CrewInteractionLogger(
                self.stream_id, self.project_id, self.correlation_id
            )

            # Log crew start
            await self.logger.log_crew_start(
                crew_id,
                len(self.crew.agents),
                len(self.crew.tasks)
            )

            # Execute crew tasks
            result = await self._execute_crew_workflow(inputs)

            # Log successful completion
            execution_time = (datetime.now() - self.execution_start_time).total_seconds()
            await self.logger.log_crew_complete(crew_id, True, result)

            # End streaming session
            await crewai_streamer.end_stream(self.stream_id, True)

            return result

        except Exception as e:
            # Log error
            if self.logger:
                crew_id = f"crew_{self.execution_start_time.strftime('%Y%m%d_%H%M%S')}" if self.execution_start_time else "unknown_crew"
                await self.logger.log_crew_complete(crew_id, False, error=str(e))

            # End streaming session with error
            if self.stream_id:
                await crewai_streamer.end_stream(self.stream_id, False, str(e))

            raise
        finally:
            self.is_executing = False

    async def _execute_crew_workflow(self, inputs: Optional[Dict[str, Any]] = None) -> Any:
        """Execute the crew workflow with streaming"""
        results = []

        # Execute tasks based on process type
        if self.crew.process == Process.sequential:
            results = await self._execute_sequential()
        elif self.crew.process == Process.hierarchical:
            results = await self._execute_hierarchical()
        else:
            # Default to sequential
            results = await self._execute_sequential()

        # Combine results
        if len(results) == 1:
            return results[0]
        else:
            return results

    async def _execute_sequential(self) -> List[Any]:
        """Execute tasks sequentially"""
        results = []

        for i, task in enumerate(self.crew.tasks):
            # Find appropriate agent for this task
            agent = self._find_agent_for_task(task, i)

            if agent:
                # Execute task with streaming
                result = await agent.execute_task(task)
                results.append(result)

                # Update overall progress
                progress = (i + 1) / len(self.crew.tasks) * 100
                await self.logger.log_progress_update(
                    progress,
                    f"Completed task {i+1}/{len(self.crew.tasks)}",
                    current_task=i+1,
                    total_tasks=len(self.crew.tasks)
                )
            else:
                logger.warning(f"No suitable agent found for task: {getattr(task, 'description', 'Unknown')[:100]}")

        return results

    async def _execute_hierarchical(self) -> List[Any]:
        """Execute tasks hierarchically (simplified implementation)"""
        # For now, use sequential execution
        # In a full implementation, this would handle manager-agent relationships
        return await self._execute_sequential()

    def _find_agent_for_task(self, task: Task, task_index: int) -> Optional[StreamingAgent]:
        """Find the most appropriate agent for a task"""
        # Simple assignment based on task index
        if task_index < len(self.streaming_agents):
            return self.streaming_agents[task_index]

        # Fallback to first agent
        return self.streaming_agents[0] if self.streaming_agents else None

    def get_execution_status(self) -> Dict[str, Any]:
        """Get current execution status"""
        if not self.stream_id:
            return {"status": "not_started"}

        stream_info = crewai_streamer.get_stream_info(self.stream_id)
        if not stream_info:
            return {"status": "unknown"}

        return {
            "status": stream_info["status"],
            "stream_id": self.stream_id,
            "started_at": stream_info["started_at"].isoformat(),
            "event_count": stream_info["event_count"],
            "is_executing": self.is_executing
        }

    def get_agent_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics for all agents"""
        return [agent.get_metrics() for agent in self.streaming_agents]

    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get overall execution metrics"""
        if not self.execution_start_time:
            return {"status": "not_started"}

        execution_time = (datetime.now() - self.execution_start_time).total_seconds() if self.is_executing else 0

        return {
            "total_agents": len(self.streaming_agents),
            "total_tasks": len(self.crew.tasks),
            "execution_time_seconds": execution_time,
            "is_executing": self.is_executing,
            "process_type": self.crew.process.value if hasattr(self.crew.process, 'value') else str(self.crew.process),
            "agent_metrics": self.get_agent_metrics()
        }

    # Delegate other attributes to the wrapped crew
    def __getattr__(self, name):
        return getattr(self.crew, name)

class StreamingCrewManager:
    """
    Manager for creating and executing streaming crews.
    Provides a high-level interface for crew execution with streaming.
    """

    def __init__(self):
        self.active_crews: Dict[str, StreamingCrewExecutor] = {}
        self.logger = logger

    async def create_streaming_crew(
        self,
        agents: List[Agent],
        tasks: List[Task],
        process: Process = Process.sequential,
        project_id: str = "default",
        correlation_id: str = "",
        **crew_kwargs
    ) -> StreamingCrewExecutor:
        """Create a streaming crew executor"""

        # Create the base crew
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=process,
            **crew_kwargs
        )

        # Wrap with streaming executor
        streaming_executor = StreamingCrewExecutor(crew, project_id, correlation_id)

        # Generate crew ID
        crew_id = f"crew_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.active_crews[crew_id] = streaming_executor

        self.logger.info(f"Created streaming crew: {crew_id}")
        return streaming_executor

    async def execute_crew(
        self,
        agents: List[Agent],
        tasks: List[Task],
        process: Process = Process.sequential,
        project_id: str = "default",
        correlation_id: str = "",
        inputs: Optional[Dict[str, Any]] = None,
        **crew_kwargs
    ) -> Any:
        """Create and execute a streaming crew"""

        streaming_executor = await self.create_streaming_crew(
            agents, tasks, process, project_id, correlation_id, **crew_kwargs
        )

        # Execute the crew
        result = await streaming_executor.execute(inputs)

        return result

    def get_active_crews(self) -> List[Dict[str, Any]]:
        """Get information about active crews"""
        return [
            {
                "crew_id": crew_id,
                "status": crew.get_execution_status(),
                "metrics": crew.get_execution_metrics()
            }
            for crew_id, crew in self.active_crews.items()
        ]

    async def cleanup_inactive_crews(self):
        """Clean up crews that are no longer executing"""
        inactive_crews = []

        for crew_id, crew in self.active_crews.items():
            if not crew.is_executing:
                # Check if stream is still active
                status = crew.get_execution_status()
                if status.get("status") in ["completed", "failed"]:
                    inactive_crews.append(crew_id)

        for crew_id in inactive_crews:
            del self.active_crews[crew_id]
            self.logger.debug(f"Cleaned up inactive crew: {crew_id}")

        return len(inactive_crews)

# Global manager instance
streaming_crew_manager = StreamingCrewManager()