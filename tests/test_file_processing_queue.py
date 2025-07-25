"""
Unit tests for FileProcessingQueue.

Tests basic functionality including thread safety, progress tracking,
and graceful shutdown.
"""

import unittest
import threading
import time
from unittest.mock import Mock
from typing import List

# Add parent directory to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processing.file_processing_queue import FileProcessingQueue, FileTask, TaskType


class TestFileProcessingQueue(unittest.TestCase):
    """Test cases for FileProcessingQueue functionality."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.queue = FileProcessingQueue()
        self.dummy_test_files = [
            "/test/file1.txt",
            "/test/file2.py",
            "/test/file3.md"
        ]
    
    def tearDown(self):
        """Clean up after each test method."""
        if hasattr(self, 'queue'):
            self.queue.shutdown()
    
    def test_queue_initialization(self):
        """Queue Initialization - Verify queue starts empty and in correct initial state"""
        self.assertIsNotNone(self.queue)
        self.assertTrue(self.queue.is_empty())
        self.assertEqual(self.queue.size(), 0)
        self.assertFalse(self.queue.is_shutdown())
    
    def test_basic_task_operations(self):
        """Basic Task Operations - Verify tasks can be added, retrieved, and marked as completed"""
        # Create a test task
        task = FileTask(
            task_type=TaskType.INDEX_FILE,
            file_path=self.dummy_test_files[0]
        )
        
        # Add task
        success = self.queue.add_task(task)
        self.assertTrue(success)
        self.assertFalse(self.queue.is_empty())
        self.assertEqual(self.queue.size(), 1)
        
        # Get task
        retrieved_task = self.queue.get_task(timeout=1.0)
        self.assertIsNotNone(retrieved_task)
        self.assertEqual(retrieved_task.file_path, self.dummy_test_files[0])
        self.assertEqual(retrieved_task.task_type, TaskType.INDEX_FILE)
        
        # Mark as completed
        self.queue.task_completed(retrieved_task, success=True)
    
    def test_fifo_ordering(self):
        """FIFO Ordering - Ensure tasks are processed in first-in-first-out order"""
        # Add tasks in order
        tasks = [
            FileTask(TaskType.INDEX_FILE, "/first.txt"),
            FileTask(TaskType.UPDATE_FILE, "/second.txt"),
            FileTask(TaskType.DELETE_FILE, "/third.txt"),
        ]
        
        # Add tasks in order
        for task in tasks:
            self.queue.add_task(task)
        
        # Retrieve tasks - should come out in same order
        expected_order = ["/first.txt", "/second.txt", "/third.txt"]
        actual_order = []
        
        for _ in range(3):
            task = self.queue.get_task(timeout=1.0)
            self.assertIsNotNone(task)
            actual_order.append(task.file_path)
            self.queue.task_completed(task, success=True)
        
        self.assertEqual(actual_order, expected_order)
    
    def test_progress_tracking(self):
        """Progress Tracking - Validate progress statistics are calculated and updated correctly"""
        # Initial progress
        progress = self.queue.get_progress()
        self.assertEqual(progress['total_added'], 0)
        self.assertEqual(progress['total_processed'], 0)
        self.assertEqual(progress['queue_size'], 0)
        self.assertFalse(progress['is_processing'])
        
        # Add some tasks
        for file_path in self.dummy_test_files:
            task = FileTask(TaskType.INDEX_FILE, file_path)
            self.queue.add_task(task)
        
        # Check progress after adding
        progress = self.queue.get_progress()
        self.assertEqual(progress['total_added'], 3)
        self.assertEqual(progress['queue_size'], 3)
        self.assertTrue(progress['is_processing'])
        
        # Process one task
        task = self.queue.get_task(timeout=1.0)
        self.queue.task_completed(task, success=True)
        
        # Check progress after processing
        progress = self.queue.get_progress()
        self.assertEqual(progress['total_processed'], 1)
        self.assertEqual(progress['queue_size'], 2)
        self.assertGreater(progress['progress_percentage'], 0)
        
        # Process remaining tasks
        while not self.queue.is_empty():
            task = self.queue.get_task(timeout=1.0)
            if task:
                self.queue.task_completed(task, success=True)
        
        # Final progress
        progress = self.queue.get_progress()
        self.assertEqual(progress['total_processed'], 3)
        self.assertEqual(progress['queue_size'], 0)
        self.assertEqual(progress['progress_percentage'], 100.0)
    
    def test_thread_safety(self):
        """Thread Safety - Verify queue handles concurrent producer/consumer operations safely"""
        num_threads = 3
        tasks_per_thread = 5
        results = {'added': 0, 'processed': 0, 'errors': 0}
        results_lock = threading.Lock()
        
        def producer_thread(thread_id: int):
            """Producer thread that adds tasks."""
            try:
                for i in range(tasks_per_thread):
                    task = FileTask(
                        task_type=TaskType.INDEX_FILE,
                        file_path=f"/thread{thread_id}/file{i}.txt"
                    )
                    if self.queue.add_task(task):
                        with results_lock:
                            results['added'] += 1
            except Exception as e:
                with results_lock:
                    results['errors'] += 1
                print(f"Producer thread {thread_id} error: {e}")
        
        def consumer_thread(thread_id: int):
            """Consumer thread that processes tasks."""
            try:
                processed_count = 0
                while processed_count < tasks_per_thread:
                    task = self.queue.get_task(timeout=2.0)
                    if task:
                        # Simulate some processing time
                        time.sleep(0.01)
                        self.queue.task_completed(task, success=True)
                        with results_lock:
                            processed_count += 1
                            results['processed'] += 1
                    else:
                        # No more tasks available
                        break
            except Exception as e:
                with results_lock:
                    results['errors'] += 1
                print(f"Consumer thread {thread_id} error: {e}")
        
        # Start producer threads
        producer_threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=producer_thread, args=(i,))
            producer_threads.append(thread)
            thread.start()
        
        # Wait for producers to finish
        for thread in producer_threads:
            thread.join(timeout=10.0)
        
        # Start consumer threads
        consumer_threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=consumer_thread, args=(i,))
            consumer_threads.append(thread)
            thread.start()
        
        # Wait for consumers to finish
        for thread in consumer_threads:
            thread.join(timeout=15.0)
        
        # Verify results
        expected_total = num_threads * tasks_per_thread
        self.assertEqual(results['added'], expected_total)
        self.assertEqual(results['processed'], expected_total)
        self.assertEqual(results['errors'], 0)
        self.assertTrue(self.queue.is_empty())
    
    def test_shutdown_functionality(self):
        """Shutdown Functionality - Ensure queue shuts down gracefully and rejects new operations"""
        # Add some tasks
        for file_path in self.dummy_test_files:
            task = FileTask(TaskType.INDEX_FILE, file_path)
            self.queue.add_task(task)
        
        self.assertFalse(self.queue.is_shutdown())
        self.assertFalse(self.queue.is_empty())
        
        # Process one task to simulate ongoing work
        task = self.queue.get_task(timeout=1.0)
        self.assertIsNotNone(task)
        
        # Initiate shutdown
        self.queue.shutdown()
        
        # Complete the task we retrieved
        self.queue.task_completed(task, success=True)
        
        # Verify shutdown state
        self.assertTrue(self.queue.is_shutdown())
        
        # Should not be able to add new tasks
        new_task = FileTask(TaskType.INDEX_FILE, "/new/file.txt")
        success = self.queue.add_task(new_task)
        self.assertFalse(success)
        
        # Should not be able to get tasks
        retrieved_task = self.queue.get_task(timeout=1.0)
        self.assertIsNone(retrieved_task)
 
if __name__ == '__main__':
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    # Run the tests
    unittest.main(verbosity=2)