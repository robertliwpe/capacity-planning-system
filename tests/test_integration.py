"""Integration tests for the complete system."""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock

from capacity_planner.orchestrator.main import CapacityPlanningOrchestrator
from capacity_planner.models.data_models import (
    AnalysisRequest, DataSource, DataSourceType, SSHConfig
)
from capacity_planner.utils.config import Config


class TestSystemIntegration:
    """Test complete system integration."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_local_file_analysis(self, temp_csv_file, temp_log_file):
        """Test end-to-end analysis with local files."""
        # Create a minimal config
        config = Config()
        config.set("config_matrix_path", "/nonexistent/path")  # Will use fallback
        
        orchestrator = CapacityPlanningOrchestrator(config)
        
        try:
            await orchestrator.start()
            
            # Create analysis request with local files
            request = AnalysisRequest(
                data_sources=[
                    DataSource(type=DataSourceType.CSV, path=temp_csv_file),
                    DataSource(type=DataSourceType.LOG, path=temp_log_file)
                ],
                confidence_threshold=0.5,  # Lower threshold for testing
                output_format="markdown"
            )
            
            result = await orchestrator.analyze(request)
            
            # Verify result structure
            assert result.status == "completed"
            assert result.request_id is not None
            assert result.execution_time > 0
            assert isinstance(result.recommendations, list)
            assert result.report is not None
            assert "# Capacity Planning Analysis Report" in result.report
            
        finally:
            await orchestrator.stop()
    
    @pytest.mark.asyncio
    @patch('capacity_planner.workers.data_processing.ssh_worker.SSHConnection')
    async def test_end_to_end_ssh_analysis(self, mock_ssh_connection_class):
        """Test end-to-end analysis with SSH data sources."""
        # Mock SSH connection
        mock_connection = AsyncMock()
        mock_connection.connect.return_value = True
        mock_connection.execute_command.side_effect = [
            "45.2",  # CPU usage
            "8589934592 5905580032 2684354560",  # Memory info
            "107374182400 37040652288 70333894112 35%",  # Disk info
            " 1.23, 1.45, 1.67",  # Load average
            "145", "3", "12", "2", "0",  # Process counts
            "exists",  # Log file exists check
            "192.168.1.1 - - [01/Jan/2024:10:00:00 +0000] \"GET / HTTP/1.1\" 200 1234 0.123",  # Log content
            "missing",  # .1 file doesn't exist
        ]
        mock_ssh_connection_class.return_value = mock_connection
        
        config = Config()
        config.set("config_matrix_path", "/nonexistent/path")  # Will use fallback
        
        orchestrator = CapacityPlanningOrchestrator(config)
        
        try:
            await orchestrator.start()
            
            # Create SSH configuration
            ssh_config = SSHConfig(
                hostname="pod-1.wpengine.com",
                username="testuser",
                key_path="~/.ssh/id_rsa",
                pod_number=1
            )
            
            # Create analysis request with SSH data source
            request = AnalysisRequest(
                data_sources=[
                    DataSource(
                        type=DataSourceType.SSH,
                        ssh_config=ssh_config,
                        install_names=["testinstall"]
                    )
                ],
                confidence_threshold=0.5,
                output_format="markdown"
            )
            
            result = await orchestrator.analyze(request)
            
            # Verify result
            assert result.status == "completed"
            assert len(result.recommendations) > 0
            assert result.server_metrics is not None
            assert len(result.server_metrics) > 0
            assert result.report is not None
            
            # Verify SSH connection was used
            mock_connection.connect.assert_called()
            assert mock_connection.execute_command.call_count > 0
            
        finally:
            await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_data_source(self):
        """Test error handling with invalid data sources."""
        config = Config()
        orchestrator = CapacityPlanningOrchestrator(config)
        
        try:
            await orchestrator.start()
            
            # Create request with non-existent file
            request = AnalysisRequest(
                data_sources=[
                    DataSource(type=DataSourceType.CSV, path="/nonexistent/file.csv")
                ]
            )
            
            result = await orchestrator.analyze(request)
            
            # Should handle error gracefully
            assert result.status == "failed"
            assert len(result.errors) > 0
            assert result.execution_time > 0
            
        finally:
            await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_mixed_data_sources(self, temp_csv_file):
        """Test analysis with mixed data sources."""
        config = Config()
        config.set("config_matrix_path", "/nonexistent/path")
        
        orchestrator = CapacityPlanningOrchestrator(config)
        
        try:
            await orchestrator.start()
            
            # Create request with mixed sources (one valid, one invalid)
            request = AnalysisRequest(
                data_sources=[
                    DataSource(type=DataSourceType.CSV, path=temp_csv_file),
                    DataSource(type=DataSourceType.LOG, path="/nonexistent/log.log")
                ],
                confidence_threshold=0.5
            )
            
            result = await orchestrator.analyze(request)
            
            # Should fail due to missing file, but capture the error
            assert result.status == "failed"
            assert len(result.errors) > 0  # Should have error for missing file
            assert "nonexistent/log.log" in str(result.errors)  # Specific error message
            
        finally:
            await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_configuration_recommendation_flow(self, temp_csv_file):
        """Test the complete configuration recommendation flow."""
        config = Config()
        config.set("config_matrix_path", "/nonexistent/path")
        
        orchestrator = CapacityPlanningOrchestrator(config)
        
        try:
            await orchestrator.start()
            
            request = AnalysisRequest(
                data_sources=[
                    DataSource(type=DataSourceType.CSV, path=temp_csv_file)
                ],
                confidence_threshold=0.1  # Very low threshold to ensure recommendations
            )
            
            result = await orchestrator.analyze(request)
            
            assert result.status == "completed"
            
            if result.recommendations:
                rec = result.recommendations[0]
                
                # Verify recommendation structure
                assert rec.config_name is not None
                assert isinstance(rec.tier, int)
                assert 0 <= rec.confidence_score <= 1
                assert isinstance(rec.reasoning, list)
                assert isinstance(rec.resource_specs, dict)
                assert isinstance(rec.estimated_capacity, dict)
                
                # Verify resource specs structure
                if "cpu" in rec.resource_specs:
                    cpu_spec = rec.resource_specs["cpu"]
                    assert "limit" in cpu_spec
                    assert isinstance(cpu_spec["limit"], (int, float))
                
                # Verify estimated capacity
                if "requests_per_second" in rec.estimated_capacity:
                    rps = rec.estimated_capacity["requests_per_second"]
                    assert isinstance(rps, (int, float))
                    assert rps >= 0
            
        finally:
            await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_report_generation_formats(self, temp_csv_file):
        """Test report generation in different formats."""
        config = Config()
        config.set("config_matrix_path", "/nonexistent/path")
        
        orchestrator = CapacityPlanningOrchestrator(config)
        
        try:
            await orchestrator.start()
            
            data_sources = [DataSource(type=DataSourceType.CSV, path=temp_csv_file)]
            
            # Test markdown format
            md_request = AnalysisRequest(
                data_sources=data_sources,
                output_format="markdown"
            )
            md_result = await orchestrator.analyze(md_request)
            
            assert md_result.report is not None
            assert "# Capacity Planning Analysis Report" in md_result.report
            
            # Test JSON format
            json_request = AnalysisRequest(
                data_sources=data_sources,
                output_format="json"
            )
            json_result = await orchestrator.analyze(json_request)
            
            assert json_result.report is not None
            # Should be valid JSON
            import json
            parsed = json.loads(json_result.report)
            assert "recommendations" in parsed
            
            # Test text format
            text_request = AnalysisRequest(
                data_sources=data_sources,
                output_format="text"
            )
            text_result = await orchestrator.analyze(text_request)
            
            assert text_result.report is not None
            assert "CAPACITY PLANNING ANALYSIS REPORT" in text_result.report
            
        finally:
            await orchestrator.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_analysis_requests(self, temp_csv_file):
        """Test handling multiple concurrent analysis requests."""
        config = Config()
        config.set("config_matrix_path", "/nonexistent/path")
        config.set("max_workers", 2)  # Limited workers for testing
        
        orchestrator = CapacityPlanningOrchestrator(config)
        
        try:
            await orchestrator.start()
            
            # Create multiple concurrent requests
            requests = [
                AnalysisRequest(
                    data_sources=[DataSource(type=DataSourceType.CSV, path=temp_csv_file)],
                    confidence_threshold=0.5
                )
                for _ in range(3)
            ]
            
            # Run them concurrently
            results = await asyncio.gather(
                *[orchestrator.analyze(req) for req in requests],
                return_exceptions=True
            )
            
            # All should complete successfully
            assert len(results) == 3
            for result in results:
                assert not isinstance(result, Exception)
                assert result.status == "completed"
                assert result.request_id is not None
                
            # Each should have unique request ID
            request_ids = [r.request_id for r in results]
            assert len(set(request_ids)) == 3
            
        finally:
            await orchestrator.stop()


class TestCLIIntegration:
    """Test CLI integration (without actually running CLI)."""
    
    def test_cli_imports(self):
        """Test that CLI imports work correctly."""
        from capacity_planner.cli.commands import cli
        assert cli is not None
    
    @patch('capacity_planner.cli.commands.asyncio.run')
    @patch('capacity_planner.cli.commands.CapacityPlanningOrchestrator')
    def test_cli_analyze_command_structure(self, mock_orchestrator_class, mock_asyncio_run):
        """Test CLI analyze command structure."""
        from capacity_planner.cli.commands import analyze
        from click.testing import CliRunner
        
        # Mock the orchestrator
        mock_orchestrator = AsyncMock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        runner = CliRunner()
        
        # Test help output
        result = runner.invoke(analyze, ['--help'])
        assert result.exit_code == 0
        assert "Analyze capacity requirements" in result.output
        assert "--data-dir" in result.output
        assert "--pods" in result.output
        assert "--installs" in result.output


class TestGUIIntegration:
    """Test GUI integration (without actually running Streamlit)."""
    
    def test_gui_imports(self):
        """Test that GUI imports work correctly."""
        from capacity_planner.gui.app import main
        assert main is not None
    
    def test_gui_component_functions(self):
        """Test GUI helper functions."""
        from capacity_planner.gui.app import parse_pod_input
        
        # Test valid input
        assert parse_pod_input("1,2,3") == [1, 2, 3]
        assert parse_pod_input("1-3") == [1, 2, 3]
        assert parse_pod_input("1,3-5,7") == [1, 3, 4, 5, 7]
        
        # Test invalid input
        assert parse_pod_input("") == []
        assert parse_pod_input("invalid") == []


@pytest.mark.asyncio
async def test_complete_system_startup_shutdown():
    """Test complete system startup and shutdown."""
    config = Config()
    orchestrator = CapacityPlanningOrchestrator(config)
    
    # Test startup
    await orchestrator.start()
    assert orchestrator._running is True
    assert orchestrator.coordinator._running is True
    
    # Test shutdown
    await orchestrator.stop()
    assert orchestrator._running is False
    assert orchestrator.coordinator._running is False