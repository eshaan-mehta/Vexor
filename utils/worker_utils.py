"""
Worker management utilities for file processing.

This module provides utilities for managing worker threads that process
file tasks from a queue.
"""

import threading
import os
from typing import List
from processing.file_processor import FileProcessor, ProcessingStatus
from utils.logging_utils import thread_safe_print, get_print_lock


def start_file_processing_workers(
    file_processing_queue, 
    file_processing_workers: List[threading.Thread], 
    processing_stats: dict,
    num_workers: int = 4
) -> None:
    """
    Start file processing worker threads.
    
    Args:
        file_processing_queue: The queue to process tasks from
        file_processing_workers: List to store worker thread references
        processing_stats: Dictionary to track processing statistics
        num_workers: Number of worker threads to create
    """
    thread_safe_print(f"Starting {num_workers} file processing workers...")
    
    for i in range(num_workers):
        worker = threading.Thread(
            target=file_processing_worker_loop,
            name=f"FileProcessor-{i}",
            args=(file_processing_queue, processing_stats),
            daemon=True
        )
        worker.start()
        file_processing_workers.append(worker)
    
    thread_safe_print(f"{len(file_processing_workers)} file processing workers successfully started")


def stop_file_processing_workers(
    file_processing_queue,
    file_processing_workers: List[threading.Thread]
) -> None:
    """
    Stop all file processing worker threads gracefully.
    
    Args:
        file_processing_queue: The queue to shutdown
        file_processing_workers: List of worker thread references to stop
    """
    thread_safe_print("Stopping file processing workers...")
    
    if file_processing_queue:
        file_processing_queue.shutdown()
    
    # Wait for all workers to finish
    for worker in file_processing_workers:
        worker.join(timeout=5.0)
    
    file_processing_workers.clear()
    thread_safe_print("File processing workers stopped")


def file_processing_worker_loop(file_processing_queue, processing_stats: dict) -> None:
    """
    Main loop for file processing worker threads.
    
    Args:
        file_processing_queue: The queue to get tasks from
        processing_stats: Dictionary to update with processing statistics
    """
    # Each worker gets its own FileProcessor instance
    processor = FileProcessor()
    worker_name = threading.current_thread().name
    print_lock = get_print_lock()
    
    thread_safe_print(f"Worker {worker_name} started")
    
    try:
        while not file_processing_queue.is_shutdown():
            task = file_processing_queue.get_task(timeout=1.0)
            if task is None:
                continue
            
            # Print when task is picked up from queue
            file_name = os.path.basename(task.file_path)
            thread_safe_print(f"{worker_name} picked up task: {task.task_type.value} for '{file_name}'")
            
            try:
                status = processor.process_task(task)
                
                # Update status counters (thread-safe)
                with print_lock:
                    processing_stats[status.value] += 1
                
                # Print result of processing with detailed status
                thread_safe_print(f"{worker_name} completed task: {task.task_type.value} for '{file_name}' - {status.value.upper()}")
                
                # Report success to queue (SUCCESS, SKIPPED, HIDDEN, and LARGE are considered successful)
                success = status in [ProcessingStatus.SUCCESS, ProcessingStatus.SKIPPED, ProcessingStatus.HIDDEN, ProcessingStatus.LARGE]
                file_processing_queue.task_completed(task, success)
                
            except Exception as e:
                # Update failure counter
                with print_lock:
                    processing_stats["failure"] += 1
                
                thread_safe_print(f"{worker_name} ERROR processing '{file_name}': {e}")
                file_processing_queue.task_completed(task, False)
    
    finally:
        # Clean up processor resources when worker stops
        processor.cleanup()
        thread_safe_print(f"Worker {worker_name} stopped and cleaned up")