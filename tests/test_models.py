"""Test data models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from capacity_planner.models.data_models import (
    SSHConfig, ServerMetrics, LogAnalysis, AnalysisRequest,
    AnalysisResult, ConfigurationRecommendation, DataSource,
    DataSourceType, WorkerTask
)


class TestSSHConfig:
    """Test SSH configuration model."""
    
    def test_valid_ssh_config(self):
        """Test valid SSH configuration."""
        config = SSHConfig(
            hostname="pod-1.wpengine.com",
            username="testuser",
            key_path="~/.ssh/id_rsa",
            port=22
        )
        
        assert config.hostname == "pod-1.wpengine.com"
        assert config.username == "testuser"
        assert config.key_path == "~/.ssh/id_rsa"
        assert config.port == 22
    
    def test_pod_number_hostname_generation(self):
        """Test automatic hostname generation from pod number."""
        config = SSHConfig(
            hostname="",
            username="testuser",
            pod_number=5
        )
        
        # Validator should set hostname based on pod_number
        assert "pod-5" in config.hostname
    
    def test_invalid_ssh_config(self):
        """Test invalid SSH configuration."""
        with pytest.raises(ValidationError):
            SSHConfig(hostname="", username="")


class TestServerMetrics:
    """Test server metrics model."""
    
    def test_valid_server_metrics(self, sample_server_metrics):
        """Test valid server metrics."""
        assert sample_server_metrics.hostname == "pod-1.wpengine.com"
        assert sample_server_metrics.cpu_usage == 45.2
        assert sample_server_metrics.memory_usage == 67.8
        assert isinstance(sample_server_metrics.timestamp, datetime)
        assert sample_server_metrics.processes["total"] == 145
    
    def test_server_metrics_serialization(self, sample_server_metrics):
        """Test server metrics serialization."""
        data = sample_server_metrics.model_dump()
        
        assert "hostname" in data
        assert "cpu_usage" in data
        assert "timestamp" in data
        
        # Test JSON serialization with datetime
        json_data = sample_server_metrics.model_dump_json()
        assert "timestamp" in json_data


class TestLogAnalysis:
    """Test log analysis model."""
    
    def test_valid_log_analysis(self, sample_log_analysis):
        """Test valid log analysis."""
        assert sample_log_analysis.log_path == "/var/log/nginx/test.access.log"
        assert sample_log_analysis.total_requests == 10000
        assert sample_log_analysis.error_rate == 2.5
        assert len(sample_log_analysis.top_ips) == 3
        assert sum(sample_log_analysis.status_codes.values()) == 10000
    
    def test_log_analysis_calculations(self, sample_log_analysis):
        """Test log analysis calculations."""
        # Verify status code totals
        total_requests = sum(sample_log_analysis.status_codes.values())
        assert total_requests == sample_log_analysis.total_requests
        
        # Verify error calculation
        error_requests = sample_log_analysis.status_codes.get("500", 0)
        expected_error_rate = (error_requests / total_requests) * 100
        # Allow for some calculation differences
        assert abs(sample_log_analysis.error_rate - expected_error_rate) < 5


class TestDataSource:
    """Test data source model."""
    
    def test_csv_data_source(self, temp_csv_file):
        """Test CSV data source."""
        source = DataSource(
            type=DataSourceType.CSV,
            path=temp_csv_file
        )
        
        assert source.type == DataSourceType.CSV
        assert source.path == temp_csv_file
        assert source.ssh_config is None
    
    def test_ssh_data_source(self, sample_ssh_config):
        """Test SSH data source."""
        source = DataSource(
            type=DataSourceType.SSH,
            ssh_config=sample_ssh_config,
            install_names=["test_install"]
        )
        
        assert source.type == DataSourceType.SSH
        assert source.ssh_config == sample_ssh_config
        assert source.install_names == ["test_install"]


class TestConfigurationRecommendation:
    """Test configuration recommendation model."""
    
    def test_valid_recommendation(self):
        """Test valid configuration recommendation."""
        rec = ConfigurationRecommendation(
            config_name="p5-php",
            tier=5,
            specialization="php",
            confidence_score=0.85,
            reasoning=["High CPU usage detected", "PHP workload identified"],
            resource_specs={
                "cpu": {"limit": 8.0, "request": 4.0},
                "memory": {"limit": 8192, "request": 6144}
            },
            estimated_capacity={
                "requests_per_second": 400.0,
                "concurrent_users": 800
            }
        )
        
        assert rec.config_name == "p5-php"
        assert rec.tier == 5
        assert rec.specialization == "php"
        assert rec.confidence_score == 0.85
        assert len(rec.reasoning) == 2
    
    def test_invalid_confidence_score(self):
        """Test invalid confidence score validation."""
        with pytest.raises(ValidationError):
            ConfigurationRecommendation(
                config_name="p5",
                tier=5,
                confidence_score=1.5,  # Invalid: > 1.0
                reasoning=[],
                resource_specs={},
                estimated_capacity={}
            )
        
        with pytest.raises(ValidationError):
            ConfigurationRecommendation(
                config_name="p5",
                tier=5,
                confidence_score=-0.1,  # Invalid: < 0.0
                reasoning=[],
                resource_specs={},
                estimated_capacity={}
            )


class TestWorkerTask:
    """Test worker task model."""
    
    def test_valid_worker_task(self, sample_worker_task):
        """Test valid worker task."""
        assert sample_worker_task.task_id == "test-task-123"
        assert sample_worker_task.worker_type == "ssh"
        assert sample_worker_task.status == "pending"
        assert sample_worker_task.priority == 0
        assert sample_worker_task.result is None
        assert sample_worker_task.error is None
    
    def test_task_status_updates(self, sample_worker_task):
        """Test task status updates."""
        # Update to processing
        sample_worker_task.status = "processing"
        assert sample_worker_task.status == "processing"
        
        # Update to completed with result
        sample_worker_task.status = "completed"
        sample_worker_task.result = {"test": "result"}
        assert sample_worker_task.status == "completed"
        assert sample_worker_task.result == {"test": "result"}
        
        # Update to failed with error
        sample_worker_task.status = "failed"
        sample_worker_task.error = "Test error"
        assert sample_worker_task.status == "failed"
        assert sample_worker_task.error == "Test error"


class TestAnalysisRequest:
    """Test analysis request model."""
    
    def test_valid_analysis_request(self, temp_csv_file):
        """Test valid analysis request."""
        data_sources = [
            DataSource(type=DataSourceType.CSV, path=temp_csv_file)
        ]
        
        request = AnalysisRequest(
            data_sources=data_sources,
            confidence_threshold=0.8,
            include_historical=True,
            output_format="markdown"
        )
        
        assert len(request.data_sources) == 1
        assert request.confidence_threshold == 0.8
        assert request.include_historical is True
        assert request.output_format == "markdown"
    
    def test_default_values(self, temp_csv_file):
        """Test default values in analysis request."""
        data_sources = [
            DataSource(type=DataSourceType.CSV, path=temp_csv_file)
        ]
        
        request = AnalysisRequest(data_sources=data_sources)
        
        assert request.confidence_threshold == 0.75
        assert request.include_historical is True
        assert request.historical_days == 30
        assert request.output_format == "markdown"
        assert request.interactive is False


class TestAnalysisResult:
    """Test analysis result model."""
    
    def test_valid_analysis_result(self, sample_server_metrics, sample_log_analysis):
        """Test valid analysis result."""
        recommendations = [
            ConfigurationRecommendation(
                config_name="p5",
                tier=5,
                confidence_score=0.85,
                reasoning=["Test reasoning"],
                resource_specs={},
                estimated_capacity={}
            )
        ]
        
        result = AnalysisResult(
            request_id="test-123",
            status="completed",
            recommendations=recommendations,
            server_metrics=[sample_server_metrics],
            log_analyses=[sample_log_analysis],
            execution_time=15.5
        )
        
        assert result.request_id == "test-123"
        assert result.status == "completed"
        assert len(result.recommendations) == 1
        assert len(result.server_metrics) == 1
        assert len(result.log_analyses) == 1
        assert result.execution_time == 15.5
        assert isinstance(result.timestamp, datetime)
    
    def test_failed_analysis_result(self):
        """Test failed analysis result."""
        result = AnalysisResult(
            request_id="test-456",
            status="failed",
            recommendations=[],
            errors=["SSH connection failed", "Invalid data format"],
            execution_time=5.2
        )
        
        assert result.status == "failed"
        assert len(result.errors) == 2
        assert len(result.recommendations) == 0
        assert result.execution_time == 5.2