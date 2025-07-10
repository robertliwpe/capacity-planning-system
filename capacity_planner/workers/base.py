"""Base worker class for all workers."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from ..models.data_models import WorkerTask


class BaseWorker(ABC):
    """Abstract base class for all workers."""
    
    def __init__(self, name: Optional[str] = None):
        """Initialize base worker.
        
        Args:
            name: Worker name for logging
        """
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"capacity_planner.workers.{self.name}")
        self._running = False
        self._tasks: Dict[str, WorkerTask] = {}
    
    @abstractmethod
    async def process(self, task: WorkerTask) -> Any:
        """Process a single task.
        
        Args:
            task: Task to process
            
        Returns:
            Processing result
        """
        pass
    
    async def execute(self, task: WorkerTask) -> WorkerTask:
        """Execute a task with error handling.
        
        Args:
            task: Task to execute
            
        Returns:
            Updated task with result or error
        """
        start_time = datetime.now(timezone.utc)
        self._tasks[task.task_id] = task
        
        try:
            self.logger.info(f"Starting task {task.task_id}")
            task.status = "processing"
            
            result = await self.process(task)
            
            task.result = result
            task.status = "completed"
            self.logger.info(f"Completed task {task.task_id}")
            
        except asyncio.CancelledError:
            task.status = "cancelled"
            self.logger.warning(f"Task {task.task_id} cancelled")
            raise
            
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self.logger.error(f"Task {task.task_id} failed: {e}", exc_info=True)
            
        finally:
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.debug(f"Task {task.task_id} took {execution_time:.2f}s")
            
        return task
    
    async def start(self):
        """Start the worker."""
        self._running = True
        self.logger.info(f"{self.name} started")
    
    async def stop(self):
        """Stop the worker."""
        self._running = False
        
        # Cancel any pending tasks
        for task_id, task in self._tasks.items():
            if task.status in ["pending", "processing"]:
                task.status = "cancelled"
                
        self.logger.info(f"{self.name} stopped")
    
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """Get status of a specific task."""
        if task_id in self._tasks:
            return self._tasks[task_id].status
        return None
    
    def get_completed_tasks(self) -> List[WorkerTask]:
        """Get all completed tasks."""
        return [
            task for task in self._tasks.values()
            if task.status == "completed"
        ]
    
    def clear_completed_tasks(self):
        """Clear completed tasks from memory."""
        self._tasks = {
            task_id: task
            for task_id, task in self._tasks.items()
            if task.status not in ["completed", "failed", "cancelled"]
        }