"""Test worker implementations."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, mock_open
import tempfile
import os

from capacity_planner.workers.base import BaseWorker
from capacity_planner.workers.data_processing import (
    SSHWorker, TerminalWorker, CSVWorker, LogWorker, PDFWorker
)
from capacity_planner.models.data_models import WorkerTask, DataSource, DataSourceType


class TestBaseWorker:
    """Test base worker functionality."""
    
    class TestWorker(BaseWorker):
        """Test implementation of base worker."""
        
        async def process(self, task):
            return {"test": "result"}
    
    @pytest.mark.asyncio
    async def test_worker_lifecycle(self):
        """Test worker start/stop lifecycle."""
        worker = self.TestWorker()
        
        assert not worker.is_running()
        
        await worker.start()
        assert worker.is_running()
        
        await worker.stop()
        assert not worker.is_running()
    
    @pytest.mark.asyncio
    async def test_task_execution(self, sample_worker_task):
        """Test task execution."""
        worker = self.TestWorker()
        
        result_task = await worker.execute(sample_worker_task)
        
        assert result_task.status == "completed"
        assert result_task.result == {"test": "result"}
        assert result_task.error is None
    
    @pytest.mark.asyncio
    async def test_task_execution_failure(self, sample_worker_task):
        """Test task execution with failure."""
        class FailingWorker(BaseWorker):
            async def process(self, task):
                raise ValueError("Test error")
        
        worker = FailingWorker()
        result_task = await worker.execute(sample_worker_task)
        
        assert result_task.status == "failed"
        assert result_task.result is None
        assert result_task.error == "Test error"


class TestSSHWorker:
    """Test SSH worker."""
    
    @pytest.mark.asyncio
    async def test_ssh_worker_initialization(self, sample_ssh_config):
        """Test SSH worker initialization."""
        worker = SSHWorker(sample_ssh_config)
        
        assert worker.ssh_config == sample_ssh_config
        assert worker.connection is None
    
    @pytest.mark.asyncio
    @patch('capacity_planner.workers.data_processing.ssh_worker.SSHConnection')
    async def test_connect_to_pod(self, mock_ssh_connection_class, sample_ssh_config):
        """Test connecting to a specific pod."""
        mock_connection = AsyncMock()
        mock_connection.connect.return_value = True
        mock_ssh_connection_class.return_value = mock_connection
        
        worker = SSHWorker(sample_ssh_config)
        result = await worker.connect_to_pod(5)
        
        assert result is True
        assert worker.ssh_config.hostname == "pod-5.wpengine.com"
        assert worker.ssh_config.pod_number == 5
    
    @pytest.mark.asyncio
    @patch('capacity_planner.workers.data_processing.ssh_worker.SSHConnection')
    async def test_collect_system_metrics(self, mock_ssh_connection_class, sample_ssh_config):
        """Test system metrics collection."""
        mock_connection = AsyncMock()
        mock_connection.execute_command.side_effect = [
            "45.2",  # CPU usage
            "8589934592 5905580032 2684354560",  # Memory info
            "107374182400 37040652288 70333894112 35%",  # Disk info
            " 1.23, 1.45, 1.67",  # Load average
            "145",  # Total processes
            "3",   # MySQL processes
            "12",  # PHP processes
            "2",   # Nginx processes
            "0"    # Apache processes
        ]
        mock_ssh_connection_class.return_value = mock_connection
        
        worker = SSHWorker(sample_ssh_config)
        worker.connection = mock_connection
        
        metrics = await worker.collect_system_metrics()
        
        assert metrics.hostname == "pod-1.wpengine.com"
        assert metrics.cpu_usage == 45.2
        assert metrics.memory_total == 8589934592
        assert metrics.disk_usage == 35.0
        assert metrics.processes["total"] == 145
        assert metrics.processes["mysql"] == 3
    
    @pytest.mark.asyncio
    @patch('capacity_planner.workers.data_processing.ssh_worker.SSHConnection')
    async def test_collect_install_logs(self, mock_ssh_connection_class, sample_ssh_config):
        """Test install log collection."""
        mock_connection = AsyncMock()
        
        # Setup more comprehensive mock responses for all potential calls
        responses = []
        
        # For each of the 3 log paths tested
        for log_path in [
            "/var/log/nginx/testinstall.apachestyle.log",
            "/var/log/nginx/testinstall.access.log", 
            "/var/log/apache2/testinstall.access.log"
        ]:
            if "apachestyle" in log_path:
                # First log exists and has content
                responses.extend([
                    "exists",  # Main file exists
                    "sample log content line 1\nsample log content line 2",  # Content
                    "exists",  # .1 file exists
                    "more log content\nfrom rotated file",  # .1 content
                    "missing",  # .2.gz doesn't exist
                ])
            else:
                # Other logs don't exist
                responses.append("missing")
        
        mock_connection.execute_command.side_effect = responses
        mock_ssh_connection_class.return_value = mock_connection
        
        worker = SSHWorker(sample_ssh_config)
        worker.connection = mock_connection
        
        logs = await worker.collect_install_logs("testinstall")
        
        assert len(logs) >= 2
        assert "/var/log/nginx/testinstall.apachestyle.log" in logs
        assert "sample log content" in logs["/var/log/nginx/testinstall.apachestyle.log"]
    
    @pytest.mark.asyncio
    async def test_analyze_logs(self, sample_ssh_config):
        """Test log analysis."""
        worker = SSHWorker(sample_ssh_config)
        
        log_content = """192.168.1.1 - - [01/Jan/2024:10:00:00 +0000] "GET / HTTP/1.1" 200 1234 0.123
