"""Configuration scoring logic."""

from typing import Dict, Any


class ConfigurationScorer:
    """Score configurations against requirements."""
    
    async def score_configuration(
        self,
        config: Dict[str, Any],
        metrics: Dict[str, Any],
        traffic: Dict[str, Any],
        patterns: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Score a configuration."""
        score = 0.0
        reasoning = []
        
        # CPU scoring
        cpu_limit = config.get('cpu_limit', 1)
        required_cpu = metrics.get('avg_cpu_usage', 0) / 100 * 2  # 2x headroom
        
        if cpu_limit >= required_cpu:
            cpu_score = min(1.0, cpu_limit / max(required_cpu, 0.1))
            score += cpu_score * 0.3
            reasoning.append(f"CPU capacity adequate ({cpu_limit} cores vs {required_cpu:.1f} required)")
        else:
            score += 0.1
            reasoning.append(f"CPU capacity insufficient ({cpu_limit} cores vs {required_cpu:.1f} required)")
        
        # Memory scoring
        memory_limit = config.get('memory_limit', 512) / 1024  # Convert to GB
        required_memory = metrics.get('avg_memory_usage', 0) / 100 * 4  # 4GB baseline
        
        if memory_limit >= required_memory:
            memory_score = min(1.0, memory_limit / max(required_memory, 0.5))
            score += memory_score * 0.3
            reasoning.append(f"Memory capacity adequate ({memory_limit:.1f}GB vs {required_memory:.1f}GB required)")
        else:
            score += 0.1
            reasoning.append(f"Memory capacity insufficient ({memory_limit:.1f}GB vs {required_memory:.1f}GB required)")
        
        # Traffic scoring
        rps_capacity = cpu_limit * 50  # Rough estimate
        required_rps = traffic.get('peak_requests_per_second', 1)
        
        if rps_capacity >= required_rps:
            traffic_score = min(1.0, rps_capacity / max(required_rps, 1))
            score += traffic_score * 0.2
            reasoning.append(f"Traffic capacity adequate ({rps_capacity:.0f} RPS vs {required_rps:.0f} peak)")
        else:
            score += 0.05
            reasoning.append(f"Traffic capacity insufficient ({rps_capacity:.0f} RPS vs {required_rps:.0f} peak)")
        
        # Pattern bonuses
        specialization = config.get('specialization')
        if patterns.get('high_cpu_usage') and specialization == 'php':
            score += 0.1
            reasoning.append("PHP specialization matches high CPU usage pattern")
        
        if patterns.get('high_memory_usage') and specialization == 'db':
            score += 0.1
            reasoning.append("Database specialization matches high memory usage pattern")
        
        # Base score
        score += 0.1
        
        return {
            'score': min(1.0, score),
            'reasoning': reasoning
        }