#!/usr/bin/env python3
"""
Test suite for database thread safety validation.
Validates that ChromaDB operations are thread-safe under concurrent access.
"""

import os
import sys
import time
import tempfile
import shutil
import threading
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

class DatabaseThreadSafetyTests:
    """Test class for database thread safety validation"""
    
    def __init__(self):
        self.test_results = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'errors': []
        }
        self.temp_dir = None
        self.original_directory = None
        self.test_files = []
    
    def setup_test_environment(self):
        """Create temporary directory with test files for database operations"""
        print("🔧 Setting up database test environment...")
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp(prefix="db_safety_test_")
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
        
        return True
    
    def cleanup_test_environment(self):
        """Clean up temporary directory and restore original directory"""
        print("🧹 Cleaning up database test environment...")
        
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
                    time.sleep(2)  # Wait for indexing to start
            except Exception as e:
                print(f"   Warning: Could not restore directory: {e}")
        
        # Remove temporary directory
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"   Removed temp directory: {self.temp_dir}")
            except Exception as e:
                print(f"   Warning: Could not remove temp directory: {e}")
    
    def create_test_file(self, filename, content):
        """Create a test file in the temp directory"""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path
    
    def perform_concurrent_searches(self, num_searches=20):
        """Perform multiple concurrent searches to test database read safety"""
        search_queries = [
            "test", "file", "content", "data", "python", "function", 
            "class", "import", "return", "string", "number", "array",
            "object", "method", "variable", "loop", "condition", "error",
            "debug", "config"
        ]
        
        def single_search(query_id):
            try:
                query = random.choice(search_queries)
                response = requests.post(
                    f"{BASE_URL}/search",
                    json={"query": query, "limit": 5},
                    timeout=10
                )
                
                return {
                    'id': query_id,
                    'query': query,
                    'status': response.status_code,
                    'success': response.status_code in [200, 404, 499],  # Valid responses
                    'response_time': response.elapsed.total_seconds()
                }
            except Exception as e:
                return {
                    'id': query_id,
                    'query': query,
                    'status': 500,
                    'success': False,
                    'error': str(e)
                }
        
        # Execute concurrent searches
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(single_search, i) for i in range(num_searches)]
            results = [future.result() for future in as_completed(futures)]
        
        return results
    
    def test_concurrent_database_reads(self):
        """Test database thread safety under concurrent read operations"""
        print("\n📖 TEST 1: Concurrent Database Reads")
        print("-" * 50)
        
        self.test_results['total_tests'] += 1
        
        try:
            # Ensure we have some data to search
            test_files = [
                ("db_test_1.txt", "Database thread safety test file with searchable content"),
                ("db_test_2.py", "# Python file for database testing\ndef test_function():\n    return 'database_test'"),
                ("db_test_3.md", "# Database Test\n\nThis file tests **database** thread safety"),
                ("db_test_4.json", '{"database": "test", "thread_safety": true, "concurrent": "reads"}'),
                ("db_test_5.txt", "Additional content for database read testing and validation"),
            ]
            
            for filename, content in test_files:
                self.create_test_file(filename, content)
            
            # Set directory to trigger indexing
            response = requests.post(
                f"{BASE_URL}/set-directory",
                json={"directoryPath": self.temp_dir},
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to set directory: {response.status_code}")
            
            # Wait for indexing to complete
            print("   Waiting for indexing to complete...")
            time.sleep(5)
            
            # Perform concurrent searches
            print("   Performing 20 concurrent searches...")
            start_time = time.time()
            results = self.perform_concurrent_searches(20)
            total_time = time.time() - start_time
            
            # Analyze results
            successful = sum(1 for r in results if r['success'])
            failed = len(results) - successful
            avg_response_time = sum(r.get('response_time', 0) for r in results if 'response_time' in r) / len(results)
            
            print(f"   Completed {len(results)} searches in {total_time:.3f}s")
            print(f"   Successful: {successful}, Failed: {failed}")
            print(f"   Average response time: {avg_response_time:.3f}s")
            
            # Check for database consistency (no crashes or corruption)
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                raise Exception("Backend became unhealthy during concurrent reads")
            
            health = response.json()
            if health.get('status') != 'healthy':
                raise Exception(f"Backend health degraded: {health}")
            
            # Success criteria: >90% success rate and system remains healthy
            success_rate = (successful / len(results)) * 100
            if success_rate >= 90:
                print(f"✅ Database read thread safety validated ({success_rate:.1f}% success rate)")
                self.test_results['passed'] += 1
                return True
            else:
                raise Exception(f"Low success rate: {success_rate:.1f}%")
                
        except Exception as e:
            print(f"❌ Concurrent database reads test failed: {e}")
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"Concurrent reads: {e}")
            return False
    
    def test_concurrent_database_writes(self):
        """Test database thread safety under concurrent write operations"""
        print("\n✍️ TEST 2: Concurrent Database Writes")
        print("-" * 50)
        
        self.test_results['total_tests'] += 1
        
        try:
            # Create initial files
            initial_files = []
            for i in range(5):
                filename = f"write_test_initial_{i}.txt"
                content = f"Initial file {i} for write testing"
                file_path = self.create_test_file(filename, content)
                initial_files.append(file_path)
            
            # Set directory to trigger initial indexing
            response = requests.post(
                f"{BASE_URL}/set-directory",
                json={"directoryPath": self.temp_dir},
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to set directory: {response.status_code}")
            
            # Wait for initial indexing
            time.sleep(3)
            
            # Create files rapidly to trigger concurrent writes
            def create_files_batch(batch_id, num_files=5):
                created = []
                for i in range(num_files):
                    filename = f"concurrent_write_{batch_id}_{i}.txt"
                    content = f"Concurrent write test file batch {batch_id} file {i}\nTimestamp: {time.time()}"
                    try:
                        file_path = self.create_test_file(filename, content)
                        created.append(file_path)
                        time.sleep(0.01)  # Small delay between files
                    except Exception as e:
                        return {'batch_id': batch_id, 'created': len(created), 'error': str(e)}
                
                return {'batch_id': batch_id, 'created': len(created), 'error': None}
            
            # Execute concurrent file creation (triggers concurrent database writes)
            print("   Creating files concurrently to trigger database writes...")
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(create_files_batch, i, 5) for i in range(5)]
                batch_results = [future.result() for future in as_completed(futures)]
            
            # Analyze batch results
            total_created = sum(r['created'] for r in batch_results)
            batch_errors = [r for r in batch_results if r['error']]
            
            print(f"   Created {total_created} files across {len(batch_results)} batches")
            if batch_errors:
                print(f"   Batch errors: {len(batch_errors)}")
            
            # Wait for processing
            time.sleep(5)
            
            # Verify system integrity
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                raise Exception("Backend became unhealthy during concurrent writes")
            
            health = response.json()
            if health.get('status') != 'healthy':
                raise Exception(f"Backend health degraded: {health}")
            
            # Check if files are being processed
            response = requests.get(f"{BASE_URL}/status", timeout=5)
            if response.status_code == 200:
                status = response.json()
                files_processed = status.get('indexing', {}).get('filesProcessed', 0)
                print(f"   Files processed: {files_processed}")
                
                # Success criteria: system remains healthy and processes files
                if files_processed > 0 and len(batch_errors) == 0:
                    print("✅ Database write thread safety validated")
                    self.test_results['passed'] += 1
                    return True
                else:
                    raise Exception(f"Write safety issues: {len(batch_errors)} batch errors")
            else:
                raise Exception("Could not get status after concurrent writes")
                
        except Exception as e:
            print(f"❌ Concurrent database writes test failed: {e}")
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"Concurrent writes: {e}")
            return False
    
    def test_database_consistency_under_load(self):
        """Test database consistency under mixed read/write load"""
        print("\n🔄 TEST 3: Database Consistency Under Load")
        print("-" * 50)
        
        self.test_results['total_tests'] += 1
        
        try:
            # Create base files
            base_files = []
            for i in range(10):
                filename = f"consistency_test_{i}.txt"
                content = f"Consistency test file {i}\nContent for load testing\nUnique identifier: {i}"
                file_path = self.create_test_file(filename, content)
                base_files.append(file_path)
            
            # Set directory
            response = requests.post(
                f"{BASE_URL}/set-directory",
                json={"directoryPath": self.temp_dir},
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to set directory: {response.status_code}")
            
            # Wait for initial indexing
            time.sleep(3)
            
            # Mixed load: concurrent searches + file creation
            def mixed_load_worker(worker_id):
                results = {'searches': 0, 'files_created': 0, 'errors': 0}
                
                for i in range(10):  # Each worker does 10 operations
                    try:
                        if i % 2 == 0:  # Even iterations: search
                            response = requests.post(
                                f"{BASE_URL}/search",
                                json={"query": f"consistency test {worker_id}", "limit": 3},
                                timeout=5
                            )
                            if response.status_code in [200, 404, 499]:
                                results['searches'] += 1
                            else:
                                results['errors'] += 1
                        else:  # Odd iterations: create file
                            filename = f"load_test_{worker_id}_{i}.txt"
                            content = f"Load test file from worker {worker_id} iteration {i}"
                            self.create_test_file(filename, content)
                            results['files_created'] += 1
                        
                        time.sleep(0.1)  # Small delay between operations
                        
                    except Exception as e:
                        results['errors'] += 1
                
                return results
            
            # Execute mixed load
            print("   Executing mixed read/write load...")
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = [executor.submit(mixed_load_worker, i) for i in range(6)]
                worker_results = [future.result() for future in as_completed(futures)]
            
            load_time = time.time() - start_time
            
            # Analyze results
            total_searches = sum(r['searches'] for r in worker_results)
            total_files = sum(r['files_created'] for r in worker_results)
            total_errors = sum(r['errors'] for r in worker_results)
            
            print(f"   Load test completed in {load_time:.3f}s")
            print(f"   Searches: {total_searches}, Files created: {total_files}, Errors: {total_errors}")
            
            # Verify system health and consistency
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                raise Exception("Backend became unhealthy under load")
            
            health = response.json()
            if health.get('status') != 'healthy':
                raise Exception(f"Backend health degraded under load: {health}")
            
            # Check database services are still functional
            services = health.get('services', {})
            if not services.get('searcher', False):
                raise Exception("Searcher service became unavailable")
            
            # Success criteria: low error rate and system remains healthy
            error_rate = (total_errors / (total_searches + total_files)) * 100 if (total_searches + total_files) > 0 else 100
            
            if error_rate <= 10:  # Allow up to 10% error rate under heavy load
                print(f"✅ Database consistency maintained under load ({error_rate:.1f}% error rate)")
                self.test_results['passed'] += 1
                return True
            else:
                raise Exception(f"High error rate under load: {error_rate:.1f}%")
                
        except Exception as e:
            print(f"❌ Database consistency under load test failed: {e}")
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"Consistency under load: {e}")
            return False
    
    def run_all_tests(self):
        """Run all database thread safety tests"""
        print("🧪 Database Thread Safety Tests")
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
            self.test_concurrent_database_reads()
            self.test_concurrent_database_writes()
            self.test_database_consistency_under_load()
            
            # Print results
            print("\n" + "=" * 60)
            print("DATABASE THREAD SAFETY TEST RESULTS")
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
                print("\n🎉 All database thread safety tests passed!")
                return True
            else:
                print(f"\n💥 {self.test_results['failed']} test(s) failed!")
                return False
                
        finally:
            # Always cleanup
            self.cleanup_test_environment()

def main():
    """Main test runner"""
    tester = DatabaseThreadSafetyTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()