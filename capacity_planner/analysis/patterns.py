"""Pattern matching for usage analysis."""

from typing import Dict, Any


class PatternMatcher:
    """Match usage patterns."""
    
    async def identify_usage_patterns(
        self, 
        metrics: Dict[str, Any], 
        traffic: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Identify usage patterns."""
        patterns = {}
        
        # CPU patterns
        cpu_usage = metrics.get('avg_cpu_usage', 0)
        patterns['high_cpu_usage'] = cpu_usage > 70
        patterns['moderate_cpu_usage'] = 30 <= cpu_usage <= 70
        patterns['low_cpu_usage'] = cpu_usage < 30
        
        # Memory patterns
        memory_usage = metrics.get('avg_memory_usage', 0)
        patterns['high_memory_usage'] = memory_usage > 75
        patterns['moderate_memory_usage'] = 30 <= memory_usage <= 75
        patterns['low_memory_usage'] = memory_usage < 30
        
        # Traffic patterns
        rps = traffic.get('peak_requests_per_second', 0)
        patterns['high_traffic'] = rps > 100
        patterns['moderate_traffic'] = 10 <= rps <= 100
        patterns['low_traffic'] = rps < 10
        
        # Error patterns
        error_rate = traffic.get('avg_error_rate', 0)
        patterns['high_error_rate'] = error_rate > 5
        patterns['errors_present'] = error_rate > 1
        
        return patterns