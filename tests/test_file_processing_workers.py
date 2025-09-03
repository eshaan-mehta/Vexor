#!/usr/bin/env python3
"""
Test suite for concurrent file processing worker threads.
Validates that multiple workers can process files simultaneously and safely.
"""

import os
import sys
import time
import tempfile
import shutil
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

class FileProcessingWorkerTests:
    """Test class for file processing worker validation"""
    
    def __init__(self):
        self.test_results = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'errors': []
        }
        self.temp_dir = None
        self.original_directory = None
    
    def setup_test_environment(self):
        """Create temporary directory with test files"""
        print("🔧 Setting up test environment...")
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp(prefix="worker_test_")
        print(f"   Created temp directory: {self.temp_dir}")
        
        # Get current directory from backend
        try:
            response = requests.get(f"{BASE_URL}/status", timeout=5)
            if response.status_code == 200:
                status = response.json()
                self.original_directory = status.get('current_directory')
                print(f"   Original directory: {self.original_directory}")
        except Exception as e:
            print(f"   Warning: Could not get original directory: {e}")
        
        # Create test files of different types
        test_files = [
            ("test_python.py", "# Python test file\nprint('Hello World')\ndef test_function():\n    return True"),
            ("test_text.txt", "This is a test text file for worker processing validation."),
            ("test_markdown.md", "# Test Markdown\n\nThis is a **test** markdown file."),
            ("test_config.json", '{"test": true, "workers": 8, "timeout": 30}'),
            ("test_readme.txt", "README file for testing concurrent processing capabilities."),
            ("test_script.js", "console.log('JavaScript test file'); function test() { return 42; }"),
            ("test_style.css", "body { margin: 0; padding: 20px; font-family: Arial; }"),
            ("test_data.csv", "name,age,city\nJohn,25,NYC\nJane,30,LA\nBob,35,Chicago"),
            ("test_log.log", "2024-01-01 10:00:00 INFO Test log entry for worker validation"),
            ("test_html.html", "<html><body><h1>Test HTML</h1><p>Worker test file</p></body></html>"),
        ]
        
        for filename, content in test_files:
            file_path = os.path.join(self.temp_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        print(f"   Created {len(test_files)} test files")
        return True
    
    def cleanup_test_environment(self):
        """Clean up temporary directory and restore original directory"""
        print("🧹 Cleaning up test environment...")
        
        # Restore original directory
        if self.original_directory:
            try:
                response = requests.post(
                    f"{BASE_URL}/set-directory",
                    json={"directoryPath": self.original_directory},
                    timeout=10
                )
                if response.status_code == 200:
                    print(f"   Restored original directory: {self.original_directory}")
                    # Wait for indexing to start
                    time.sleep(2)
            except Exception as e:
                print(f"   Warning: Could not restore directory: {e}")
        
        # Remove temporary directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"   Removed temp directory: {self.temp_dir}")
            except Exception as e:
                print(f"   Warning: Could not remove temp directory: {e}")
    
    def wait_for_indexing_completion(self, timeout=30):
        """Wait for indexing to complete"""
        print("⏳ Waiting for indexing to complete...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{BASE_URL}/status", timeout=5)
                if response.status_code == 200:
                    status = response.json()
                    indexing = status.get('indexing', {})
                    
                    if not indexing.get('isIndexing', True):
                        files_processed = indexing.get('filesProcessed', 0)
                        total_files = indexing.get('totalFiles', 0)
                        print(f"   Indexing complete: {files_processed}/{total_files} files")
                        return True
                    else:
                        files_processed = indexing.get('filesProcessed', 0)
                        total_files = indexing.get('totalFiles', 0)
                        progress = indexing.get('progress', 0) * 100
                        print(f"   Indexing progress: {files_processed}/{total_files} ({progress:.1f}%)")
            except Exception as e:
                print(f"   Error checking status: {e}")
            
            time.sleep(1)
        
        print(f"   Warning: Indexing did not complete within {timeout} seconds")
        return False
    
    def test_concurrent_file_processing(self):
        """Test that multiple workers can process files concurrently"""
        print("\n📁 TEST 1: Concurrent File Processing")
        print("-" * 50)
        
        self.test_results['total_tests'] += 1
        
        try:
            # Set directory to temp directory to trigger indexing
            response = requests.post(
                f"{BASE_URL}/set-directory",
                json={"directoryPath": self.temp_dir},
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to set directory: {response.status_code}")
            
            print(f"✅ Set directory to: {self.temp_dir}")
            
            # Wait for indexing to complete
            if not self.wait_for_indexing_completion():
                raise Exception("Indexing did not complete in time")
            
            # Verify files were processed
            response = requests.get(f"{BASE_URL}/status", timeout=5)
            if response.status_code == 200:
                status = response.json()
                indexing = status.get('indexing', {})
                files_processed = indexing.get('filesProcessed', 0)
                
                if files_processed >= 10:  # We created 10 test files
                    print(f"✅ Successfully processed {files_processed} files concurrently")
                    self.test_results['passed'] += 1
                    return True
                else:
                    raise Exception(f"Only {files_processed} files processed, expected at least 10")
            else:
                raise Exception(f"Failed to get status: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Concurrent processing test failed: {e}")
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"Concurrent processing: {e}")
            return False
    
    def test_worker_thread_safety(self):
        """Test thread safety by rapidly adding and removing files"""
        print("\n🔒 TEST 2: Worker Thread Safety")
        print("-" * 50)
        
        self.test_results['total_tests'] += 1
        
        try:
            # Create additional files rapidly to stress test workers
            stress_files = []
            for i in range(20):
                filename = f"stress_test_{i}.txt"
                file_path = os.path.join(self.temp_dir, filename)
                content = f"Stress test file {i}\nContent for thread safety testing\nTimestamp: {time.time()}"
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                stress_files.append(file_path)
                
                # Small delay to simulate real file creation
                time.sleep(0.01)
            
            print(f"✅ Created {len(stress_files)} stress test files")
            
            # Wait for processing
            time.sleep(5)
            
            # Verify system is still responsive
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                if health.get('status') == 'healthy':
                    print("✅ System remains healthy under stress")
                    
                    # Check if files are being processed
                    response = requests.get(f"{BASE_URL}/status", timeout=5)
                    if response.status_code == 200:
                        status = response.json()
                        indexing = status.get('indexing', {})
                        files_processed = indexing.get('filesProcessed', 0)
                        print(f"✅ Processed {files_processed} files under stress conditions")
                        
                        self.test_results['passed'] += 1
                        return True
                    else:
                        raise Exception("Could not get status after stress test")
                else:
                    raise Exception(f"System unhealthy: {health}")
            else:
                raise Exception(f"Health check failed: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Thread safety test failed: {e}")
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"Thread safety: {e}")
            return False
    
    def test_worker_performance(self):
        """Test worker performance and throughput"""
        print("\n⚡ TEST 3: Worker Performance")
        print("-" * 50)
        
        self.test_results['total_tests'] += 1
        
        try:
            # Get initial status
            response = requests.get(f"{BASE_URL}/status", timeout=5)
            if response.status_code != 200:
                raise Exception("Could not get initial status")
            
            initial_status = response.json()
            initial_processed = initial_status.get('indexing', {}).get('filesProcessed', 0)
            
            # Create batch of files for performance testing
            batch_size = 15
            start_time = time.time()
            
            for i in range(batch_size):
                filename = f"perf_test_{i}.txt"
                file_path = os.path.join(self.temp_dir, filename)
                content = f"Performance test file {i}\n" + "Content line\n" * 10
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            creation_time = time.time() - start_time
            print(f"✅ Created {batch_size} files in {creation_time:.3f}s")
            
            # Wait for processing and measure time
            processing_start = time.time()
            max_wait = 30
            
            while time.time() - processing_start < max_wait:
                response = requests.get(f"{BASE_URL}/status", timeout=5)
                if response.status_code == 200:
                    status = response.json()
                    current_processed = status.get('indexing', {}).get('filesProcessed', 0)
                    
                    if current_processed >= initial_processed + batch_size:
                        processing_time = time.time() - processing_start
                        throughput = batch_size / processing_time
                        print(f"✅ Processed {batch_size} files in {processing_time:.3f}s")
                        print(f"✅ Worker throughput: {throughput:.2f} files/second")
                        
                        if throughput > 1.0:  # At least 1 file per second
                            self.test_results['passed'] += 1
                            return True
                        else:
                            raise Exception(f"Low throughput: {throughput:.2f} files/second")
                
                time.sleep(0.5)
            
            raise Exception(f"Processing did not complete within {max_wait} seconds")
            
        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"Performance: {e}")
            return False
    
    def run_all_tests(self):
        """Run all file processing worker tests"""
        print("🧪 File Processing Worker Thread Tests")
        print("=" * 60)
        
        # Check backend health
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                print("❌ Backend is not healthy")
                return False
            print("✅ Backend is healthy")
        except Exception as e:
            print(f"❌ Cannot connect to backend: {e}")
            return False
        
        try:
            # Setup test environment
            if not self.setup_test_environment():
                print("❌ Failed to setup test environment")
                return False
            
            # Run tests
            self.test_concurrent_file_processing()
            self.test_worker_thread_safety()
            self.test_worker_performance()
            
            # Print results
            print("\n" + "=" * 60)
            print("FILE PROCESSING WORKER TEST RESULTS")
            print("=" * 60)
            print(f"Total Tests:     {self.test_results['total_tests']}")
            print(f"Passed:          {self.test_results['passed']}")
            print(f"Failed:          {self.test_results['failed']}")
            
            if self.test_results['errors']:
                print("\nErrors:")
                for error in self.test_results['errors']:
                    print(f"  - {error}")
            
            success_rate = (self.test_results['passed'] / self.test_results['total_tests']) * 100
            print(f"\nSuccess Rate:    {success_rate:.1f}%")
            
            if self.test_results['failed'] == 0:
                print("\n🎉 All file processing worker tests passed!")
                return True
            else:
                print(f"\n💥 {self.test_results['failed']} test(s) failed!")
                return False
                
        finally:
            # Always cleanup
            self.cleanup_test_environment()

def main():
    """Main test runner"""
    tester = FileProcessingWorkerTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()