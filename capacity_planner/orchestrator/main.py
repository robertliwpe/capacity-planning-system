"""Main orchestrator for capacity planning analysis."""

import asyncio
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from ..models.data_models import (
    AnalysisRequest, AnalysisResult, DataSource, DataSourceType,
    WorkerTask, ConfigurationRecommendation
)
from ..utils.config import Config
from ..utils.logging import get_logger
from .task_analyzer import TaskAnalyzer
from .coordinator import WorkerCoordinator
from ..analysis.recommendation_engine import RecommendationEngine


class CapacityPlanningOrchestrator:
    """Main orchestrator for capacity planning analysis."""
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize orchestrator.
        
        Args:
            config: Configuration instance
        """
        self.config = config or Config()
        self.logger = get_logger("orchestrator")
        self.task_analyzer = TaskAnalyzer()
        self.coordinator = WorkerCoordinator(self.config)
        self.recommendation_engine = RecommendationEngine(self.config)
        self._running = False
    
    async def start(self):
        """Start the orchestrator."""
        self._running = True
        await self.coordinator.start()
        self.logger.info("Orchestrator started")
    
    async def stop(self):
        """Stop the orchestrator."""
        self._running = False
        await self.coordinator.stop()
        self.logger.info("Orchestrator stopped")
    
    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """Perform capacity planning analysis.
        
        Args:
            request: Analysis request
            
        Returns:
            Analysis result
        """
        start_time = datetime.now(timezone.utc)
        request_id = str(uuid.uuid4())
        
        self.logger.info(f"Starting analysis {request_id}")
        
        try:
            # Analyze task complexity
            complexity = await self.task_analyzer.analyze_complexity(request.data_sources)
            self.logger.info(f"Task complexity: {complexity}")
            
            # Create worker tasks
            tasks = await self.task_analyzer.create_tasks(request.data_sources)
            self.logger.info(f"Created {len(tasks)} tasks")
            
            # Execute tasks
            task_results = await self.coordinator.execute_tasks(tasks)
            
            # Process results
            all_metrics = []
            all_log_analyses = []
            errors = []
            warnings = []
            
            for task_result in task_results:
                if task_result.status == "completed" and task_result.result:
                    result_data = task_result.result
                    
                    # Check if result is InstallMetrics (from SSH worker)
                    if hasattr(result_data, 'install_name') and hasattr(result_data, 'metrics'):
                        # Extract ServerMetrics from InstallMetrics
                        all_metrics.append(result_data.metrics)
                        # Extract log analyses from InstallMetrics
                        if hasattr(result_data, 'logs') and result_data.logs:
                            all_log_analyses.extend(result_data.logs.values())
                    
                    # Extract metrics from other types
                    elif hasattr(result_data, 'metrics'):
                        all_metrics.append(result_data.metrics)
                    elif isinstance(result_data, dict) and 'metrics' in result_data:
                        all_metrics.append(result_data['metrics'])
                    
                    # Extract log analyses from other types
                    elif hasattr(result_data, 'logs'):
                        all_log_analyses.extend(result_data.logs.values())
                    elif isinstance(result_data, dict) and 'analysis' in result_data:
                        analysis = result_data['analysis']
                        # Only process if this is actually log analysis data
                        if hasattr(analysis, 'total_requests') or (isinstance(analysis, dict) and 'total_requests' in analysis):
                            # Ensure analysis is a LogAnalysis object
                            if isinstance(analysis, dict):
                                from ..models.data_models import LogAnalysis
                                analysis = LogAnalysis(**analysis)
                            all_log_analyses.append(analysis)
                
                elif task_result.status == "failed":
                    errors.append(f"Task {task_result.task_id}: {task_result.error}")
                
                elif task_result.status == "cancelled":
                    warnings.append(f"Task {task_result.task_id} was cancelled")
            
            # Generate recommendations
            recommendations = await self.recommendation_engine.generate_recommendations(
                metrics=all_metrics,
                log_analyses=all_log_analyses,
                confidence_threshold=request.confidence_threshold
            )
            
            # Generate report
            report = await self.generate_report(
                recommendations=recommendations,
                metrics=all_metrics,
                log_analyses=all_log_analyses,
                format=request.output_format
            )
            
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Determine overall status
            overall_status = "failed" if errors else "completed"
            
            result = AnalysisResult(
                request_id=request_id,
                status=overall_status,
                recommendations=recommendations,
                server_metrics=all_metrics,
                log_analyses=all_log_analyses,
                report=report,
                errors=errors,
                warnings=warnings,
                execution_time=execution_time
            )
            
            self.logger.info(f"Analysis {request_id} completed in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.error(f"Analysis {request_id} failed: {e}", exc_info=True)
            
            return AnalysisResult(
                request_id=request_id,
                status="failed",
                recommendations=[],
                errors=[str(e)],
                execution_time=execution_time
            )
    
    async def generate_report(
        self,
        recommendations: List[ConfigurationRecommendation],
        metrics: List[Any],
        log_analyses: List[Any],
        format: str = "markdown"
    ) -> str:
        """Generate analysis report.
        
        Args:
            recommendations: Configuration recommendations
            metrics: Server metrics
            log_analyses: Log analyses
            format: Report format
            
        Returns:
            Generated report
        """
        if format.lower() == "markdown":
            return await self._generate_markdown_report(recommendations, metrics, log_analyses)
        elif format.lower() == "json":
            import json
            return json.dumps({
                "recommendations": [r.model_dump() for r in recommendations],
                "metrics_count": len(metrics),
                "log_analyses_count": len(log_analyses)
            }, indent=2)
        else:
            return await self._generate_text_report(recommendations, metrics, log_analyses)
    
    async def _generate_markdown_report(
        self,
        recommendations: List[ConfigurationRecommendation],
        metrics: List[Any],
        log_analyses: List[Any]
    ) -> str:
        """Generate markdown report."""
        report = []
        
        # Header
        report.append("# Capacity Planning Analysis Report")
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("")
        
        # Executive Summary
        report.append("## Executive Summary")
        
        if recommendations:
            top_rec = recommendations[0]
            report.append(f"**Recommended Configuration:** {top_rec.config_name}")
            report.append(f"**Confidence Score:** {top_rec.confidence_score:.2%}")
            report.append(f"**Tier:** {top_rec.tier}")
            if top_rec.specialization:
                report.append(f"**Specialization:** {top_rec.specialization}")
        else:
            report.append("No suitable configuration recommendations found.")
        
        report.append("")
        
        # Recommendations
        if recommendations:
            report.append("## Configuration Recommendations")
            
            for i, rec in enumerate(recommendations[:5], 1):  # Top 5
                report.append(f"### {i}. {rec.config_name}")
                report.append(f"- **Confidence:** {rec.confidence_score:.2%}")
                report.append(f"- **Tier:** {rec.tier}")
                if rec.specialization:
                    report.append(f"- **Specialization:** {rec.specialization}")
                if rec.size:
                    report.append(f"- **Size:** {rec.size}")
                
                report.append("**Reasoning:**")
                for reason in rec.reasoning:
                    report.append(f"- {reason}")
                
                if rec.warnings:
                    report.append("**Warnings:**")
                    for warning in rec.warnings:
                        report.append(f"- ⚠️ {warning}")
                
                report.append("")
        
        # System Metrics Summary
        if metrics:
            report.append("## System Metrics Summary")
            
            # Calculate averages
            cpu_values = [m.cpu_usage for m in metrics if hasattr(m, 'cpu_usage')]
            memory_values = [m.memory_usage for m in metrics if hasattr(m, 'memory_usage')]
            
            if cpu_values:
                report.append(f"- **Average CPU Usage:** {sum(cpu_values)/len(cpu_values):.1f}%")
                report.append(f"- **Peak CPU Usage:** {max(cpu_values):.1f}%")
            
            if memory_values:
                report.append(f"- **Average Memory Usage:** {sum(memory_values)/len(memory_values):.1f}%")
                report.append(f"- **Peak Memory Usage:** {max(memory_values):.1f}%")
            
            report.append(f"- **Servers Analyzed:** {len(metrics)}")
            report.append("")
        
        # Log Analysis Summary
        if log_analyses:
            report.append("## Log Analysis Summary")
            
            total_requests = sum(
                log.total_requests for log in log_analyses 
                if hasattr(log, 'total_requests')
            )
            
            error_rates = [
                log.error_rate for log in log_analyses 
                if hasattr(log, 'error_rate')
            ]
            
            response_times = [
                log.avg_response_time for log in log_analyses 
                if hasattr(log, 'avg_response_time') and log.avg_response_time > 0
            ]
            
            if total_requests > 0:
                report.append(f"- **Total Requests Analyzed:** {total_requests:,}")
            
            if error_rates:
                avg_error_rate = sum(error_rates) / len(error_rates)
                report.append(f"- **Average Error Rate:** {avg_error_rate:.2f}%")
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                report.append(f"- **Average Response Time:** {avg_response_time:.2f}s")
            
            report.append(f"- **Log Files Analyzed:** {len(log_analyses)}")
            report.append("")
        
        # Generated by footer
        report.append("---")
        report.append("*Generated by Capacity Planning System*")
        
        return "\n".join(report)
    
    async def _generate_text_report(
        self,
        recommendations: List[ConfigurationRecommendation],
        metrics: List[Any],
        log_analyses: List[Any]
    ) -> str:
        """Generate plain text report."""
        report = []
        
        report.append("CAPACITY PLANNING ANALYSIS REPORT")
        report.append("=" * 50)
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("")
        
        if recommendations:
            report.append("TOP RECOMMENDATION")
            report.append("-" * 20)
            top_rec = recommendations[0]
            report.append(f"Configuration: {top_rec.config_name}")
            report.append(f"Confidence: {top_rec.confidence_score:.2%}")
            report.append(f"Tier: {top_rec.tier}")
            report.append("")
        
        report.append(f"Data Sources Analyzed: {len(metrics) + len(log_analyses)}")
        if metrics:
            report.append(f"- Server Metrics: {len(metrics)}")
        if log_analyses:
            report.append(f"- Log Files: {len(log_analyses)}")
        
        return "\n".join(report)
    
    async def analyze_single_pod(
        self,
        pod_number: int,
        install_names: List[str],
        ssh_config: Dict[str, Any]
    ) -> AnalysisResult:
        """Analyze a single pod with specific installs.
        
        Args:
            pod_number: Pod number
            install_names: List of install names
            ssh_config: SSH configuration
            
        Returns:
            Analysis result
        """
        # Create SSH data sources
        data_sources = []
        
        for install_name in install_names:
            data_source = DataSource(
                type=DataSourceType.SSH,
                ssh_config=ssh_config,
                install_names=[install_name],
                metadata={
                    'pod_number': pod_number,
                    'install_name': install_name
                }
            )
            data_sources.append(data_source)
        
        # Create analysis request
        request = AnalysisRequest(
            data_sources=data_sources,
            confidence_threshold=self.config.confidence_threshold
        )
        
        return await self.analyze(request)