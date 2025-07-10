"""Test utility functions."""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from capacity_planner.utils.config import Config
from capacity_planner.utils.logging import setup_logging, get_logger
from capacity_planner.utils.ssh_utils import SSHConnection
from capacity_planner.utils.validation import validate_ssh_config, validate_data_source
from capacity_planner.models.data_models import SSHConfig, DataSource, DataSourceType


class TestConfig:
    """Test configuration management."""
    
    def test_config_initialization_with_defaults(self):
        """Test config initialization with default values."""
        config = Config()
        
        assert config.get("log_level") == "ERROR"  # Set by test environment
        assert config.get("confidence_threshold") == 0.75
        assert config.get("max_workers") == 10
        assert isinstance(config.get("streamlit_port"), int)
    
    def test_config_initialization_with_env_file(self, monkeypatch):
        """Test config initialization with environment file."""
        # Clear the environment variables so .env file takes precedence
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("CONFIDENCE_THRESHOLD", raising=False)
        monkeypatch.delenv("MAX_WORKERS", raising=False)
        
        # Create temporary .env file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("LOG_LEVEL=DEBUG\n")
            f.write("CONFIDENCE_THRESHOLD=0.80\n")
            f.write("MAX_WORKERS=5\n")
            env_file = f.name
        
        try:
            config = Config(env_file)
            
            assert config.get("log_level") == "DEBUG"
            assert config.get("confidence_threshold") == 0.80
            assert config.get("max_workers") == 5
        finally:
            os.unlink(env_file)
    
    def test_config_get_set(self):
        """Test config get/set operations."""
        config = Config()
        
        # Test get with default
        assert config.get("nonexistent_key", "default") == "default"
        
        # Test set and get
        config.set("test_key", "test_value")
        assert config.get("test_key") == "test_value"
    
    def test_config_properties(self):
        """Test config properties."""
        config = Config()
        
        # Test path expansion
        assert "~" not in config.ssh_key_path
        
        # Test property access
        assert isinstance(config.confidence_threshold, float)
        assert isinstance(config.max_workers, int)
        assert isinstance(config.log_level, str)
    
    def test_config_to_dict(self):
        """Test config serialization to dictionary."""
        config = Config()
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert "log_level" in config_dict
        assert "confidence_threshold" in config_dict
        assert "max_workers" in config_dict


