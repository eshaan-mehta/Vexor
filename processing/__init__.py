"""
Processing module for queue-based file processing.

This module handles the unified queue-based architecture for file processing,
including queue management, worker threads, and progress tracking.
"""

from .file_processing_queue import FileProcessingQueue, FileTask, TaskType

__all__ = ['FileProcessingQueue', 'FileTask', 'TaskType']