"""
Error Monitoring and Performance Optimization for CrewAI Streaming
Provides centralized error handling, monitoring, and performance optimizations.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
import traceback
import functools

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    """Error categories for classification"""
    NETWORK = "network"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    PROCESSING = "processing"
    CONFIGURATION = "configuration"
    RESOURCE = "resource"
    UNKNOWN = "unknown"

@dataclass
class ErrorRecord:
    """Represents an error record for monitoring"""
    error_id: str
    timestamp: datetime
    component: str
    error_type: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    resolved: bool = False
    resolution_time: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert error record to dictionary"""
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp.isoformat(),
            "component": self.component,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "category": self.category.value,
            "stack_trace": self.stack_trace,
            "context": self.context,
            "retry_count": self.retry_count,
            "resolved": self.resolved,
            "resolution_time": self.resolution_time.isoformat() if self.resolution_time else None
        }

@dataclass
class PerformanceMetric:
    """Represents a performance metric"""
    metric_id: str
    component: str
    operation: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def complete(self, success: bool = True, **kwargs):
        """Mark the metric as completed"""
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        self.success = success
        self.metadata.update(kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary"""
        return {
            "metric_id": self.metric_id,
            "component": self.component,
            "operation": self.operation,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "metadata": self.metadata
        }

class CircuitBreaker:
    """Circuit breaker pattern implementation"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                else:
                    raise Exception("Circuit breaker is OPEN")

            try:
                result = await func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as e:
                self._on_failure()
                raise e

        return wrapper

    def _on_success(self):
        """Handle successful operation"""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("Circuit breaker reset to CLOSED state")

    def _on_failure(self):
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit"""
        if self.last_failure_time is None:
            return True

        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

class ErrorMonitor:
    """Centralized error monitoring and handling"""

    def __init__(self):
        self.errors: List[ErrorRecord] = []
        self.max_errors = 1000
        self.error_handlers: Dict[ErrorCategory, List[Callable]] = {}

        # Initialize error handler lists
        for category in ErrorCategory:
            self.error_handlers[category] = []

    def register_error_handler(self, category: ErrorCategory, handler: Callable):
        """Register an error handler for a specific category"""
        self.error_handlers[category].append(handler)
        logger.debug(f"Registered error handler for category: {category.value}")

    def unregister_error_handler(self, category: ErrorCategory, handler: Callable):
        """Unregister an error handler"""
        if handler in self.error_handlers[category]:
            self.error_handlers[category].remove(handler)

    async def record_error(self, component: str, error: Exception,
                          severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                          category: ErrorCategory = ErrorCategory.UNKNOWN,
                          context: Optional[Dict[str, Any]] = None) -> str:
        """Record an error for monitoring"""
        error_id = f"err_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        error_record = ErrorRecord(
            error_id=error_id,
            timestamp=datetime.now(),
            component=component,
            error_type=type(error).__name__,
            error_message=str(error),
            severity=severity,
            category=category,
            stack_trace=traceback.format_exc(),
            context=context or {}
        )

        # Add to error list
        self.errors.append(error_record)
        if len(self.errors) > self.max_errors:
            self.errors.pop(0)

        # Log the error
        log_message = f"[{severity.value.upper()}] {component}: {error}"
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message)
        elif severity == ErrorSeverity.HIGH:
            logger.error(log_message)
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        # Call error handlers
        for handler in self.error_handlers[category]:
            try:
                await handler(error_record)
            except Exception as e:
                logger.error(f"Error in error handler: {e}")

        return error_id

    def resolve_error(self, error_id: str):
        """Mark an error as resolved"""
        for error in self.errors:
            if error.error_id == error_id:
                error.resolved = True
                error.resolution_time = datetime.now()
                logger.info(f"Error {error_id} marked as resolved")
                break

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        total_errors = len(self.errors)
        unresolved_errors = len([e for e in self.errors if not e.resolved])

        # Count by severity
        severity_counts = {}
        for severity in ErrorSeverity:
            severity_counts[severity.value] = len([
                e for e in self.errors if e.severity == severity
            ])

        # Count by category
        category_counts = {}
        for category in ErrorCategory:
            category_counts[category.value] = len([
                e for e in self.errors if e.category == category
            ])

        return {
            "total_errors": total_errors,
            "unresolved_errors": unresolved_errors,
            "severity_counts": severity_counts,
            "category_counts": category_counts,
            "recent_errors": [e.to_dict() for e in self.errors[-10:]]  # Last 10 errors
        }

class PerformanceMonitor:
    """Performance monitoring and metrics collection"""

    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.max_metrics = 5000
        self.active_metrics: Dict[str, PerformanceMetric] = {}

    def start_operation(self, component: str, operation: str, **metadata) -> str:
        """Start tracking a performance metric"""
        metric_id = f"perf_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        metric = PerformanceMetric(
            metric_id=metric_id,
            component=component,
            operation=operation,
            start_time=datetime.now(),
            metadata=metadata
        )

        self.active_metrics[metric_id] = metric
        return metric_id

    def end_operation(self, metric_id: str, success: bool = True, **kwargs):
        """End tracking a performance metric"""
        if metric_id not in self.active_metrics:
            logger.warning(f"Attempted to end unknown metric: {metric_id}")
            return

        metric = self.active_metrics[metric_id]
        metric.complete(success, **kwargs)

        # Move to completed metrics
        self.metrics.append(metric)
        if len(self.metrics) > self.max_metrics:
            self.metrics.pop(0)

        del self.active_metrics[metric_id]

        # Log slow operations
        if metric.duration_ms and metric.duration_ms > 5000:  # 5 seconds
            logger.warning(".2f")

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.metrics:
            return {"total_operations": 0}

        total_operations = len(self.metrics)
        successful_operations = len([m for m in self.metrics if m.success])
        failed_operations = total_operations - successful_operations

        # Calculate average duration
        durations = [m.duration_ms for m in self.metrics if m.duration_ms is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Calculate success rate
        success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0

        # Get operations by component
        component_stats = {}
        for metric in self.metrics:
            if metric.component not in component_stats:
                component_stats[metric.component] = {
                    "count": 0,
                    "total_duration": 0,
                    "success_count": 0
                }

            comp_stat = component_stats[metric.component]
            comp_stat["count"] += 1
            if metric.duration_ms:
                comp_stat["total_duration"] += metric.duration_ms
            if metric.success:
                comp_stat["success_count"] += 1

        # Calculate averages for each component
        for comp_stat in component_stats.values():
            if comp_stat["count"] > 0:
                comp_stat["avg_duration"] = comp_stat["total_duration"] / comp_stat["count"]
                comp_stat["success_rate"] = (comp_stat["success_count"] / comp_stat["count"]) * 100

        return {
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "failed_operations": failed_operations,
            "success_rate": success_rate,
            "average_duration_ms": avg_duration,
            "component_stats": component_stats,
            "active_operations": len(self.active_metrics)
        }

class RetryMechanism:
    """Retry mechanism with exponential backoff"""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 60.0, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with retry logic"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = min(self.base_delay * (self.backoff_factor ** attempt), self.max_delay)
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed: {e}")

        raise last_exception

# Global instances
error_monitor = ErrorMonitor()
performance_monitor = PerformanceMonitor()
retry_mechanism = RetryMechanism()

# Circuit breakers for different components
websocket_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
database_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

# Decorators for easy integration

def monitor_performance(component: str, operation: str):
    """Decorator to monitor performance of a function"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            metric_id = performance_monitor.start_operation(component, operation)

            try:
                result = await func(*args, **kwargs)
                performance_monitor.end_operation(metric_id, success=True)
                return result
            except Exception as e:
                performance_monitor.end_operation(metric_id, success=False, error=str(e))
                raise e

        return wrapper
    return decorator

def handle_errors(component: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 category: ErrorCategory = ErrorCategory.UNKNOWN):
    """Decorator to handle errors in a function"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await error_monitor.record_error(
                    component=component,
                    error=e,
                    severity=severity,
                    category=category,
                    context={"function": func.__name__, "args": str(args), "kwargs": str(kwargs)}
                )
                raise e

        return wrapper
    return decorator

def with_retry(max_retries: int = 3):
    """Decorator to add retry logic to a function"""
    def decorator(func: Callable) -> Callable:
        retry_mech = RetryMechanism(max_retries=max_retries)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_mech.execute_with_retry(func, *args, **kwargs)

        return wrapper
    return decorator

def with_circuit_breaker(circuit_breaker: CircuitBreaker):
    """Decorator to add circuit breaker to a function"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await circuit_breaker(func)(*args, **kwargs)

        return wrapper
    return decorator

# Health check functions

async def perform_health_check() -> Dict[str, Any]:
    """Perform a comprehensive health check"""
    health_status = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "healthy",
        "components": {}
    }

    # Check error rates
    error_stats = error_monitor.get_error_stats()
    error_rate_healthy = error_stats["unresolved_errors"] < 10  # Less than 10 unresolved errors
    health_status["components"]["error_monitor"] = {
        "status": "healthy" if error_rate_healthy else "unhealthy",
        "unresolved_errors": error_stats["unresolved_errors"]
    }

    # Check performance
    perf_stats = performance_monitor.get_performance_stats()
    perf_healthy = perf_stats.get("success_rate", 0) > 95  # >95% success rate
    health_status["components"]["performance_monitor"] = {
        "status": "healthy" if perf_healthy else "degraded",
        "success_rate": perf_stats.get("success_rate", 0)
    }

    # Overall status
    if not error_rate_healthy or not perf_healthy:
        health_status["overall_status"] = "degraded"
    if error_stats["unresolved_errors"] > 50:  # Critical threshold
        health_status["overall_status"] = "unhealthy"

    return health_status

# Cleanup functions

async def cleanup_old_data():
    """Clean up old error records and metrics"""
    cutoff_date = datetime.now() - timedelta(days=7)

    # Clean up old errors
    error_monitor.errors = [
        e for e in error_monitor.errors
        if e.timestamp > cutoff_date
    ]

    # Clean up old metrics
    performance_monitor.metrics = [
        m for m in performance_monitor.metrics
        if m.start_time > cutoff_date
    ]

    logger.info("Cleaned up old monitoring data")

# Auto-start cleanup task
async def start_cleanup_task():
    """Start periodic cleanup task"""
    while True:
        await asyncio.sleep(3600)  # Run every hour
        await cleanup_old_data()

asyncio.create_task(start_cleanup_task())