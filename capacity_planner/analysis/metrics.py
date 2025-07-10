"""Metrics calculation and aggregation."""

from typing import List, Dict, Any
from ..models.data_models import ServerMetrics, LogAnalysis


class MetricsCalculator:
    """Calculate and aggregate metrics."""
    
    async def aggregate_metrics(self, metrics_list: List[ServerMetrics]) -> Dict[str, Any]:
        """Aggregate server metrics."""
        if not metrics_list:
            return {}
        
        cpu_values = [m.cpu_usage for m in metrics_list]
        memory_values = [m.memory_usage for m in metrics_list]
        
        return {
            'avg_cpu_usage': sum(cpu_values) / len(cpu_values),
            'max_cpu_usage': max(cpu_values),
            'avg_memory_usage': sum(memory_values) / len(memory_values),
            'max_memory_usage': max(memory_values),
            'server_count': len(metrics_list)
        }
    
    async def analyze_traffic_patterns(self, log_analyses: List[LogAnalysis]) -> Dict[str, Any]:
        """Analyze traffic patterns from logs."""
        if not log_analyses:
            return {}
        
        total_requests = sum(log.total_requests for log in log_analyses)
        error_rates = [log.error_rate for log in log_analyses if log.error_rate is not None]
        
        return {
            'total_requests': total_requests,
            'avg_error_rate': sum(error_rates) / len(error_rates) if error_rates else 0,
            'peak_requests_per_second': max(log.peak_requests_per_minute for log in log_analyses) / 60,
        }