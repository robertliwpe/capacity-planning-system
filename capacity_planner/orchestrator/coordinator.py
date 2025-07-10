"""Worker coordination and task execution."""

import asyncio
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from ..models.data_models import WorkerTask, SSHConfig, DataSourceType
from ..workers.data_processing import (
    SSHWorker, TerminalWorker, CSVWorker, LogWorker, PDFWorker
)
from ..utils.config import Config
from ..utils.logging import get_logger


class WorkerCoordinator:
    """Coordinates worker execution and task management."""
    
    def __init__(self, config: Config):
        """Initialize worker coordinator.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        self.logger = get_logger("coordinator")
        self.workers: Dict[str, Any] = {}
        self.executor = ThreadPoolExecutor(max_workers=config.max_workers)
        self._running = False
    
    async def start(self):
        """Start the coordinator."""
        self._running = True
        self.logger.info("Worker coordinator started")
    
    async def stop(self):
        """Stop the coordinator."""
        self._running = False
        
        # Stop all workers
        for worker in self.workers.values():
            if hasattr(worker, 'stop'):
                await worker.stop()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        self.logger.info("Worker coordinator stopped")
    
    async def execute_tasks(self, tasks: List[WorkerTask]) -> List[WorkerTask]:
        """Execute a list of tasks.
        
        Args:
            tasks: List of tasks to execute
            
        Returns:
            List of completed tasks
        """
        if not tasks:
            return []
        
        self.logger.info(f"Executing {len(tasks)} tasks")
        
        # Group tasks by worker type for better resource management
        task_groups = self._group_tasks_by_worker_type(tasks)
        
        # Execute task groups with appropriate concurrency
        completed_tasks = []
        
        for worker_type, group_tasks in task_groups.items():
            self.logger.info(f"Executing {len(group_tasks)} {worker_type} tasks")
            
            # Determine concurrency based on worker type
            max_concurrent = self._get_max_concurrent_for_worker_type(worker_type)
            
            # Execute tasks in batches
            batch_results = await self._execute_task_batch(
                group_tasks, worker_type, max_concurrent
            )
            completed_tasks.extend(batch_results)
        
        self.logger.info(f"Completed {len(completed_tasks)} tasks")
        return completed_tasks
    
    def _group_tasks_by_worker_type(self, tasks: List[WorkerTask]) -> Dict[str, List[WorkerTask]]:
        """Group tasks by worker type.
        
        Args:
            tasks: List of tasks
            
        Returns:
            Dictionary of worker type to tasks
        """
        groups = {}
        for task in tasks:
            if task.worker_type not in groups:
                groups[task.worker_type] = []
            groups[task.worker_type].append(task)
        
        # Sort tasks within each group by priority
        for worker_type in groups:
            groups[worker_type].sort(key=lambda t: t.priority, reverse=True)
        
        return groups
    
    def _get_max_concurrent_for_worker_type(self, worker_type: str) -> int:
        """Get maximum concurrent workers for a worker type.
        
        Args:
            worker_type: Type of worker
            
        Returns:
            Maximum concurrent workers
        """
        # SSH workers should be limited to avoid overwhelming servers
        if worker_type == "ssh":
            return min(3, self.config.max_workers)
        
        # Terminal workers can run more concurrently for local operations
        elif worker_type == "terminal":
            return min(5, self.config.max_workers)
        
        # File processing workers
        else:
            return min(4, self.config.max_workers)
    
    async def _execute_task_batch(
        self,
        tasks: List[WorkerTask],
        worker_type: str,
        max_concurrent: int
    ) -> List[WorkerTask]:
        """Execute a batch of tasks with concurrency control.
        
        Args:
            tasks: Tasks to execute
            worker_type: Type of worker
            max_concurrent: Maximum concurrent execution
            
        Returns:
            Completed tasks
        """
        completed_tasks = []
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_single_task(task: WorkerTask) -> WorkerTask:
            async with semaphore:
                try:
                    worker = await self._get_worker(task.worker_type, task)
                    return await worker.execute(task)
                except Exception as e:
                    self.logger.error(f"Task {task.task_id} failed: {e}")
                    task.status = "failed"
                    task.error = str(e)
                    return task
        
        # Execute all tasks concurrently with semaphore control
        task_coroutines = [execute_single_task(task) for task in tasks]
        completed_tasks = await asyncio.gather(*task_coroutines)
        
        return completed_tasks
    
    async def _get_worker(self, worker_type: str, task: WorkerTask) -> Any:
        """Get or create a worker instance.
        
        Args:
            worker_type: Type of worker needed
            task: Task to be executed
            
        Returns:
            Worker instance
        """
        # For SSH workers, create new instances for each connection
        if worker_type == "ssh":
            ssh_config = task.data_source.ssh_config
            if not ssh_config:
                raise ValueError("SSH task requires SSH configuration")
            return SSHWorker(ssh_config)
        
        # For other workers, reuse instances
        worker_key = f"{worker_type}_worker"
        
        if worker_key not in self.workers:
            if worker_type == "terminal":
                self.workers[worker_key] = TerminalWorker()
            elif worker_type == "csv":
                self.workers[worker_key] = CSVWorker()
            elif worker_type == "log":
                self.workers[worker_key] = LogWorker()
            elif worker_type == "pdf":
                self.workers[worker_key] = PDFWorker()
            else:
                raise ValueError(f"Unknown worker type: {worker_type}")
            
            # Start the worker
            await self.workers[worker_key].start()
        
        return self.workers[worker_key]
    
    async def execute_single_task(self, task: WorkerTask) -> WorkerTask:
        """Execute a single task.
        
        Args:
            task: Task to execute
            
        Returns:
            Completed task
        """
        try:
            worker = await self._get_worker(task.worker_type, task)
            return await worker.execute(task)
        except Exception as e:
            self.logger.error(f"Task {task.task_id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
            return task
    
    async def get_task_status(self, task_id: str) -> Optional[str]:
        """Get status of a specific task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task status or None if not found
        """
        for worker in self.workers.values():
            if hasattr(worker, 'get_task_status'):
                status = worker.get_task_status(task_id)
                if status:
                    return status
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if task was cancelled
        """
        for worker in self.workers.values():
            if hasattr(worker, '_tasks') and task_id in worker._tasks:
                task = worker._tasks[task_id]
                if task.status in ["pending", "processing"]:
                    task.status = "cancelled"
                    self.logger.info(f"Cancelled task {task_id}")
                    return True
        return False
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics.
        
        Returns:
            Worker statistics
        """
        stats = {
            'active_workers': len(self.workers),
            'worker_types': list(self.workers.keys()),
            'max_workers': self.config.max_workers,
            'running': self._running
        }
        
        # Get task counts from workers
        total_tasks = 0
        completed_tasks = 0
        failed_tasks = 0
        
        for worker in self.workers.values():
            if hasattr(worker, '_tasks'):
                worker_tasks = worker._tasks.values()
                total_tasks += len(worker_tasks)
                completed_tasks += len([t for t in worker_tasks if t.status == "completed"])
                failed_tasks += len([t for t in worker_tasks if t.status == "failed"])
        
        stats.update({
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'failed_tasks': failed_tasks
        })
        
        return stats