"""
Thread-safe queue management for file processing.

This module provides a clean, thread-safe queue infrastructure for handling
all file processing tasks in a unified pipeline.
"""

import queue
import threading
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Types of file processing tasks."""
    INDEX_FILE = "index_file"
    DELETE_FILE = "delete_file"
    UPDATE_FILE = "update_file"
    MOVE_FILE = "move_file"


@dataclass
class FileTask:
    """Represents a file processing task."""
    task_type: TaskType
    file_path: str
    metadata: Optional[Dict[str, Any]] = None


class FileProcessingQueue:
    """
    Thread-safe queue manager for file processing tasks.
    
    Provides a clean interface for adding tasks, getting tasks, tracking progress
    """
    
    def __init__(self, max_size: int = 0):
        """
        Initialize the file processing queue.
        
        Args:
            max_size: Maximum queue size (0 = unlimited)
        """
        self._queue = queue.Queue(maxsize=max_size) # thread safe queue
        self._shutdown_event = threading.Event() # thread safe shutdown manager
        
        # Progress tracking for indexing progress updates
        self._stats_lock = threading.Lock()
        self._stats = {
            'total_added': 0,
            'total_processed': 0,
            'total_failed': 0,
            'processing_start_time': None
        }
        
        logger.info("FileProcessingQueue initialized")
    
    def add_task(self, task: FileTask) -> bool:
        """
        Add a file processing task to the queue.
        
        Args:
            task: FileTask to add to the queue
            
        Returns:
            bool: True if task was added successfully, False if shutdown
        """

        if self._shutdown_event.is_set():
            return False
        
        try:
            self._queue.put(task, timeout=1.0)
            
            with self._stats_lock:
                self._stats['total_added'] += 1
                
                # Set start time on first task
                if self._stats['processing_start_time'] is None:
                    self._stats['processing_start_time'] = time.time()
            
            logger.debug(f"Added task: {task.task_type.value} for {task.file_path}")
            return True
            
        except queue.Full:
            logger.error(f"Queue is full - cannot add task: {task.file_path}")
            return False
        except queue.Empty:
            logger.error("Queue is empty - unexpected condition")
            return False
    
    def get_task(self, timeout: float = 1.0) -> Optional[FileTask]:
        """
        Get the next task from the queue.
        
        Args:
            timeout: Maximum time to wait for a task
            
        Returns:
            FileTask or None if no task available or shutting down
        """
        if self._shutdown_event.is_set():
            return None
        
        try:
            task = self._queue.get(timeout=timeout)
            return task
        except queue.Empty:
            return None
    
    def task_completed(self, task: FileTask, success: bool = True):
        """
        Mark a task as completed and update statistics.
        
        Args:
            task: The completed FileTask
            success: Whether the task completed successfully
        """
        with self._stats_lock:
            if success:
                self._stats['total_processed'] += 1
            else:
                self._stats['total_failed'] += 1
        
        # Mark task as done in the queue
        self._queue.task_done()
        
        logger.debug(f"Task completed: {task.task_type.value} for {task.file_path} (success: {success})")
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get current processing progress and statistics.
        
        Returns:
            Dict containing progress information for indexing progress updates
        """
        with self._stats_lock:
            stats = self._stats.copy()
        
        # Calculate additional metrics
        total_completed = stats['total_processed'] + stats['total_failed']
        if stats['total_added'] > 0:
            progress_percentage = (total_completed / stats['total_added']) * 100
        else:
            progress_percentage = 0.0
        
        # Calculate processing rate
        processing_rate = 0.0
        if stats['processing_start_time'] and total_completed > 0:
            elapsed_time = time.time() - stats['processing_start_time']
            if elapsed_time > 0:
                processing_rate = total_completed / elapsed_time
        
        return {
            'is_processing': total_completed < stats['total_added'],
            'total_added': stats['total_added'],
            'total_processed': stats['total_processed'],
            'total_failed': stats['total_failed'],
            'progress_percentage': progress_percentage,
            'processing_rate': processing_rate,  # tasks per second
        }
    
    def is_empty(self) -> bool:
        """Check if the queue is empty."""
        return self._queue.empty()
    
    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    def shutdown(self) -> bool:
        """
        Initiate graceful shutdown of the queue.
        """
        logger.info("Shutdown initiated for FileProcessingQueue")

        self._shutdown_event.set()
        
        return True