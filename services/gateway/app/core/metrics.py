"""
File Overview: Lightweight latency tracking helpers and in memory performance monitor for HelixStream APIs.
Responsibilities:
- Decorate sync/async functions to log execution time and flag slow calls over 100ms.
- Capture per-call stats and accumulate successes/failures and slow-query lists for the session.
Data Flow:
- Inputs: wrapped callable invocation (endpoint or service), optional endpoint_name override.
- Outputs: log lines for timing/ failures; in memory stats dictionaries via PerformanceMonitor.
System Integration:
- Used by FastAPI endpoints to emit latency info to application logs.
Technical Details:
- Uses functools.wraps to preserve metadata; supports coroutine detection to select async vs sync wrapper.
- Percentile calculations (p95/p99) performed on collected durations in milliseconds.
Future Considerations:
- Export metrics to structured backend (Prometheus/OpenTelemetry) and bound list growth with rolling windows.
"""

# Performance monitoring and query time tracking for tracking API endpoint latencies
import time
import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def track_query_time(endpoint_name: str = None):
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            name = endpoint_name or func.__name__
            
            try:
                result = await func(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000
                
                if elapsed_ms > 100:
                    logger.warning(f"SLOW QUERY: {name} took {elapsed_ms:.2f}ms")
                else:
                    logger.info(f"{name}: {elapsed_ms:.2f}ms")
                
                return result
                
            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.error(f"✗ {name} FAILED after {elapsed_ms:.2f}ms: {e}", exc_info=True)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            name = endpoint_name or func.__name__
            
            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.time() - start_time) * 1000
                
                if elapsed_ms > 100:
                    logger.warning(f"SLOW QUERY: {name} took {elapsed_ms:.2f}ms")
                else:
                    logger.info(f"{name}: {elapsed_ms:.2f}ms")
                
                return result
                
            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.error(f"✗ {name} FAILED after {elapsed_ms:.2f}ms: {e}", exc_info=True)
                raise
        
        # Return appropriate wrapper based on whether func is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class PerformanceMonitor:
    """
    Simple performance monitoring for tracking query statistics.
    
    Keeps in-memory statistics for the current session.
    """
    
    def __init__(self):
        self.query_times = []
        self.slow_queries = []
        self.failed_queries = []
    
    def record_query(self, endpoint: str, duration_ms: float, success: bool = True):
        """Record query execution time."""
        self.query_times.append({
            "endpoint": endpoint,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": time.time()
        })
        
        if duration_ms > 100:
            self.slow_queries.append({
                "endpoint": endpoint,
                "duration_ms": duration_ms
            })
        
        if not success:
            self.failed_queries.append({
                "endpoint": endpoint,
                "duration_ms": duration_ms
            })
    
    def get_stats(self) -> dict:
        """Get performance statistics."""
        if not self.query_times:
            return {
                "total_queries": 0,
                "avg_latency_ms": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
                "slow_query_count": 0,
                "failed_query_count": 0,
                "success_rate": 1.0
            }
        
        durations = [q["duration_ms"] for q in self.query_times]
        successful = [q for q in self.query_times if q["success"]]
        
        durations_sorted = sorted(durations)
        p95_idx = int(len(durations_sorted) * 0.95)
        p99_idx = int(len(durations_sorted) * 0.99)
        
        return {
            "total_queries": len(self.query_times),
            "avg_latency_ms": sum(durations) / len(durations),
            "p95_latency_ms": durations_sorted[p95_idx] if durations_sorted else 0,
            "p99_latency_ms": durations_sorted[p99_idx] if durations_sorted else 0,
            "slow_query_count": len(self.slow_queries),
            "failed_query_count": len(self.failed_queries),
            "success_rate": len(successful) / len(self.query_times)
        }
    
    def reset(self):
        """Reset all statistics."""
        self.query_times.clear()
        self.slow_queries.clear()
        self.failed_queries.clear()


# Global monitor instance
performance_monitor = PerformanceMonitor()
