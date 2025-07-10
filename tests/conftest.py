"""Pytest configuration and fixtures."""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock
import pandas as pd

from capacity_planner.models.data_models import (
    SSHConfig, ServerMetrics, LogAnalysis, WorkerTask, 
    DataSource, DataSourceType
)
from capacity_planner.utils.config import Config


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = Mock(spec=Config)
    config.ssh_key_path = "~/.ssh/id_rsa"
    config.default_ssh_user = "testuser"
    config.sudo_password = "testpass"
    config.confidence_threshold = 0.75
    config.max_workers = 4
    config.config_matrix_path = "/tmp/test_matrix.csv"
    return config


@pytest.fixture
def sample_ssh_config():
    """Sample SSH configuration."""
    return SSHConfig(
        hostname="pod-1.wpengine.com",
        username="testuser",
        key_path="~/.ssh/id_rsa",
        pod_number=1
    )


@pytest.fixture
def sample_server_metrics():
    """Sample server metrics."""
    return ServerMetrics(
        hostname="pod-1.wpengine.com",
        cpu_usage=45.2,
        memory_usage=67.8,
        memory_total=8589934592,  # 8GB
        memory_available=2684354560,  # ~2.5GB
        disk_usage=34.5,
        disk_total=107374182400,  # 100GB
        disk_used=37040652288,   # ~34.5GB
        load_average="1.23, 1.45, 1.67",
        processes={
            "total": 145,
            "mysql": 3,
            "php": 12,
            "nginx": 2,
            "apache": 0
        }
    )


@pytest.fixture
def sample_log_analysis():
    """Sample log analysis."""
    return LogAnalysis(
        log_path="/var/log/nginx/test.access.log",
        total_requests=10000,
        error_rate=2.5,
        avg_response_time=0.234,
        peak_requests_per_minute=850,
        top_ips=["192.168.1.1", "10.0.0.1", "172.16.0.1"],
        status_codes={"200": 8500, "404": 150, "500": 25, "301": 1325}
    )


@pytest.fixture
def sample_worker_task():
    """Sample worker task."""
    return WorkerTask(
        task_id="test-task-123",
        worker_type="ssh",
        data_source=DataSource(
            type=DataSourceType.SSH,
            ssh_config=SSHConfig(
                hostname="pod-1.wpengine.com",
                username="testuser",
                key_path="~/.ssh/id_rsa"
            )
        ),
        parameters={"test_param": "test_value"}
    )


@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        # Write sample CSV data
        f.write("timestamp,cpu_usage,memory_usage,requests\n")
        f.write("2024-01-01 10:00:00,45.2,67.8,1250\n")
        f.write("2024-01-01 10:01:00,47.1,68.2,1380\n")
        f.write("2024-01-01 10:02:00,44.8,66.9,1190\n")
        f.write("2024-01-01 10:03:00,46.5,69.1,1420\n")
        
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        # Write sample access log entries
        log_entries = [
            '192.168.1.1 - - [01/Jan/2024:10:00:00 +0000] "GET / HTTP/1.1" 200 1234 0.123',
            '192.168.1.2 - - [01/Jan/2024:10:00:01 +0000] "GET /page1 HTTP/1.1" 200 5678 0.089',
            '192.168.1.3 - - [01/Jan/2024:10:00:02 +0000] "POST /api/data HTTP/1.1" 500 0 2.345',
            '192.168.1.1 - - [01/Jan/2024:10:00:03 +0000] "GET /image.jpg HTTP/1.1" 404 0 0.012',
            '192.168.1.4 - - [01/Jan/2024:10:00:04 +0000] "GET /about HTTP/1.1" 200 2345 0.156'
        ]
        
        for entry in log_entries:
            f.write(entry + '\n')
        
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_pdf_file():
    """Create a temporary PDF file for testing."""
    # For testing, we'll create a simple text file with PDF extension
    # In real tests, you might want to create an actual PDF
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pdf', delete=False) as f:
        f.write("Sample PDF content for testing\n")
        f.write("CPU Usage: 45.2%\n")
        f.write("Memory: 8GB\n")
        f.write("Configuration: p5-php\n")
        
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_ssh_connection():
    """Mock SSH connection for testing."""
    connection = AsyncMock()
    connection.connect.return_value = True
    connection.execute_command.return_value = "test output"
    connection.close.return_value = None
    return connection


@pytest.fixture
def sample_configuration_matrix():
    """Sample configuration matrix for testing."""
    return pd.DataFrame([
        {
            "name": "p0",
            "tier": 0,
            "cpu_limit": 0.5,
            "memory_limit": 512,
            "specialization": None
        },
        {
            "name": "p1",
            "tier": 1,
            "cpu_limit": 1.0,
            "memory_limit": 1024,
            "specialization": None
        },
        {
            "name": "p2-php",
            "tier": 2,
            "cpu_limit": 2.0,
            "memory_limit": 2048,
            "specialization": "php"
        },
        {
            "name": "p3-db",
            "tier": 3,
            "cpu_limit": 4.0,
            "memory_limit": 4096,
            "specialization": "db"
        }
    ])


@pytest.fixture
def temp_matrix_file(sample_configuration_matrix):
    """Create temporary configuration matrix file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        sample_configuration_matrix.to_csv(f.name, index=False)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Setup test environment."""
    # Set test environment variables
    monkeypatch.setenv("LOG_LEVEL", "ERROR")  # Reduce log noise in tests
    monkeypatch.setenv("SSH_KEY_PATH", "~/.ssh/test_rsa")
    monkeypatch.setenv("DEFAULT_SSH_USER", "testuser")
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.75")