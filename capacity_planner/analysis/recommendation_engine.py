"""Recommendation engine for configuration matching."""

import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..models.data_models import ConfigurationRecommendation, ServerMetrics, LogAnalysis
from ..utils.config import Config
from ..utils.logging import get_logger
from .metrics import MetricsCalculator
from .patterns import PatternMatcher
from .scoring import ConfigurationScorer


class RecommendationEngine:
    """Engine for generating configuration recommendations."""
    
    def __init__(self, config: Config):
        """Initialize recommendation engine.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        self.logger = get_logger("recommendation_engine")
        self.metrics_calculator = MetricsCalculator()
        self.pattern_matcher = PatternMatcher()
        self.scorer = ConfigurationScorer()
        self.configuration_matrix: Optional[pd.DataFrame] = None
        
    async def load_configuration_matrix(self) -> bool:
        """Load configuration matrix from file.
        
        Returns:
            True if loaded successfully
        """
        matrix_path = Path(self.config.config_matrix_path)
        
        if not matrix_path.exists():
            self.logger.warning(f"Configuration matrix not found: {matrix_path}")
            # Create a basic fallback matrix
            self._create_fallback_matrix()
            return False
        
        try:
            self.configuration_matrix = pd.read_csv(matrix_path)
            self.logger.info(f"Loaded {len(self.configuration_matrix)} configurations")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load configuration matrix: {e}")
            self._create_fallback_matrix()
            return False
    
    def _create_fallback_matrix(self):
        """Create a basic fallback configuration matrix."""
        # Basic configurations from p0 to p10
        configs = []
        
        base_configs = [
            {"name": "p0", "tier": 0, "cpu_limit": 0.5, "memory_limit": 512, "specialization": None},
            {"name": "p1", "tier": 1, "cpu_limit": 1.0, "memory_limit": 1024, "specialization": None},
            {"name": "p2", "tier": 2, "cpu_limit": 2.0, "memory_limit": 2048, "specialization": None},
            {"name": "p3", "tier": 3, "cpu_limit": 4.0, "memory_limit": 4096, "specialization": None},
            {"name": "p4", "tier": 4, "cpu_limit": 6.0, "memory_limit": 6144, "specialization": None},
            {"name": "p5", "tier": 5, "cpu_limit": 8.0, "memory_limit": 8192, "specialization": None},
            {"name": "p6", "tier": 6, "cpu_limit": 12.0, "memory_limit": 12288, "specialization": None},
            {"name": "p7", "tier": 7, "cpu_limit": 16.0, "memory_limit": 16384, "specialization": None},
            {"name": "p8", "tier": 8, "cpu_limit": 24.0, "memory_limit": 24576, "specialization": None},
            {"name": "p9", "tier": 9, "cpu_limit": 32.0, "memory_limit": 32768, "specialization": None},
            {"name": "p10", "tier": 10, "cpu_limit": 48.0, "memory_limit": 49152, "specialization": None},
        ]
        
        # Add specialized variants
        for base in base_configs:
            if base["tier"] >= 3:  # Only higher tiers have specializations
                # PHP specialized
                php_config = base.copy()
                php_config["name"] = f"{base['name']}-php"
                php_config["specialization"] = "php"
                php_config["cpu_limit"] *= 1.2  # More CPU for PHP
                configs.append(php_config)
                
                # Database specialized
                db_config = base.copy()
                db_config["name"] = f"{base['name']}-db"
                db_config["specialization"] = "db"
                db_config["memory_limit"] *= 1.5  # More memory for DB
                configs.append(db_config)
                
                # Dense variant
                if base["tier"] >= 5:
                    dense_config = base.copy()
                    dense_config["name"] = f"{base['name']}-dense"
                    dense_config["specialization"] = "dense"
                    dense_config["cpu_limit"] *= 1.5
                    dense_config["memory_limit"] *= 1.3
                    configs.append(dense_config)
            
            configs.append(base)
        
        self.configuration_matrix = pd.DataFrame(configs)
        self.logger.info(f"Created fallback matrix with {len(configs)} configurations")
    
    async def generate_recommendations(
        self,
        metrics: List[ServerMetrics],
        log_analyses: List[LogAnalysis],
        confidence_threshold: float = 0.75
    ) -> List[ConfigurationRecommendation]:
        """Generate configuration recommendations.
        
        Args:
            metrics: Server metrics
            log_analyses: Log analyses
            confidence_threshold: Minimum confidence threshold
            
        Returns:
            List of configuration recommendations
        """
        # Load configuration matrix if not loaded
        if self.configuration_matrix is None:
            await self.load_configuration_matrix()
        
        # Calculate aggregate metrics
        aggregate_metrics = await self.metrics_calculator.aggregate_metrics(metrics)
        
        # Calculate traffic patterns
        traffic_patterns = await self.metrics_calculator.analyze_traffic_patterns(log_analyses)
        
        # Match patterns
        usage_patterns = await self.pattern_matcher.identify_usage_patterns(
            aggregate_metrics, traffic_patterns
        )
        
        # Score configurations
        scored_configs = []
        
        for _, config_row in self.configuration_matrix.iterrows():
            score_data = await self.scorer.score_configuration(
                config_row.to_dict(),
                aggregate_metrics,
                traffic_patterns,
                usage_patterns
            )
            
            if score_data['score'] >= confidence_threshold:
                recommendation = await self._create_recommendation(
                    config_row.to_dict(),
                    score_data,
                    aggregate_metrics,
                    usage_patterns
                )
                scored_configs.append(recommendation)
        
        # Sort by confidence score
        scored_configs.sort(key=lambda x: x.confidence_score, reverse=True)
        
        # Add warnings for edge cases
        for rec in scored_configs[:5]:  # Top 5 recommendations
            await self._add_warnings(rec, aggregate_metrics, traffic_patterns)
        
        self.logger.info(f"Generated {len(scored_configs)} recommendations")
        return scored_configs
    
    async def _create_recommendation(
        self,
        config: Dict[str, Any],
        score_data: Dict[str, Any],
        metrics: Dict[str, Any],
        patterns: Dict[str, Any]
    ) -> ConfigurationRecommendation:
        """Create a configuration recommendation.
        
        Args:
            config: Configuration data
            score_data: Scoring data
            metrics: Aggregate metrics
            patterns: Usage patterns
            
        Returns:
            Configuration recommendation
        """
        # Extract configuration details
        config_name = config.get('name', 'unknown')
        tier = config.get('tier', 0)
        specialization = config.get('specialization')
        
        # Determine size if applicable
        size = None
        if 'xl' in config_name.lower():
            size = "xl"
        elif 'large' in config_name.lower():
            size = "large"
        
        # Build reasoning
        reasoning = score_data.get('reasoning', [])
        
        # Add specific reasoning based on patterns
        if patterns.get('high_cpu_usage'):
            reasoning.append("High CPU usage detected, recommending CPU-optimized configuration")
        
        if patterns.get('high_memory_usage'):
            reasoning.append("High memory usage detected, recommending memory-optimized configuration")
        
        if patterns.get('high_traffic'):
            reasoning.append("High traffic volume detected, recommending higher tier configuration")
        
        if patterns.get('database_intensive'):
            reasoning.append("Database-intensive workload detected")
        
        # Build resource specifications
        resource_specs = {
            'cpu': {
                'limit': config.get('cpu_limit', 0),
                'request': config.get('cpu_request', config.get('cpu_limit', 0) * 0.5)
            },
            'memory': {
                'limit': config.get('memory_limit', 0),
                'request': config.get('memory_request', config.get('memory_limit', 0) * 0.7)
            }
        }
        
        # Add other resource specs if available
        for resource in ['nginx', 'php', 'mysql', 'memcached', 'varnish']:
            if f'{resource}_cpu_limit' in config:
                resource_specs[resource] = {
                    'cpu_limit': config.get(f'{resource}_cpu_limit'),
                    'memory_limit': config.get(f'{resource}_memory_limit'),
                    'cpu_request': config.get(f'{resource}_cpu_request'),
                    'memory_request': config.get(f'{resource}_memory_request')
                }
        
        # Estimate capacity
        estimated_capacity = {
            'requests_per_second': self._estimate_rps_capacity(config, metrics),
            'concurrent_users': self._estimate_concurrent_capacity(config, metrics),
            'storage_gb': config.get('storage_limit', 100)
        }
        
        return ConfigurationRecommendation(
            config_name=config_name,
            tier=tier,
            specialization=specialization,
            size=size,
            confidence_score=score_data['score'],
            reasoning=reasoning,
            resource_specs=resource_specs,
            estimated_capacity=estimated_capacity
        )
    
    def _estimate_rps_capacity(self, config: Dict[str, Any], metrics: Dict[str, Any]) -> float:
        """Estimate requests per second capacity.
        
        Args:
            config: Configuration
            metrics: Aggregate metrics
            
        Returns:
            Estimated RPS capacity
        """
        # Base RPS based on CPU and tier
        base_rps = config.get('cpu_limit', 1) * 50  # 50 RPS per CPU core
        
        # Adjust for specialization
        if config.get('specialization') == 'php':
            base_rps *= 1.2
        elif config.get('specialization') == 'db':
            base_rps *= 0.8  # DB-heavy workloads typically handle fewer requests
        
        # Adjust based on current performance
        current_rps = metrics.get('avg_requests_per_second', 0)
        if current_rps > 0:
            # Use current performance as a baseline
            scaling_factor = base_rps / max(current_rps, 1)
            base_rps = current_rps * scaling_factor
        
        return round(base_rps, 1)
    
    def _estimate_concurrent_capacity(self, config: Dict[str, Any], metrics: Dict[str, Any]) -> int:
        """Estimate concurrent users capacity.
        
        Args:
            config: Configuration
            metrics: Aggregate metrics
            
        Returns:
            Estimated concurrent users
        """
        # Base concurrent users based on memory and CPU
        memory_gb = config.get('memory_limit', 512) / 1024
        cpu_cores = config.get('cpu_limit', 1)
        
        # Rough estimate: 100 concurrent users per GB memory + 200 per CPU core
        base_concurrent = int(memory_gb * 100 + cpu_cores * 200)
        
        # Adjust for specialization
        if config.get('specialization') == 'dense':
            base_concurrent = int(base_concurrent * 1.5)
        
        return base_concurrent
    
    async def _add_warnings(
        self,
        recommendation: ConfigurationRecommendation,
        metrics: Dict[str, Any],
        traffic_patterns: Dict[str, Any]
    ):
        """Add warnings to recommendations.
        
        Args:
            recommendation: Recommendation to add warnings to
            metrics: Aggregate metrics
            traffic_patterns: Traffic patterns
        """
        warnings = []
        
        # CPU warnings
        cpu_usage = metrics.get('avg_cpu_usage', 0)
        if cpu_usage > 80:
            warnings.append("Current CPU usage is very high. Monitor performance after migration.")
        
        # Memory warnings
        memory_usage = metrics.get('avg_memory_usage', 0)
        if memory_usage > 85:
            warnings.append("Current memory usage is very high. Consider higher tier if issues persist.")
        
        # Traffic warnings
        peak_rps = traffic_patterns.get('peak_requests_per_second', 0)
        estimated_rps = recommendation.estimated_capacity.get('requests_per_second', 0)
        
        if peak_rps > estimated_rps * 0.8:
            warnings.append("Peak traffic is close to estimated capacity. Monitor during high traffic periods.")
        
        # Error rate warnings
        error_rate = traffic_patterns.get('avg_error_rate', 0)
        if error_rate > 5:
            warnings.append("High error rate detected. Investigate application issues before migration.")
        
        # Database warnings
        if metrics.get('mysql_slow_queries', 0) > 100:
            warnings.append("High number of slow MySQL queries detected. Consider database optimization.")
        
        # Tier-specific warnings
        if recommendation.tier == 0:
            warnings.append("P0 configuration has very limited resources. Only suitable for development/testing.")
        
        elif recommendation.tier >= 8:
            warnings.append("High-tier configuration selected. Ensure cost justification.")
        
        recommendation.warnings = warnings