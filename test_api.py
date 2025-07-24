#!/usr/bin/env python3
"""
Simple test script for the FastAPI backend
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health check: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_status():
    """Test status endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/status")
        print(f"Status check: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Status check failed: {e}")
        return False

def test_search():
    """Test search endpoint"""
    try:
        search_data = {
            "query": "test",
            "limit": 5
        }
        response = requests.post(f"{BASE_URL}/search", json=search_data)
        print(f"Search test: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Search test failed: {e}")
        return False

def test_indexing_progress():
    """Test indexing progress endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/indexing-progress")
        print(f"Indexing progress: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Indexing progress test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing FastAPI backend...")
    print("Make sure the server is running with: python3 main.py")
    print("-" * 50)
    
    # Wait a moment for server to be ready
    time.sleep(1)
    
    tests = [
        ("Health Check", test_health),
        ("Status Check", test_status),
        ("Indexing Progress", test_indexing_progress),
        ("Search Test", test_search),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n=== {test_name} ===")
        success = test_func()
        results.append((test_name, success))
        print(f"Result: {'PASS' if success else 'FAIL'}")
    
    print("\n" + "=" * 50)
    print("TEST SUMMARY:")
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  {test_name}: {status}")