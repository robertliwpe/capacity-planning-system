"""Task complexity analysis and task creation."""

import uuid
from typing import List, Dict, Any
from enum import Enum

from ..models.data_models import DataSource, DataSourceType, WorkerTask
from ..utils.logging import get_logger


class TaskComplexity(str, Enum):
    """Task complexity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class TaskAnalyzer:
    """Analyzes task complexity and creates worker tasks."""
    
    def __init__(self):
        """Initialize task analyzer."""
        self.logger = get_logger("task_analyzer")
    
    async def analyze_complexity(self, data_sources: List[DataSource]) -> TaskComplexity:
        """Analyze task complexity based on data sources.
        
        Args:
            data_sources: List of data sources
            
        Returns:
            Task complexity level
        """
        complexity_score = 0
        
        for source in data_sources:
            # SSH sources are more complex
            if source.type == DataSourceType.SSH:
                complexity_score += 3
                
                # Multiple installs increase complexity
                if source.install_names:
                    complexity_score += len(source.install_names)
            
            # PDF processing is complex
            elif source.type == DataSourceType.PDF:
                complexity_score += 2
            
            # Log files can be large
            elif source.type == DataSourceType.LOG:
                complexity_score += 2
            
            # CSV and terminal are simpler
            else:
                complexity_score += 1
        
        # Determine complexity level
        if complexity_score <= 3:
            return TaskComplexity.LOW
        elif complexity_score <= 8:
            return TaskComplexity.MEDIUM
        elif complexity_score <= 15:
            return TaskComplexity.HIGH
        else:
            return TaskComplexity.VERY_HIGH
    
    async def create_tasks(self, data_sources: List[DataSource]) -> List[WorkerTask]:
        """Create worker tasks from data sources.
        
        Args:
            data_sources: List of data sources
            
        Returns:
            List of worker tasks
        """
        tasks = []
        
        for source in data_sources:
            if source.type == DataSourceType.SSH:
                tasks.extend(await self._create_ssh_tasks(source))
            
            elif source.type == DataSourceType.CSV:
                tasks.append(await self._create_csv_task(source))
            
            elif source.type == DataSourceType.PDF:
                tasks.append(await self._create_pdf_task(source))
            
            elif source.type == DataSourceType.LOG:
                tasks.append(await self._create_log_task(source))
            
            elif source.type == DataSourceType.TERMINAL:
                tasks.append(await self._create_terminal_task(source))
            
            elif source.type == DataSourceType.JSON:
                tasks.append(await self._create_json_task(source))
        
        # Assign priorities
        self._assign_priorities(tasks)
        
        self.logger.info(f"Created {len(tasks)} tasks")
        return tasks
    
    async def _create_ssh_tasks(self, source: DataSource) -> List[WorkerTask]:
        """Create SSH worker tasks.
        
        Args:
            source: SSH data source
            
        Returns:
            List of SSH tasks
        """
        tasks = []
        
        if source.install_names:
            # Create a task for each install
            for install_name in source.install_names:
                task = WorkerTask(
                    task_id=str(uuid.uuid4()),
                    worker_type="ssh",
                    data_source=source,
                    parameters={
                        'install_name': install_name,
                        'pod_number': source.metadata.get('pod_number'),
                        'collect_logs': True,
                        'collect_metrics': True,
                        'collect_wp_info': True
                    }
                )
                tasks.append(task)
        else:
            # Single SSH task for general server metrics
            task = WorkerTask(
                task_id=str(uuid.uuid4()),
                worker_type="ssh",
                data_source=source,
                parameters={
                    'collect_metrics': True,
                    'collect_logs': False,
                    'pod_number': source.metadata.get('pod_number')
                }
            )
            tasks.append(task)
        
        return tasks
    
    async def _create_csv_task(self, source: DataSource) -> WorkerTask:
        """Create CSV worker task.
        
        Args:
            source: CSV data source
            
        Returns:
            CSV task
        """
        return WorkerTask(
            task_id=str(uuid.uuid4()),
            worker_type="csv",
            data_source=source,
            parameters={
                'type': source.metadata.get('analysis_type', 'auto'),
                'encoding': source.metadata.get('encoding')
            }
        )
    
    async def _create_pdf_task(self, source: DataSource) -> WorkerTask:
        """Create PDF worker task.
        
        Args:
            source: PDF data source
            
        Returns:
            PDF task
        """
        return WorkerTask(
            task_id=str(uuid.uuid4()),
            worker_type="pdf",
            data_source=source,
            parameters={
                'extract_metrics': True,
                'extract_config': True,
                'search_keywords': source.metadata.get('keywords', [])
            }
        )
    
    async def _create_log_task(self, source: DataSource) -> WorkerTask:
        """Create log worker task.
        
        Args:
            source: Log data source
            
        Returns:
            Log task
        """
        return WorkerTask(
            task_id=str(uuid.uuid4()),
            worker_type="log",
            data_source=source,
            parameters={
                'format': source.metadata.get('log_format', 'auto'),
                'max_lines': source.metadata.get('max_lines', 10000),
                'access_format': source.metadata.get('access_format', 'apache')
            }
        )
    
    async def _create_terminal_task(self, source: DataSource) -> WorkerTask:
        """Create terminal worker task.
        
        Args:
            source: Terminal data source
            
        Returns:
            Terminal task
        """
        return WorkerTask(
            task_id=str(uuid.uuid4()),
            worker_type="terminal",
            data_source=source,
            parameters={
                'type': source.metadata.get('task_type', 'system_info'),
                'command': source.metadata.get('command'),
                'timeout': source.metadata.get('timeout', 30),
                'hosts': source.metadata.get('hosts', [])
            }
        )
    
    async def _create_json_task(self, source: DataSource) -> WorkerTask:
        """Create JSON processing task.
        
        Args:
            source: JSON data source
            
        Returns:
            JSON task
        """
        return WorkerTask(
            task_id=str(uuid.uuid4()),
            worker_type="json",
            data_source=source,
            parameters={
                'schema': source.metadata.get('schema'),
                'extract_metrics': True
            }
        )
    
    def _assign_priorities(self, tasks: List[WorkerTask]):
        """Assign priorities to tasks.
        
        Args:
            tasks: List of tasks to prioritize
        """
        for task in tasks:
            # SSH tasks have higher priority due to complexity
            if task.worker_type == "ssh":
                task.priority = 3
            
            # Terminal tasks are quick, high priority
            elif task.worker_type == "terminal":
                task.priority = 2
            
            # CSV and JSON are medium priority
            elif task.worker_type in ["csv", "json"]:
                task.priority = 1
            
            # PDF and log processing can be slower
            else:
                task.priority = 0
    
    async def estimate_execution_time(self, tasks: List[WorkerTask]) -> float:
        """Estimate total execution time for tasks.
        
        Args:
            tasks: List of tasks
            
        Returns:
            Estimated execution time in seconds
        """
        # Base time estimates per worker type
        time_estimates = {
            "ssh": 30,      # SSH connections can be slow
            "terminal": 5,   # Local commands are fast
            "csv": 10,      # CSV processing is medium
            "pdf": 15,      # PDF extraction takes time
            "log": 20,      # Log parsing can be intensive
            "json": 5       # JSON parsing is fast
        }
        
        total_time = 0
        for task in tasks:
            base_time = time_estimates.get(task.worker_type, 10)
            
            # Adjust for task complexity
            if task.worker_type == "ssh":
                # More time for installs with logs
                if task.parameters.get('collect_logs'):
                    base_time += 20
                if task.parameters.get('collect_wp_info'):
                    base_time += 10
            
            total_time += base_time
        
        # Account for parallel execution (assume 4 workers)
        parallel_workers = min(4, len(tasks))
        if parallel_workers > 1:
            total_time = total_time / parallel_workers * 1.2  # 20% overhead
        
        return total_time