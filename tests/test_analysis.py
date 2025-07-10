"""Test analysis engine components."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, AsyncMock

from capacity_planner.analysis.metrics import MetricsCalculator
from capacity_planner.analysis.patterns import PatternMatcher
from capacity_planner.analysis.scoring import ConfigurationScorer
from capacity_planner.analysis.recommendation_engine import RecommendationEngine
from capacity_planner.models.data_models import ServerMetrics, LogAnalysis


class TestMetricsCalculator:
    """Test metrics calculator."""
    
    @pytest.mark.asyncio
    async def test_aggregate_metrics_empty(self):
        """Test aggregating empty metrics list."""
        calculator = MetricsCalculator()
        result = await calculator.aggregate_metrics([])
        
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_aggregate_metrics(self, sample_server_metrics):
        """Test metrics aggregation."""
        calculator = MetricsCalculator()
        
        # Create multiple metrics
        metrics_list = [
            sample_server_metrics,
            ServerMetrics(
                hostname="pod-2.wpengine.com",
                cpu_usage=55.5,
                memory_usage=72.3,
                memory_total=8589934592,
                memory_available=2147483648,
                disk_usage=40.0,
                disk_total=107374182400,
                disk_used=42949672960,
                load_average="1.5, 1.6, 1.7",
                processes={"total": 150, "mysql": 4, "php": 15}
            )
        ]
        
        result = await calculator.aggregate_metrics(metrics_list)
        
        assert result["server_count"] == 2
        assert result["avg_cpu_usage"] == (45.2 + 55.5) / 2
        assert result["max_cpu_usage"] == 55.5
        assert result["avg_memory_usage"] == (67.8 + 72.3) / 2
        assert result["max_memory_usage"] == 72.3
    
    @pytest.mark.asyncio
    async def test_analyze_traffic_patterns_empty(self):
        """Test analyzing empty traffic patterns."""
        calculator = MetricsCalculator()
        result = await calculator.analyze_traffic_patterns([])
        
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_analyze_traffic_patterns(self, sample_log_analysis):
        """Test traffic pattern analysis."""
        calculator = MetricsCalculator()
        
        # Create multiple log analyses
        log_analyses = [
            sample_log_analysis,
            LogAnalysis(
                log_path="/var/log/nginx/test2.access.log",
                total_requests=5000,
                error_rate=1.5,
                avg_response_time=0.180,
                peak_requests_per_minute=420,
                top_ips=["10.0.0.1", "172.16.0.1"],
                status_codes={"200": 4900, "404": 75, "500": 25}
            )
        ]
        
        result = await calculator.analyze_traffic_patterns(log_analyses)
        
        assert result["total_requests"] == 15000  # 10000 + 5000
        assert result["avg_error_rate"] == (2.5 + 1.5) / 2
        assert result["peak_requests_per_second"] == 850 / 60  # Max peak_requests_per_minute / 60


class TestPatternMatcher:
    """Test pattern matcher."""
    
    @pytest.mark.asyncio
    async def test_identify_usage_patterns_high_usage(self):
        """Test identifying high usage patterns."""
        matcher = PatternMatcher()
        
        metrics = {
            "avg_cpu_usage": 85.0,
            "avg_memory_usage": 80.0
        }
        
        traffic = {
            "peak_requests_per_second": 150.0,
            "avg_error_rate": 6.0
        }
        
        patterns = await matcher.identify_usage_patterns(metrics, traffic)
        
        assert patterns["high_cpu_usage"] is True
        assert patterns["moderate_cpu_usage"] is False
        assert patterns["low_cpu_usage"] is False
        
        assert patterns["high_memory_usage"] is True
        assert patterns["moderate_memory_usage"] is False
        assert patterns["low_memory_usage"] is False
        
        assert patterns["high_traffic"] is True
        assert patterns["moderate_traffic"] is False
        assert patterns["low_traffic"] is False
        
        assert patterns["high_error_rate"] is True
        assert patterns["errors_present"] is True
    
    @pytest.mark.asyncio
    async def test_identify_usage_patterns_low_usage(self):
        """Test identifying low usage patterns."""
        matcher = PatternMatcher()
        
        metrics = {
            "avg_cpu_usage": 25.0,
            "avg_memory_usage": 35.0
        }
        
        traffic = {
            "peak_requests_per_second": 5.0,
            "avg_error_rate": 0.5
        }
        
        patterns = await matcher.identify_usage_patterns(metrics, traffic)
        
        assert patterns["high_cpu_usage"] is False
        assert patterns["moderate_cpu_usage"] is False
        assert patterns["low_cpu_usage"] is True
        
        assert patterns["high_memory_usage"] is False
        assert patterns["moderate_memory_usage"] is True
        assert patterns["low_memory_usage"] is False
        
        assert patterns["high_traffic"] is False
        assert patterns["moderate_traffic"] is False
        assert patterns["low_traffic"] is True
        
        assert patterns["high_error_rate"] is False
        assert patterns["errors_present"] is False


class TestConfigurationScorer:
    """Test configuration scorer."""
    
    @pytest.mark.asyncio
    async def test_score_configuration_adequate(self):
        """Test scoring adequate configuration."""
        scorer = ConfigurationScorer()
        
        config = {
            "name": "p5",
            "tier": 5,
            "cpu_limit": 8.0,
            "memory_limit": 8192,  # 8GB in MB
            "specialization": None
        }
        
        metrics = {
            "avg_cpu_usage": 50.0,  # Requires ~1.0 CPU (50% of 2x headroom)
            "avg_memory_usage": 60.0  # Requires ~2.4GB
        }
        
        traffic = {
            "peak_requests_per_second": 200.0
        }
        
        patterns = {
            "high_cpu_usage": False,
            "high_memory_usage": False
        }
        
        result = await scorer.score_configuration(config, metrics, traffic, patterns)
        
        assert result["score"] > 0.5  # Should be a good match
        assert len(result["reasoning"]) > 0
        assert any("adequate" in reason.lower() for reason in result["reasoning"])
    
    @pytest.mark.asyncio
    async def test_score_configuration_insufficient(self):
        """Test scoring insufficient configuration."""
        scorer = ConfigurationScorer()
        
        config = {
            "name": "p1",
            "tier": 1,
            "cpu_limit": 1.0,
            "memory_limit": 1024,  # 1GB in MB
            "specialization": None
        }
        
        metrics = {
            "avg_cpu_usage": 80.0,  # Requires ~1.6 CPU
            "avg_memory_usage": 85.0  # Requires ~3.4GB
        }
        
        traffic = {
            "peak_requests_per_second": 300.0
        }
        
        patterns = {
            "high_cpu_usage": True,
            "high_memory_usage": True
        }
        
        result = await scorer.score_configuration(config, metrics, traffic, patterns)
        
        assert result["score"] < 0.5  # Should be a poor match
        assert any("insufficient" in reason.lower() for reason in result["reasoning"])
    
    @pytest.mark.asyncio
    async def test_score_configuration_with_specialization(self):
        """Test scoring configuration with specialization bonus."""
        scorer = ConfigurationScorer()
        
        config = {
            "name": "p3-php",
            "tier": 3,
            "cpu_limit": 4.0,
            "memory_limit": 4096,
            "specialization": "php"
        }
        
        metrics = {
            "avg_cpu_usage": 60.0,
            "avg_memory_usage": 50.0
        }
        
        traffic = {
            "peak_requests_per_second": 100.0
        }
        
        patterns = {
            "high_cpu_usage": True,  # This should trigger PHP specialization bonus
            "high_memory_usage": False
        }
        
        result = await scorer.score_configuration(config, metrics, traffic, patterns)
        
        # Should get bonus for PHP specialization with high CPU usage
        assert any("php specialization" in reason.lower() for reason in result["reasoning"])


class TestRecommendationEngine:
    """Test recommendation engine."""
    
    @pytest.mark.asyncio
    async def test_recommendation_engine_initialization(self, mock_config):
        """Test recommendation engine initialization."""
        engine = RecommendationEngine(mock_config)
        
        assert engine.config == mock_config
        assert engine.configuration_matrix is None
    
    @pytest.mark.asyncio
    async def test_create_fallback_matrix(self, mock_config):
        """Test fallback matrix creation."""
        engine = RecommendationEngine(mock_config)
        engine._create_fallback_matrix()
        
        assert engine.configuration_matrix is not None
        assert len(engine.configuration_matrix) > 10  # Should have multiple configs
        assert "name" in engine.configuration_matrix.columns
        assert "tier" in engine.configuration_matrix.columns
        assert "cpu_limit" in engine.configuration_matrix.columns
    
    @pytest.mark.asyncio
    @patch('pathlib.Path.exists')
    @patch('pandas.read_csv')
    async def test_load_configuration_matrix_success(self, mock_read_csv, mock_exists, mock_config, sample_configuration_matrix):
        """Test successful configuration matrix loading."""
        mock_exists.return_value = True
        mock_read_csv.return_value = sample_configuration_matrix
        
        engine = RecommendationEngine(mock_config)
        result = await engine.load_configuration_matrix()
        
        assert result is True
        assert engine.configuration_matrix is not None
        assert len(engine.configuration_matrix) == 4
    
    @pytest.mark.asyncio
    @patch('pandas.read_csv')
    async def test_load_configuration_matrix_failure(self, mock_read_csv, mock_config):
        """Test configuration matrix loading failure."""
        mock_read_csv.side_effect = FileNotFoundError("File not found")
        
        engine = RecommendationEngine(mock_config)
        result = await engine.load_configuration_matrix()
        
        assert result is False
        assert engine.configuration_matrix is not None  # Should have fallback
    
    @pytest.mark.asyncio
    async def test_generate_recommendations(self, mock_config, sample_server_metrics, sample_log_analysis):
        """Test recommendation generation."""
        engine = RecommendationEngine(mock_config)
        
        # Use fallback matrix
        engine._create_fallback_matrix()
        
        # Mock the components
        with patch.object(engine.metrics_calculator, 'aggregate_metrics') as mock_aggregate, \
             patch.object(engine.metrics_calculator, 'analyze_traffic_patterns') as mock_traffic, \
             patch.object(engine.pattern_matcher, 'identify_usage_patterns') as mock_patterns, \
             patch.object(engine.scorer, 'score_configuration') as mock_scorer:
            
            mock_aggregate.return_value = {
                "avg_cpu_usage": 45.0,
                "avg_memory_usage": 65.0
            }
            
            mock_traffic.return_value = {
                "peak_requests_per_second": 100.0,
                "avg_error_rate": 2.0
            }
            
            mock_patterns.return_value = {
                "high_cpu_usage": False,
                "high_memory_usage": False
            }
            
            # Return high score for p2 configuration
            def mock_score_func(config, metrics, traffic, patterns):
                if config.get("name") == "p2":
                    return {"score": 0.85, "reasoning": ["Good match"]}
                else:
                    return {"score": 0.60, "reasoning": ["Adequate match"]}
            
            mock_scorer.side_effect = mock_score_func
            
            recommendations = await engine.generate_recommendations(
                metrics=[sample_server_metrics],
                log_analyses=[sample_log_analysis],
                confidence_threshold=0.75
            )
            
            assert len(recommendations) >= 1
            # Should be sorted by confidence score
            assert recommendations[0].confidence_score >= 0.75
            assert recommendations[0].config_name is not None
            assert recommendations[0].tier >= 0
    
    @pytest.mark.asyncio
    async def test_estimate_rps_capacity(self, mock_config):
        """Test RPS capacity estimation."""
        engine = RecommendationEngine(mock_config)
        
        config = {
            "cpu_limit": 4.0,
            "specialization": "php"
        }
        
        metrics = {
            "avg_requests_per_second": 150.0
        }
        
        rps = engine._estimate_rps_capacity(config, metrics)
        
        assert rps > 0
        assert isinstance(rps, float)
        # PHP specialization should increase capacity
        assert rps > 4.0 * 50  # Base calculation
    
    @pytest.mark.asyncio
    async def test_estimate_concurrent_capacity(self, mock_config):
        """Test concurrent user capacity estimation."""
        engine = RecommendationEngine(mock_config)
        
        config = {
            "cpu_limit": 4.0,
            "memory_limit": 8192,  # 8GB
            "specialization": "dense"
        }
        
        metrics = {}
        
        concurrent = engine._estimate_concurrent_capacity(config, metrics)
        
        assert concurrent > 0
        assert isinstance(concurrent, int)
        # Dense specialization should increase capacity
        base_estimate = int(8 * 100 + 4.0 * 200)  # 800 + 800 = 1600
        assert concurrent > base_estimate
    
    @pytest.mark.asyncio
    async def test_add_warnings(self, mock_config):
        """Test warning addition to recommendations."""
        from capacity_planner.models.data_models import ConfigurationRecommendation
        
        engine = RecommendationEngine(mock_config)
        
        recommendation = ConfigurationRecommendation(
            config_name="p0",
            tier=0,
            confidence_score=0.80,
            reasoning=["Test reasoning"],
            resource_specs={},
            estimated_capacity={"requests_per_second": 50.0}
        )
        
        metrics = {
            "avg_cpu_usage": 85.0,  # High CPU usage
            "avg_memory_usage": 90.0,  # High memory usage
            "mysql_slow_queries": 150  # High slow queries
        }
        
        traffic_patterns = {
            "peak_requests_per_second": 45.0,  # Close to capacity
            "avg_error_rate": 8.0  # High error rate
        }
        
        await engine._add_warnings(recommendation, metrics, traffic_patterns)
        
        assert len(recommendation.warnings) > 0
        
        # Check for specific warnings
        warning_text = " ".join(recommendation.warnings).lower()
        assert "cpu" in warning_text or "memory" in warning_text
        assert "p0" in warning_text  # Should warn about P0 tier