192.168.1.2 - - [01/Jan/2024:10:00:01 +0000] "GET /page1 HTTP/1.1" 200 5678 0.089
192.168.1.3 - - [01/Jan/2024:10:00:02 +0000] "POST /api/data HTTP/1.1" 500 0 2.345
192.168.1.1 - - [01/Jan/2024:10:00:03 +0000] "GET /image.jpg HTTP/1.1" 404 0 0.012"""
        
        analysis = await worker.analyze_logs(log_content, "access")
        
        assert analysis.total_requests == 4
        assert analysis.status_codes["200"] == 2
        assert analysis.status_codes["500"] == 1
        assert analysis.status_codes["404"] == 1
        assert "192.168.1.1" in analysis.top_ips


class TestTerminalWorker:
    """Test terminal worker."""
    
    @pytest.mark.asyncio
    async def test_terminal_worker_initialization(self):
        """Test terminal worker initialization."""
        worker = TerminalWorker()
        assert worker.name == "TerminalWorker"
    
    @pytest.mark.asyncio
    @patch('capacity_planner.workers.data_processing.terminal_worker.psutil')
    async def test_collect_local_system_info(self, mock_psutil):
        """Test local system info collection."""
        # Mock psutil responses
        mock_psutil.cpu_percent.return_value = 45.2
        mock_psutil.virtual_memory.return_value = Mock(
            total=8589934592, available=2684354560, percent=67.8, used=5905580032, free=2684354560
        )
        mock_psutil.disk_usage.return_value = Mock(
            total=107374182400, used=37040652288, free=70333894112, percent=34.5
        )
        mock_psutil.getloadavg.return_value = (1.23, 1.45, 1.67)
        mock_psutil.pids.return_value = list(range(145))
        mock_psutil.process_iter.return_value = [
            Mock(info={'name': 'python3'}),
            Mock(info={'name': 'node'}),
            Mock(info={'name': 'dockerd'})
        ]
        mock_psutil.net_io_counters.return_value = Mock(
            bytes_sent=1000000, bytes_recv=2000000, packets_sent=500, packets_recv=1000
        )
        
        worker = TerminalWorker()
        metrics = await worker.collect_local_system_info()
        
        assert metrics.cpu_usage == 45.2
        assert metrics.memory_usage == 67.8
        assert metrics.disk_usage == 34.5
        assert metrics.processes["total"] == 145
        assert metrics.network_io["bytes_sent"] == 1000000
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_shell')
    async def test_execute_command(self, mock_subprocess):
        """Test command execution."""
        # Mock successful command execution
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"test output", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        worker = TerminalWorker()
        result = await worker.execute_command("echo test")
        
        assert result == "test output"
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_shell')
    async def test_execute_command_failure(self, mock_subprocess):
        """Test command execution failure."""
        # Mock failed command execution
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"command not found")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process
        
        worker = TerminalWorker()
        
        with pytest.raises(RuntimeError, match="Command failed"):
            await worker.execute_command("nonexistent_command")


class TestCSVWorker:
    """Test CSV worker."""
    
    @pytest.mark.asyncio
    async def test_csv_worker_initialization(self):
        """Test CSV worker initialization."""
        worker = CSVWorker()
        assert worker.name == "CSVWorker"
    
    @pytest.mark.asyncio
    async def test_read_csv(self, temp_csv_file):
        """Test CSV file reading."""
        worker = CSVWorker()
        df = await worker.read_csv(temp_csv_file)
        
        assert len(df) == 4
        assert "timestamp" in df.columns
        assert "cpu_usage" in df.columns
        assert "memory_usage" in df.columns
        assert "requests" in df.columns
    
    @pytest.mark.asyncio
    async def test_analyze_usage_data(self, temp_csv_file):
        """Test usage data analysis."""
        worker = CSVWorker()
        df = await worker.read_csv(temp_csv_file)
        analysis = await worker.analyze_usage_data(df)
        
        assert analysis["row_count"] == 4
        assert "cpu_usage" in analysis["columns"]
        assert "cpu_usage" in analysis["metrics"]
        assert "mean" in analysis["metrics"]["cpu_usage"]
        assert analysis["metrics"]["cpu_usage"]["mean"] > 0
    
    @pytest.mark.asyncio
    async def test_process_task(self, temp_csv_file):
        """Test CSV task processing."""
        worker = CSVWorker()
        
        task = WorkerTask(
            task_id="csv-test",
            worker_type="csv",
            data_source=DataSource(type=DataSourceType.CSV, path=temp_csv_file),
            parameters={"type": "usage"}
        )
        
        result = await worker.process(task)
        
        assert result["file_path"] == temp_csv_file
        assert result["row_count"] == 4
        assert result["task_type"] == "usage"
        assert "analysis" in result


class TestLogWorker:
    """Test log worker."""
    
    @pytest.mark.asyncio
    async def test_log_worker_initialization(self):
        """Test log worker initialization."""
        worker = LogWorker()
        assert worker.name == "LogWorker"
    
    @pytest.mark.asyncio
    async def test_read_log_file(self, temp_log_file):
        """Test log file reading."""
        worker = LogWorker()
        lines = await worker.read_log_file(temp_log_file)
        
        assert len(lines) == 5
        assert "192.168.1.1" in lines[0]
        assert "GET /" in lines[0]
    
    @pytest.mark.asyncio
    async def test_parse_access_log(self, temp_log_file):
        """Test access log parsing."""
        worker = LogWorker()
        lines = await worker.read_log_file(temp_log_file)
        analysis = await worker.parse_access_log(lines)
        
        assert analysis.total_requests == 5
        assert analysis.status_codes["200"] == 3
        assert analysis.status_codes["500"] == 1
        assert analysis.status_codes["404"] == 1
        assert len(analysis.top_ips) > 0
    
    @pytest.mark.asyncio
    async def test_detect_log_type(self):
        """Test log type detection."""
        worker = LogWorker()
        
        # Test access log detection
        access_lines = [
            'GET / HTTP/1.1" 200 1234',
            'POST /api HTTP/1.1" 500 0'
        ]
        log_type = await worker.detect_log_type(access_lines)
        assert log_type == "access"
        
        # Test error log detection
        error_lines = [
            'ERROR: Database connection failed',
            'WARNING: High memory usage'
        ]
        log_type = await worker.detect_log_type(error_lines)
        assert log_type == "error"
    
    @pytest.mark.asyncio
    async def test_process_task(self, temp_log_file):
        """Test log task processing."""
        worker = LogWorker()
        
        task = WorkerTask(
            task_id="log-test",
            worker_type="log",
            data_source=DataSource(type=DataSourceType.LOG, path=temp_log_file),
            parameters={"format": "auto"}
        )
        
        result = await worker.process(task)
        
        assert result["file_path"] == temp_log_file
        assert result["lines_processed"] == 5
        assert result["log_type"] == "access"
        assert "analysis" in result


class TestPDFWorker:
    """Test PDF worker."""
    
    @pytest.mark.asyncio
    async def test_pdf_worker_initialization(self):
        """Test PDF worker initialization."""
        worker = PDFWorker()
        assert worker.name == "PDFWorker"
    
    @pytest.mark.asyncio
    @patch('capacity_planner.workers.data_processing.pdf_worker.PyPDF2.PdfReader')
    async def test_extract_text_from_pdf(self, mock_pdf_reader, temp_pdf_file):
        """Test PDF text extraction."""
        # Mock PDF reader
        mock_page = Mock()
        mock_page.extract_text.return_value = "Sample PDF content\nCPU Usage: 45.2%"
        
        mock_reader = Mock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        worker = PDFWorker()
        text = await worker.extract_text_from_pdf(temp_pdf_file)
        
        assert "Sample PDF content" in text
        assert "CPU Usage" in text
    
    @pytest.mark.asyncio
    async def test_extract_metrics_from_text(self):
        """Test metrics extraction from text."""
        worker = PDFWorker()
        
        text = """
        System Performance Report
        CPU Usage: 45.2%
        Memory Usage: 67.8%
        Total Requests: 10,000
        Response Time: 0.234 seconds
        Error Rate: 2.5%
        """
        
        metrics = await worker.extract_metrics_from_text(text)
        
        assert "cpu" in metrics
        assert metrics["cpu"]["values"] == [45.2]
        assert "memory" in metrics
        assert metrics["memory"]["values"] == [67.8]
        assert "requests" in metrics
        assert "response_time" in metrics
        assert "error_rate" in metrics
    
    @pytest.mark.asyncio
    @patch('capacity_planner.workers.data_processing.pdf_worker.PyPDF2.PdfReader')
    async def test_process_task(self, mock_pdf_reader, temp_pdf_file):
        """Test PDF task processing."""
        # Mock PDF reader
        mock_page = Mock()
        mock_page.extract_text.return_value = "CPU Usage: 45.2%\nMemory: 8GB\nConfiguration: p5-php"
        
        mock_reader = Mock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        worker = PDFWorker()
        
        task = WorkerTask(
            task_id="pdf-test",
            worker_type="pdf",
            data_source=DataSource(type=DataSourceType.PDF, path=temp_pdf_file),
            parameters={}
        )
        
        result = await worker.process(task)
        
        assert result["file_path"] == temp_pdf_file
        assert result["text_length"] > 0
        assert "metrics" in result
        assert "configuration" in result