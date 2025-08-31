"""
Streaming Tool wrapper for monitoring CrewAI tool executions.
Provides real-time updates and detailed logging for tool operations.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Type
from functools import wraps
import inspect

from .crewai_streamer import crewai_streamer, CrewAIEventType
from .crew_interaction_logger import CrewInteractionLogger

logger = logging.getLogger(__name__)

class StreamingTool:
    """
    Wrapper for CrewAI tools with streaming capabilities.
    Monitors execution and provides real-time updates.
    """

    def __init__(self, tool: Any, stream_id: str, project_id: str, correlation_id: str,
                 agent_name: str = "Unknown Agent"):
        self.tool = tool
        self.stream_id = stream_id
        self.project_id = project_id
        self.correlation_id = correlation_id
        self.agent_name = agent_name
        self.logger = CrewInteractionLogger(stream_id, project_id, correlation_id)

        # Execution metrics
        self.execution_count = 0
        self.success_count = 0
        self.error_count = 0
        self.total_execution_time = 0.0
        self.last_execution_time = 0.0

        # Tool metadata
        self.tool_name = getattr(tool, '__class__', {}).get('__name__', 'UnknownTool')
        self.tool_description = getattr(tool, 'description', 'No description available')

    async def execute(self, *args, **kwargs) -> Any:
        """Execute the tool with streaming updates"""
        self.execution_count += 1
        execution_id = f"{self.agent_name}_{self.tool_name}_{datetime.now().isoformat()}"

        start_time = time.time()

        try:
            # Log tool execution start
            await self.logger.log_tool_call(
                self.agent_name,
                self.tool_name,
                'execute',
                {
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200],
                    'execution_id': execution_id
                }
            )

            # Execute the tool
            if asyncio.iscoroutinefunction(getattr(self.tool, 'run', None)):
                # Async tool
                result = await self.tool.run(*args, **kwargs)
            elif hasattr(self.tool, 'run'):
                # Sync tool - run in thread pool
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.tool.run, *args, **kwargs
                )
            elif callable(self.tool):
                # Direct callable
                if inspect.iscoroutinefunction(self.tool):
                    result = await self.tool(*args, **kwargs)
                else:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, self.tool, *args, **kwargs
                    )
            else:
                raise ValueError(f"Tool {self.tool_name} is not callable")

            # Calculate execution time
            execution_time = time.time() - start_time
            self.last_execution_time = execution_time
            self.total_execution_time += execution_time

            # Log successful completion
            self.success_count += 1
            await self.logger.log_tool_result(
                self.agent_name,
                self.tool_name,
                execution_id,
                True,
                result,
                execution_time_seconds=execution_time
            )

            return result

        except Exception as e:
            # Calculate execution time for failed execution
            execution_time = time.time() - start_time
            self.last_execution_time = execution_time
            self.total_execution_time += execution_time

            # Log error
            self.error_count += 1
            error_msg = f"{type(e).__name__}: {str(e)}"

            await self.logger.log_tool_result(
                self.agent_name,
                self.tool_name,
                execution_id,
                False,
                error=error_msg,
                execution_time_seconds=execution_time
            )

            raise

    def get_metrics(self) -> Dict[str, Any]:
        """Get execution metrics for this tool"""
        avg_execution_time = (self.total_execution_time / self.execution_count) if self.execution_count > 0 else 0

        return {
            "tool_name": self.tool_name,
            "tool_description": self.tool_description,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0,
            "total_execution_time": self.total_execution_time,
            "average_execution_time": avg_execution_time,
            "last_execution_time": self.last_execution_time
        }

    # Delegate other attributes to the wrapped tool
    def __getattr__(self, name):
        return getattr(self.tool, name)

class StreamingToolRegistry:
    """
    Registry for managing streaming tool wrappers.
    Provides centralized tool monitoring and metrics.
    """

    def __init__(self):
        self.tools: Dict[str, StreamingTool] = {}
        self.logger = logger

    def register_tool(self, tool: Any, stream_id: str, project_id: str,
                     correlation_id: str, agent_name: str = "Unknown Agent") -> StreamingTool:
        """Register a tool and return its streaming wrapper"""
        tool_name = getattr(tool, '__class__', {}).get('__name__', 'UnknownTool')

        if tool_name in self.tools:
            self.logger.warning(f"Tool {tool_name} already registered, returning existing wrapper")
            return self.tools[tool_name]

        streaming_tool = StreamingTool(
            tool, stream_id, project_id, correlation_id, agent_name
        )

        self.tools[tool_name] = streaming_tool
        self.logger.info(f"Registered streaming tool: {tool_name}")

        return streaming_tool

    def get_tool(self, tool_name: str) -> Optional[StreamingTool]:
        """Get a registered streaming tool"""
        return self.tools.get(tool_name)

    def get_all_tools(self) -> List[StreamingTool]:
        """Get all registered streaming tools"""
        return list(self.tools.values())

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary for all tools"""
        all_metrics = [tool.get_metrics() for tool in self.tools.values()]

        if not all_metrics:
            return {"total_tools": 0}

        total_executions = sum(m["execution_count"] for m in all_metrics)
        total_successes = sum(m["success_count"] for m in all_metrics)
        total_errors = sum(m["error_count"] for m in all_metrics)
        total_time = sum(m["total_execution_time"] for m in all_metrics)

        return {
            "total_tools": len(all_metrics),
            "total_executions": total_executions,
            "total_successes": total_successes,
            "total_errors": total_errors,
            "overall_success_rate": (total_successes / total_executions * 100) if total_executions > 0 else 0,
            "total_execution_time": total_time,
            "average_execution_time": (total_time / total_executions) if total_executions > 0 else 0,
            "tool_metrics": all_metrics
        }

    def unregister_tool(self, tool_name: str) -> bool:
        """Unregister a tool"""
        if tool_name in self.tools:
            del self.tools[tool_name]
            self.logger.info(f"Unregistered tool: {tool_name}")
            return True
        return False

    def clear_all_tools(self):
        """Clear all registered tools"""
        count = len(self.tools)
        self.tools.clear()
        self.logger.info(f"Cleared {count} registered tools")