class TestLogging:
    """Test logging utilities."""
    
    def test_setup_logging_default(self):
        """Test logging setup with default parameters."""
        logger = setup_logging()
        
        assert logger.name == "capacity_planner"
        assert len(logger.handlers) > 0
    
    def test_setup_logging_with_file(self):
        """Test logging setup with file output."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            log_file = f.name
        
        try:
            logger = setup_logging(
                log_level="DEBUG",
                log_file=log_file,
                console_output=False
            )
            
            # Should have file handler
            assert len(logger.handlers) == 1
            assert hasattr(logger.handlers[0], 'baseFilename')
            
            # Test logging
            logger.info("Test message")
            
            # Check file was created
            assert os.path.exists(log_file)
            
        finally:
            if os.path.exists(log_file):
                os.unlink(log_file)
    
    def test_get_logger(self):
        """Test getting named logger."""
        logger = get_logger("test_module")
        
        assert logger.name == "capacity_planner.test_module"
    
    def test_setup_logging_custom_format(self):
        """Test logging setup with custom format."""
        custom_format = "%(name)s - %(levelname)s - %(message)s"
        
        logger = setup_logging(
            log_format=custom_format,
            console_output=True
        )
        
        # Check that handler was configured
        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        assert handler.formatter is not None


class TestSSHUtils:
    """Test SSH utilities."""
    
    def test_ssh_connection_initialization(self):
        """Test SSH connection initialization."""
        conn = SSHConnection(
            hostname="test.example.com",
            username="testuser",
            key_filename="~/.ssh/id_rsa",
            port=2222,
            timeout=60
        )
        
        assert conn.hostname == "test.example.com"
        assert conn.username == "testuser"
        assert conn.key_filename == "~/.ssh/id_rsa"
        assert conn.port == 2222
        assert conn.timeout == 60
        assert conn.client is None
    
    @pytest.mark.asyncio
    @patch('paramiko.SSHClient')
    async def test_ssh_connection_success(self, mock_ssh_client):
        """Test successful SSH connection."""
        mock_client = Mock()
        mock_transport = Mock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_client.return_value = mock_client
        
        conn = SSHConnection("test.example.com", "testuser")
        result = await conn.connect()
        
        assert result is True
        assert conn.client is not None
        mock_client.set_missing_host_key_policy.assert_called_once()
        mock_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('paramiko.SSHClient')
    async def test_ssh_connection_failure(self, mock_ssh_client):
        """Test SSH connection failure."""
        mock_client = Mock()
        mock_client.connect.side_effect = Exception("Connection failed")
        mock_ssh_client.return_value = mock_client
        
        conn = SSHConnection("test.example.com", "testuser")
        
        with pytest.raises(ConnectionError, match="SSH connection failed"):
            await conn.connect()
    
    @pytest.mark.asyncio
    @patch('paramiko.SSHClient')
    async def test_ssh_execute_command(self, mock_ssh_client):
        """Test SSH command execution."""
        mock_client = Mock()
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"command output"
        mock_stderr.read.return_value = b""
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        mock_ssh_client.return_value = mock_client
        
        conn = SSHConnection("test.example.com", "testuser")
        conn.client = mock_client
        
        result = await conn.execute_command("echo test")
        
        assert result == "command output"
        mock_client.exec_command.assert_called_once_with("echo test", timeout=30)
    
    @pytest.mark.asyncio
    @patch('paramiko.SSHClient')
    async def test_ssh_execute_command_failure(self, mock_ssh_client):
        """Test SSH command execution failure."""
        mock_client = Mock()
        mock_stdin = Mock()
        mock_stdout = Mock()
        mock_stderr = Mock()
        
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"command error"
        
        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        mock_ssh_client.return_value = mock_client
        
        conn = SSHConnection("test.example.com", "testuser")
        conn.client = mock_client
        
        with pytest.raises(RuntimeError, match="Command execution failed"):
            await conn.execute_command("false")
    
    @pytest.mark.asyncio
    @patch('paramiko.SSHClient')
    async def test_ssh_download_file(self, mock_ssh_client):
        """Test SSH file download."""
        mock_client = Mock()
        mock_sftp = Mock()
        mock_client.open_sftp.return_value = mock_sftp
        mock_ssh_client.return_value = mock_client
        
        conn = SSHConnection("test.example.com", "testuser")
        conn.client = mock_client
        
        with tempfile.NamedTemporaryFile() as temp_file:
            result = await conn.download_file("/remote/path", temp_file.name)
            
            assert result is True
            mock_sftp.get.assert_called_once_with("/remote/path", temp_file.name)
            mock_sftp.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ssh_context_manager(self):
        """Test SSH connection as context manager."""
        with patch('paramiko.SSHClient') as mock_ssh_client:
            mock_client = Mock()
            mock_transport = Mock()
            mock_transport.is_active.return_value = True
            mock_client.get_transport.return_value = mock_transport
            mock_ssh_client.return_value = mock_client
            
            async with SSHConnection("test.example.com", "testuser") as conn:
                assert conn.client is not None
            
            mock_client.close.assert_called_once()


class TestValidation:
    """Test validation utilities."""
    
    def test_validate_ssh_config_valid(self):
        """Test validating valid SSH configuration."""
        ssh_config = SSHConfig(
            hostname="test.example.com",
            username="testuser",
            port=22
        )
        
        is_valid, error = validate_ssh_config(ssh_config)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_ssh_config_missing_hostname(self):
        """Test validating SSH config with missing hostname."""
        # Use construct to bypass model validation
        ssh_config = SSHConfig.model_construct(
            hostname="",
            username="testuser"
        )
        
        is_valid, error = validate_ssh_config(ssh_config)
        
        assert is_valid is False
        assert "hostname" in error.lower()
    
    def test_validate_ssh_config_missing_username(self):
        """Test validating SSH config with missing username."""
        ssh_config = SSHConfig.model_construct(
            hostname="test.example.com",
            username=""
        )
        
        is_valid, error = validate_ssh_config(ssh_config)
        
        assert is_valid is False
        assert "username" in error.lower()
    
    def test_validate_ssh_config_invalid_port(self):
        """Test validating SSH config with invalid port."""
        ssh_config = SSHConfig(
            hostname="test.example.com",
            username="testuser",
            port=0
        )
        
        is_valid, error = validate_ssh_config(ssh_config)
        
        assert is_valid is False
        assert "port" in error.lower()
    
    def test_validate_ssh_config_invalid_key_file(self):
        """Test validating SSH config with non-existent key file."""
        ssh_config = SSHConfig(
            hostname="test.example.com",
            username="testuser",
            key_path="/nonexistent/key"
        )
        
        is_valid, error = validate_ssh_config(ssh_config)
        
        assert is_valid is False
        assert "not found" in error.lower()
    
    def test_validate_data_source_valid_csv(self, temp_csv_file):
        """Test validating valid CSV data source."""
        data_source = DataSource(
            type=DataSourceType.CSV,
            path=temp_csv_file
        )
        
        is_valid, error = validate_data_source(data_source)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_data_source_nonexistent_file(self):
        """Test validating data source with non-existent file."""
        data_source = DataSource(
            type=DataSourceType.CSV,
            path="/nonexistent/file.csv"
        )
        
        is_valid, error = validate_data_source(data_source)
        
        assert is_valid is False
        assert "not found" in error.lower()
    
    def test_validate_data_source_wrong_extension(self, temp_csv_file):
        """Test validating data source with wrong file extension."""
        # Rename CSV file to have wrong extension
        wrong_ext_file = temp_csv_file.replace('.csv', '.txt')
        os.rename(temp_csv_file, wrong_ext_file)
        
        try:
            data_source = DataSource(
                type=DataSourceType.CSV,
                path=wrong_ext_file
            )
            
            is_valid, error = validate_data_source(data_source)
            
            assert is_valid is False
            assert "extension" in error.lower()
        finally:
            if os.path.exists(wrong_ext_file):
                os.unlink(wrong_ext_file)
    
    def test_validate_data_source_with_ssh_config(self):
        """Test validating data source with SSH configuration."""
        ssh_config = SSHConfig(
            hostname="test.example.com",
            username="testuser"
        )
        
        data_source = DataSource(
            type=DataSourceType.SSH,
            ssh_config=ssh_config
        )
        
        is_valid, error = validate_data_source(data_source)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_data_source_with_invalid_ssh_config(self):
        """Test validating data source with invalid SSH configuration."""
        ssh_config = SSHConfig.model_construct(
            hostname="",  # Invalid: empty hostname
            username="testuser"
        )
        
        data_source = DataSource(
            type=DataSourceType.SSH,
            ssh_config=ssh_config
        )
        
        is_valid, error = validate_data_source(data_source)
        
        assert is_valid is False
        assert "ssh configuration invalid" in error.lower()