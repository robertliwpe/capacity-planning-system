"""Test orchestrator components."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from capacity_planner.orchestrator.main import CapacityPlanningOrchestrator
from capacity_planner.orchestrator.task_analyzer import TaskAnalyzer, TaskComplexity
from capacity_planner.orchestrator.coordinator import WorkerCoordinator
from capacity_planner.models.data_models import (
    AnalysisRequest, DataSource, DataSourceType, SSHConfig, WorkerTask
)


class TestTaskAnalyzer:
    """Test task analyzer."""
    
    def test_task_analyzer_initialization(self):
        """Test task analyzer initialization."""
        analyzer = TaskAnalyzer()
        assert analyzer.logger is not None
    
    @pytest.mark.asyncio
    async def test_analyze_complexity_low(self):
        """Test low complexity analysis."""
        analyzer = TaskAnalyzer()
        
        data_sources = [
            DataSource(type=DataSourceType.CSV, path="/tmp/test.csv"),
            DataSource(type=DataSourceType.TERMINAL, metadata={"task_type": "system_info"})
        ]
        
        complexity = await analyzer.analyze_complexity(data_sources)
        assert complexity == TaskComplexity.LOW
    
    @pytest.mark.asyncio
    async def test_analyze_complexity_high(self):
        """Test high complexity analysis."""
        analyzer = TaskAnalyzer()
        
        data_sources = [
            DataSource(
                type=DataSourceType.SSH,
                ssh_config=SSHConfig(hostname="pod-1.wpengine.com", username="test"),
                install_names=["install1", "install2", "install3"]
            ),
            DataSource(
                type=DataSourceType.SSH,
                ssh_config=SSHConfig(hostname="pod-2.wpengine.com", username="test"),
                install_names=["install4", "install5"]
            ),
            DataSource(type=DataSourceType.PDF, path="/tmp/test.pdf"),
            DataSource(type=DataSourceType.LOG, path="/tmp/test.log")
        ]
        
        complexity = await analyzer.analyze_complexity(data_sources)
        assert complexity in [TaskComplexity.HIGH, TaskComplexity.VERY_HIGH]
    
    @pytest.mark.asyncio
    async def test_create_tasks(self):
        """Test task creation."""
        analyzer = TaskAnalyzer()
        
        data_sources = [
            DataSource(type=DataSourceType.CSV, path="/tmp/test.csv"),
            DataSource(
                type=DataSourceType.SSH,
                ssh_config=SSHConfig(hostname="pod-1.wpengine.com", username="test"),
                install_names=["install1"]
            )
        ]
        
        tasks = await analyzer.create_tasks(data_sources)
        
        assert len(tasks) == 2
        assert any(task.worker_type == "csv" for task in tasks)
        assert any(task.worker_type == "ssh" for task in tasks)
        
        # Check task priorities
        ssh_task = next(task for task in tasks if task.worker_type == "ssh")
        csv_task = next(task for task in tasks if task.worker_type == "csv")
        
        assert ssh_task.priority >= csv_task.priority
    
    @pytest.mark.asyncio
    async def test_estimate_execution_time(self):
        """Test execution time estimation."""
        analyzer = TaskAnalyzer()
        
        tasks = [
            WorkerTask(
                task_id="1",
                worker_type="ssh",
                data_source=DataSource(type=DataSourceType.SSH),
                parameters={"collect_logs": True}
            ),
            WorkerTask(
                task_id="2",
                worker_type="csv",
                data_source=DataSource(type=DataSourceType.CSV),
                parameters={}
            )
        ]
        
        estimated_time = await analyzer.estimate_execution_time(tasks)
        
        assert estimated_time > 0
        assert isinstance(estimated_time, float)


class TestWorkerCoordinator:
    """Test worker coordinator."""
    
    @pytest.mark.asyncio
    async def test_coordinator_lifecycle(self, mock_config):
        """Test coordinator start/stop lifecycle."""
        coordinator = WorkerCoordinator(mock_config)
        
        await coordinator.start()
        assert coordinator._running is True
        
        await coordinator.stop()
        assert coordinator._running is False
    
    @pytest.mark.asyncio
    @patch('capacity_planner.orchestrator.coordinator.TerminalWorker')
    async def test_execute_single_task(self, mock_terminal_worker, mock_config):
        """Test single task execution."""
        # Setup mock worker
        mock_worker_instance = AsyncMock()
        mock_worker_instance.execute.return_value = WorkerTask(
            task_id="test",
            worker_type="terminal",
            data_source=DataSource(type=DataSourceType.TERMINAL),
            status="completed",
            result={"test": "result"}
        )
        mock_terminal_worker.return_value = mock_worker_instance
        
        coordinator = WorkerCoordinator(mock_config)
        
        task = WorkerTask(
            task_id="test",
            worker_type="terminal",
            data_source=DataSource(type=DataSourceType.TERMINAL),
            parameters={"type": "system_info"}
        )
        
        result = await coordinator.execute_single_task(task)
        
        assert result.status == "completed"
        assert result.result == {"test": "result"}
    
    @pytest.mark.asyncio
    async def test_group_tasks_by_worker_type(self, mock_config):
        """Test task grouping by worker type."""
        coordinator = WorkerCoordinator(mock_config)
        
        tasks = [
            WorkerTask(
                task_id="1",
                worker_type="ssh",
                data_source=DataSource(type=DataSourceType.SSH),
                priority=3
            ),
            WorkerTask(
                task_id="2",
                worker_type="csv",
                data_source=DataSource(type=DataSourceType.CSV),
                priority=1
            ),
            WorkerTask(
                task_id="3",
                worker_type="ssh",
                data_source=DataSource(type=DataSourceType.SSH),
                priority=2
            )
        ]
        
        groups = coordinator._group_tasks_by_worker_type(tasks)
        
        assert "ssh" in groups
        assert "csv" in groups
        assert len(groups["ssh"]) == 2
        assert len(groups["csv"]) == 1
        
        # Check priority sorting (higher priority first)
        assert groups["ssh"][0].priority == 3
        assert groups["ssh"][1].priority == 2
    
    @pytest.mark.asyncio
    async def test_get_max_concurrent_for_worker_type(self, mock_config):
        """Test concurrent worker limits."""
        coordinator = WorkerCoordinator(mock_config)
        
        # SSH workers should be limited
        ssh_limit = coordinator._get_max_concurrent_for_worker_type("ssh")
        assert ssh_limit <= 3
        
        # Terminal workers can run more concurrently
        terminal_limit = coordinator._get_max_concurrent_for_worker_type("terminal")
        assert terminal_limit <= 5
        
        # Other workers have medium limits
        csv_limit = coordinator._get_max_concurrent_for_worker_type("csv")
        assert csv_limit <= 4


class TestCapacityPlanningOrchestrator:
    """Test main orchestrator."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, mock_config):
        """Test orchestrator initialization."""
        orchestrator = CapacityPlanningOrchestrator(mock_config)
        
        assert orchestrator.config == mock_config
        assert orchestrator.task_analyzer is not None
        assert orchestrator.coordinator is not None
        assert orchestrator.recommendation_engine is not None
        assert not orchestrator._running
    
    @pytest.mark.asyncio
    async def test_orchestrator_lifecycle(self, mock_config):
        """Test orchestrator start/stop lifecycle."""
        orchestrator = CapacityPlanningOrchestrator(mock_config)
        
        await orchestrator.start()
        assert orchestrator._running is True
        
        await orchestrator.stop()
        assert orchestrator._running is False
    
    @pytest.mark.asyncio
    @patch('capacity_planner.orchestrator.main.RecommendationEngine')
    @patch('capacity_planner.orchestrator.main.WorkerCoordinator')
    @patch('capacity_planner.orchestrator.main.TaskAnalyzer')
    async def test_analyze_success(self, mock_task_analyzer_class, mock_coordinator_class, 
                                  mock_recommendation_engine_class, mock_config, 
                                  sample_server_metrics, sample_log_analysis):
        """Test successful analysis."""
        # Setup mocks
        mock_task_analyzer = AsyncMock()
        mock_task_analyzer.analyze_complexity.return_value = TaskComplexity.MEDIUM
        mock_task_analyzer.create_tasks.return_value = [
            WorkerTask(
                task_id="test",
                worker_type="terminal",
                data_source=DataSource(type=DataSourceType.TERMINAL),
                status="completed",
                result={"metrics": sample_server_metrics}
            )
        ]
        mock_task_analyzer_class.return_value = mock_task_analyzer
        
        mock_coordinator = AsyncMock()
        mock_coordinator.execute_tasks.return_value = [
            WorkerTask(
                task_id="test",
                worker_type="terminal",
                data_source=DataSource(type=DataSourceType.TERMINAL),
                status="completed",
                result={"metrics": sample_server_metrics}
            )
        ]
        mock_coordinator_class.return_value = mock_coordinator
        
        from capacity_planner.models.data_models import ConfigurationRecommendation
        mock_recommendation_engine = AsyncMock()
        mock_recommendation_engine.generate_recommendations.return_value = [
            ConfigurationRecommendation(
                config_name="p5",
                tier=5,
                confidence_score=0.85,
                reasoning=["Test reasoning"],
                resource_specs={},
                estimated_capacity={}
            )
        ]
        mock_recommendation_engine_class.return_value = mock_recommendation_engine
        
        orchestrator = CapacityPlanningOrchestrator(mock_config)
        
        request = AnalysisRequest(
            data_sources=[
                DataSource(type=DataSourceType.TERMINAL, metadata={"task_type": "system_info"})
            ]
        )
        
        result = await orchestrator.analyze(request)
        
        assert result.status == "completed"
        assert len(result.recommendations) == 1
        assert result.recommendations[0].config_name == "p5"
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_analyze_failure(self, mock_config):
        """Test analysis failure handling."""
        orchestrator = CapacityPlanningOrchestrator(mock_config)
        
        # Create request with invalid data source
        request = AnalysisRequest(
            data_sources=[
                DataSource(type=DataSourceType.CSV, path="/nonexistent/file.csv")
            ]
        )
        
        result = await orchestrator.analyze(request)
        
        assert result.status == "failed"
        assert len(result.errors) > 0
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_generate_markdown_report(self, mock_config, sample_server_metrics, sample_log_analysis):
        """Test markdown report generation."""
        from capacity_planner.models.data_models import ConfigurationRecommendation
        
        orchestrator = CapacityPlanningOrchestrator(mock_config)
        
        recommendations = [
            ConfigurationRecommendation(
                config_name="p5-php",
                tier=5,
                specialization="php",
                confidence_score=0.85,
                reasoning=["High CPU usage detected", "PHP workload identified"],
                resource_specs={"cpu": {"limit": 8.0}},
                estimated_capacity={"requests_per_second": 400.0}
            )
        ]
        
        report = await orchestrator.generate_report(
            recommendations=recommendations,
            metrics=[sample_server_metrics],
            log_analyses=[sample_log_analysis],
            format="markdown"
        )
        
        assert "# Capacity Planning Analysis Report" in report
        assert "p5-php" in report
        assert "85" in report  # Should match 85.00% or 0.85
        assert "High CPU usage detected" in report
    
    @pytest.mark.asyncio
    async def test_generate_json_report(self, mock_config):
        """Test JSON report generation."""
        import json
        
        orchestrator = CapacityPlanningOrchestrator(mock_config)
        
        report = await orchestrator.generate_report(
            recommendations=[],
            metrics=[],
            log_analyses=[],
            format="json"
        )
        
        # Should be valid JSON
        parsed = json.loads(report)
        assert "recommendations" in parsed
        assert "metrics_count" in parsed
        assert "log_analyses_count" in parsed
    
    @pytest.mark.asyncio
    async def test_analyze_single_pod(self, mock_config):
        """Test single pod analysis."""
        orchestrator = CapacityPlanningOrchestrator(mock_config)
        
        ssh_config = SSHConfig(
            hostname="pod-1.wpengine.com",
            username="testuser",
            key_path="~/.ssh/id_rsa"
        )
        
        with patch.object(orchestrator, 'analyze') as mock_analyze:
            mock_analyze.return_value = Mock(status="completed", recommendations=[])
            
            result = await orchestrator.analyze_single_pod(
                pod_number=1,
                install_names=["test_install"],
                ssh_config=ssh_config.model_dump()
            )
            
            mock_analyze.assert_called_once()
            call_args = mock_analyze.call_args[0][0]  # Get the AnalysisRequest
            
            assert len(call_args.data_sources) == 1
            assert call_args.data_sources[0].type == DataSourceType.SSH
            assert call_args.data_sources[0].install_names == ["test_install"]