class ToolExecutionMonitor:
    """
    Advanced tool execution monitor with performance tracking and anomaly detection.
    """

    def __init__(self, registry: StreamingToolRegistry):
        self.registry = registry
        self.execution_history: List[Dict[str, Any]] = []
        self.performance_thresholds = {
            "max_execution_time": 30.0,  # seconds
            "min_success_rate": 80.0,    # percentage
            "max_error_rate": 20.0       # percentage
        }
        self.logger = logger

    async def monitor_execution(self, tool_name: str, execution_time: float,
                               success: bool) -> Dict[str, Any]:
        """Monitor a tool execution and detect anomalies"""
        execution_record = {
            "tool_name": tool_name,
            "execution_time": execution_time,
            "success": success,
            "timestamp": datetime.now(),
            "anomalies": []
        }

        # Check for performance anomalies
        if execution_time > self.performance_thresholds["max_execution_time"]:
            execution_record["anomalies"].append({
                "type": "slow_execution",
                "message": f"Execution time {execution_time:.2f}s exceeds threshold {self.performance_thresholds['max_execution_time']}s",
                "severity": "warning"
            })

        # Get tool metrics for success rate analysis
        tool = self.registry.get_tool(tool_name)
        if tool:
            metrics = tool.get_metrics()
            success_rate = metrics["success_rate"]

            if success_rate < self.performance_thresholds["min_success_rate"]:
                execution_record["anomalies"].append({
                    "type": "low_success_rate",
                    "message": f"Success rate {success_rate:.1f}% below threshold {self.performance_thresholds['min_success_rate']}%",
                    "severity": "error"
                })

        # Store execution record
        self.execution_history.append(execution_record)

        # Keep only recent history
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-1000:]

        # Log anomalies
        for anomaly in execution_record["anomalies"]:
            if anomaly["severity"] == "error":
                self.logger.error(f"Tool anomaly detected: {anomaly['message']}")
            elif anomaly["severity"] == "warning":
                self.logger.warning(f"Tool anomaly detected: {anomaly['message']}")

        return execution_record

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate a performance report for all tools"""
        report = {
            "timestamp": datetime.now(),
            "total_executions": len(self.execution_history),
            "anomaly_summary": {},
            "tool_performance": {},
            "recommendations": []
        }

        # Analyze anomalies
        anomaly_counts = {}
        for record in self.execution_history:
            for anomaly in record["anomalies"]:
                anomaly_type = anomaly["type"]
                if anomaly_type not in anomaly_counts:
                    anomaly_counts[anomaly_type] = 0
                anomaly_counts[anomaly_type] += 1

        report["anomaly_summary"] = anomaly_counts

        # Analyze tool performance
        for tool in self.registry.get_all_tools():
            metrics = tool.get_metrics()
            report["tool_performance"][tool.tool_name] = metrics

            # Generate recommendations
            if metrics["success_rate"] < 70:
                report["recommendations"].append(
                    f"Investigate low success rate for {tool.tool_name} ({metrics['success_rate']:.1f}%)"
                )

            if metrics["average_execution_time"] > 10:
                report["recommendations"].append(
                    f"Optimize performance for {tool.tool_name} (avg {metrics['average_execution_time']:.2f}s)"
                )

        return report

    def update_thresholds(self, thresholds: Dict[str, float]):
        """Update performance thresholds"""
        self.performance_thresholds.update(thresholds)
        self.logger.info(f"Updated performance thresholds: {thresholds}")

# Global instances
streaming_tool_registry = StreamingToolRegistry()
tool_execution_monitor = ToolExecutionMonitor(streaming_tool_registry)

def create_streaming_tool_wrapper(tool_class: Type) -> Type:
    """
    Decorator to create a streaming wrapper for a tool class.
    Automatically wraps tool execution with streaming capabilities.
    """

    class StreamingToolWrapper(tool_class):
        def __init__(self, *args, stream_id: str = "", project_id: str = "",
                     correlation_id: str = "", agent_name: str = "Unknown Agent", **kwargs):
            super().__init__(*args, **kwargs)

            if stream_id:
                self._streaming_tool = StreamingTool(
                    self, stream_id, project_id, correlation_id, agent_name
                )
            else:
                self._streaming_tool = None

        def run(self, *args, **kwargs):
            if self._streaming_tool:
                # Use asyncio to run the async execute method
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is already running, we need to handle this differently
                        # For now, fall back to direct execution
                        return super().run(*args, **kwargs)
                    else:
                        return loop.run_until_complete(self._streaming_tool.execute(*args, **kwargs))
                except RuntimeError:
                    # No event loop, fall back to direct execution
                    return super().run(*args, **kwargs)
            else:
                return super().run(*args, **kwargs)

        async def arun(self, *args, **kwargs):
            if self._streaming_tool:
                return await self._streaming_tool.execute(*args, **kwargs)
            else:
                # Call the parent's run method (assuming it's sync)
                return super().run(*args, **kwargs)

    return StreamingToolWrapper