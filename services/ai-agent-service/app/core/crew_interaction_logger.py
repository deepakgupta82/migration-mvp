"""
Enhanced CrewInteractionLogger for detailed CrewAI event capture and streaming.
Captures agent switches, tool executions, reasoning steps, and other granular activities.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, List
import json
import traceback

try:
    from langchain.callbacks.base import BaseCallbackHandler
except ImportError:
    # Fallback for environments without langchain
    class BaseCallbackHandler:
        pass

from .crewai_streamer import crewai_streamer, CrewAIEventType

logger = logging.getLogger(__name__)

class CrewInteractionLogger(BaseCallbackHandler):
    """
    Enhanced logger for capturing detailed CrewAI interactions.
    Integrates with CrewAIStreamer for real-time event processing and broadcasting.
    """

    def __init__(self, stream_id: str, project_id: str, correlation_id: str):
        super().__init__()
        self.stream_id = stream_id
        self.project_id = project_id
        self.correlation_id = correlation_id
        self.current_agent = None
        self.current_task = None
        self.agent_start_times: Dict[str, datetime] = {}
        self.tool_execution_times: Dict[str, datetime] = {}
        self.reasoning_steps: List[Dict[str, Any]] = []
        self.logger = logger

        # Register with streamer for event handling
        self._setup_event_handlers()

    def _setup_event_handlers(self):
        """Setup event handlers for processing streamed events"""
        # Optional: Add custom processing for specific events
        pass

    async def log_crew_start(self, crew_id: str, agent_count: int, task_count: int):
        """Log crew initialization"""
        try:
            event = crewai_streamer._create_event(
                CrewAIEventType.CREW_START,
                self.project_id,
                self.correlation_id,
                crew_id=crew_id,
                data={
                    "agent_count": agent_count,
                    "task_count": task_count,
                    "stream_id": self.stream_id
                }
            )
            await crewai_streamer.emit_event(event)
        except Exception as e:
            self.logger.error(f"Error logging crew start: {e}")

    async def log_crew_complete(self, crew_id: str, success: bool, result: Any = None, error: Optional[str] = None):
        """Log crew completion"""
        try:
            data = {
                "success": success,
                "stream_id": self.stream_id
            }

            if result is not None:
                data["result_summary"] = str(result)[:500]
            if error:
                data["error"] = error

            event_type = CrewAIEventType.CREW_COMPLETE if success else CrewAIEventType.CREW_ERROR

            event = crewai_streamer._create_event(
                event_type,
                self.project_id,
                self.correlation_id,
                crew_id=crew_id,
                data=data
            )
            await crewai_streamer.emit_event(event)
        except Exception as e:
            self.logger.error(f"Error logging crew completion: {e}")

    async def log_agent_start(self, agent_name: str, role: str, goal: str, backstory: Optional[str] = None):
        """Log agent initialization"""
        try:
            self.current_agent = agent_name
            self.agent_start_times[agent_name] = datetime.now()

            await crewai_streamer.emit_agent_event(
                self.stream_id,
                CrewAIEventType.AGENT_START,
                agent_name,
                role=role,
                goal=goal,
                backstory=backstory
            )
        except Exception as e:
            self.logger.error(f"Error logging agent start: {e}")

    async def log_agent_complete(self, agent_name: str, success: bool, output: Any = None, error: Optional[str] = None):
        """Log agent completion"""
        try:
            if agent_name in self.agent_start_times:
                start_time = self.agent_start_times[agent_name]
                duration = (datetime.now() - start_time).total_seconds()
            else:
                duration = 0

            data = {
                "duration_seconds": duration,
                "success": success
            }

            if output is not None:
                data["output_summary"] = str(output)[:500]
            if error:
                data["error"] = error

            event_type = CrewAIEventType.AGENT_COMPLETE if success else CrewAIEventType.AGENT_ERROR

            await crewai_streamer.emit_agent_event(
                self.stream_id,
                event_type,
                agent_name,
                **data
            )

            # Clear current agent if this was the active one
            if self.current_agent == agent_name:
                self.current_agent = None

        except Exception as e:
            self.logger.error(f"Error logging agent completion: {e}")

    async def log_agent_switch(self, from_agent: Optional[str], to_agent: str):
        """Log agent context switching"""
        try:
            await crewai_streamer.emit_agent_event(
                self.stream_id,
                CrewAIEventType.AGENT_SWITCH,
                to_agent,
                from_agent=from_agent,
                to_agent=to_agent
            )
        except Exception as e:
            self.logger.error(f"Error logging agent switch: {e}")

    async def log_agent_reasoning(self, agent_name: str, thought: str, action: Optional[str] = None):
        """Log agent reasoning steps"""
        try:
            reasoning_data = {
                "thought": thought,
                "action": action,
                "step_number": len(self.reasoning_steps) + 1
            }

            # Store reasoning step
            self.reasoning_steps.append({
                "agent": agent_name,
                "timestamp": datetime.now(),
                **reasoning_data
            })

            await crewai_streamer.emit_agent_event(
                self.stream_id,
                CrewAIEventType.AGENT_REASONING,
                agent_name,
                **reasoning_data
            )
        except Exception as e:
            self.logger.error(f"Error logging agent reasoning: {e}")

    async def log_tool_call(self, agent_name: str, tool_name: str, function_name: str, params: Dict[str, Any]):
        """Log tool execution start"""
        try:
            execution_id = f"{agent_name}_{tool_name}_{datetime.now().isoformat()}"
            self.tool_execution_times[execution_id] = datetime.now()

            await crewai_streamer.emit_tool_event(
                self.stream_id,
                CrewAIEventType.TOOL_EXECUTION_START,
                agent_name,
                tool_name,
                execution_id=execution_id,
                function_name=function_name,
                params=params
            )
        except Exception as e:
            self.logger.error(f"Error logging tool call: {e}")

    async def log_tool_result(self, agent_name: str, tool_name: str, execution_id: str,
                             success: bool, result: Any = None, error: Optional[str] = None):
        """Log tool execution completion"""
        try:
            duration = 0
            if execution_id in self.tool_execution_times:
                start_time = self.tool_execution_times[execution_id]
                duration = (datetime.now() - start_time).total_seconds()
                del self.tool_execution_times[execution_id]

            data = {
                "execution_id": execution_id,
                "duration_seconds": duration,
                "success": success
            }

            if result is not None:
                data["result_summary"] = str(result)[:500]
            if error:
                data["error"] = error

            event_type = CrewAIEventType.TOOL_EXECUTION_COMPLETE if success else CrewAIEventType.TOOL_EXECUTION_ERROR

            await crewai_streamer.emit_tool_event(
                self.stream_id,
                event_type,
                agent_name,
                tool_name,
                **data
            )
        except Exception as e:
            self.logger.error(f"Error logging tool result: {e}")

    async def log_task_start(self, task_name: str, description: str, assigned_agent: Optional[str] = None):
        """Log task initialization"""
        try:
            self.current_task = task_name

            event = crewai_streamer._create_event(
                CrewAIEventType.TASK_START,
                self.project_id,
                self.correlation_id,
                task_name=task_name,
                data={
                    "description": description,
                    "assigned_agent": assigned_agent
                }
            )
            await crewai_streamer.emit_event(event)
        except Exception as e:
            self.logger.error(f"Error logging task start: {e}")

    async def log_task_complete(self, task_name: str, success: bool, output: Any = None, error: Optional[str] = None):
        """Log task completion"""
        try:
            data = {"success": success}

            if output is not None:
                data["output_summary"] = str(output)[:500]
            if error:
                data["error"] = error

            event_type = CrewAIEventType.TASK_COMPLETE if success else CrewAIEventType.TASK_ERROR

            event = crewai_streamer._create_event(
                event_type,
                self.project_id,
                self.correlation_id,
                task_name=task_name,
                data=data
            )
            await crewai_streamer.emit_event(event)

            # Clear current task if this was the active one
            if self.current_task == task_name:
                self.current_task = None

        except Exception as e:
            self.logger.error(f"Error logging task completion: {e}")

    async def log_progress_update(self, progress_percentage: float, current_step: str, **kwargs):
        """Log progress updates"""
        try:
            await crewai_streamer.emit_progress_event(
                self.stream_id,
                progress_percentage,
                current_step,
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"Error logging progress update: {e}")

    # CrewAI Callback Handler Methods

    def on_agent_start(self, agent, **kwargs):
        """Called when an agent starts - CrewAI callback"""
        try:
            agent_name = getattr(agent, 'role', 'Unknown Agent')
            goal = getattr(agent, 'goal', '')
            backstory = getattr(agent, 'backstory', '')

            # Run async logging in background
            asyncio.create_task(self.log_agent_start(agent_name, agent_name, goal, backstory))
        except Exception as e:
            self.logger.error(f"Error in on_agent_start callback: {e}")

    def on_agent_end(self, agent, **kwargs):
        """Called when an agent ends - CrewAI callback"""
        try:
            agent_name = getattr(agent, 'role', 'Unknown Agent')
            # Note: CrewAI doesn't always provide success/failure info here
            asyncio.create_task(self.log_agent_complete(agent_name, True))
        except Exception as e:
            self.logger.error(f"Error in on_agent_end callback: {e}")

    def on_tool_start(self, tool, input_str, **kwargs):
        """Called when a tool starts - CrewAI callback"""
        try:
            tool_name = getattr(tool, '__class__', {}).get('__name__', 'Unknown Tool')
            agent_name = getattr(self.current_agent, 'role', 'Unknown Agent') if self.current_agent else 'Unknown Agent'

            params = {'input': input_str} if input_str else {}

            asyncio.create_task(self.log_tool_call(agent_name, tool_name, 'execute', params))
        except Exception as e:
            self.logger.error(f"Error in on_tool_start callback: {e}")

    def on_tool_end(self, output, **kwargs):
        """Called when a tool ends - CrewAI callback"""
        try:
            # This is a simplified version - in practice, you'd need to track tool execution IDs
            agent_name = getattr(self.current_agent, 'role', 'Unknown Agent') if self.current_agent else 'Unknown Agent'
            tool_name = 'Unknown Tool'  # Would need to be tracked from on_tool_start

            execution_id = f"{agent_name}_{tool_name}_{datetime.now().isoformat()}"
            asyncio.create_task(self.log_tool_result(agent_name, tool_name, execution_id, True, output))
        except Exception as e:
            self.logger.error(f"Error in on_tool_end callback: {e}")

    def on_tool_error(self, error, **kwargs):
        """Called when a tool errors - CrewAI callback"""
        try:
            agent_name = getattr(self.current_agent, 'role', 'Unknown Agent') if self.current_agent else 'Unknown Agent'
            tool_name = 'Unknown Tool'  # Would need to be tracked

            execution_id = f"{agent_name}_{tool_name}_{datetime.now().isoformat()}"
            asyncio.create_task(self.log_tool_result(agent_name, tool_name, execution_id, False, error=str(error)))
        except Exception as e:
            self.logger.error(f"Error in on_tool_error callback: {e}")

    def on_text(self, text, **kwargs):
        """Called when there's text output - CrewAI callback"""
        try:
            if self.current_agent and text:
                agent_name = getattr(self.current_agent, 'role', 'Unknown Agent')

                # Check for reasoning patterns
                if any(keyword in text.lower() for keyword in ['thought:', 'reasoning:', 'considering:', 'action:']):
                    asyncio.create_task(self.log_agent_reasoning(agent_name, text, 'processing'))
        except Exception as e:
            self.logger.error(f"Error in on_text callback: {e}")

    def on_chain_start(self, chain, inputs, **kwargs):
        """Called when a chain starts - CrewAI callback"""
        try:
            if hasattr(chain, 'get_name'):
                chain_name = chain.get_name()
            else:
                chain_name = str(chain)

            self.logger.debug(f"Chain started: {chain_name}")
        except Exception as e:
            self.logger.error(f"Error in on_chain_start callback: {e}")

    def on_chain_end(self, outputs, **kwargs):
        """Called when a chain ends - CrewAI callback"""
        try:
            self.logger.debug("Chain completed")
        except Exception as e:
            self.logger.error(f"Error in on_chain_end callback: {e}")

    def on_chain_error(self, error, **kwargs):
        """Called when a chain errors - CrewAI callback"""
        try:
            self.logger.error(f"Chain error: {error}")
        except Exception as e:
            self.logger.error(f"Error in on_chain_error callback: {e}")

    # Utility methods

    def get_reasoning_history(self, agent_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get reasoning history for an agent or all agents"""
        if agent_name:
            return [step for step in self.reasoning_steps if step["agent"] == agent_name]
        return self.reasoning_steps.copy()

    def get_agent_metrics(self) -> Dict[str, Any]:
        """Get metrics about agent performance"""
        metrics = {
            "total_agents": len(self.agent_start_times),
            "total_reasoning_steps": len(self.reasoning_steps),
            "total_tool_executions": len(self.tool_execution_times)
        }

        # Calculate average durations if available
        agent_durations = []
        for agent, start_time in self.agent_start_times.items():
            # This is simplified - in practice you'd track end times too
            pass

        return metrics

    def set_current_agent(self, agent):
        """Set the current agent for context"""
        self.current_agent = agent

    def set_current_task(self, task):
        """Set the current task for context"""
        self.current_task = task