#!/usr/bin/env python3
"""
Main test runner for the File Search API project.
Runs all tests in the tests/ directory.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def check_backend_health():
    """Check if the backend is running"""
    try:
        import requests
        response = requests.get("http://127.0.0.1:8000/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def run_test_file(test_file):
    """Run a single test file and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {test_file}")
    print('='*60)
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              capture_output=False, 
                              text=True, 
                              timeout=300)  # 5 minute timeout
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"❌ {test_file} timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running {test_file}: {e}")
        return False

def main():
    """Main test runner"""
    print("🧪 File Search API Test Suite")
    print("="*60)
    
    # Check if backend is running
    print("🔍 Checking backend health...")
    if not check_backend_health():
        print("❌ Backend is not running or not healthy!")
        print("   Please start the backend first:")
        print("   python main.py")
        return False
    
    print("✅ Backend is healthy and ready for testing")
    
    # Find all test files
    tests_dir = Path("tests")
    if not tests_dir.exists():
        print("❌ Tests directory not found!")
        return False
    
    test_files = []
    for test_file in tests_dir.glob("test_*.py"):
        test_files.append(str(test_file))
    
    if not test_files:
        print("❌ No test files found in tests/ directory!")
        return False
    
    print(f"📋 Found {len(test_files)} test files:")
    for test_file in test_files:
        print(f"   - {test_file}")
    
    # Run all tests
    results = {}
    start_time = time.time()
    
    for test_file in test_files:
        test_start = time.time()
        success = run_test_file(test_file)
        test_duration = time.time() - test_start
        
        results[test_file] = {
            'success': success,
            'duration': test_duration
        }
    
    total_duration = time.time() - start_time
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 TEST RESULTS SUMMARY")
    print('='*60)
    
    passed = 0
    failed = 0
    
    for test_file, result in results.items():
        status = "✅ PASSED" if result['success'] else "❌ FAILED"
        duration = result['duration']
        print(f"{status} {test_file} ({duration:.2f}s)")
        
        if result['success']:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Overall Results:")
    print(f"   Passed: {passed}")
    print(f"   Failed: {failed}")
    print(f"   Total:  {len(test_files)}")
    print(f"   Duration: {total_duration:.2f}s")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return True
    else:
        print(f"\n💥 {failed} test(s) failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)