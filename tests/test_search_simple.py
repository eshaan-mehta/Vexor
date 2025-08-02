#!/usr/bin/env python3
"""
Simple synchronous test for generation-based search system.
Easier to debug and understand the flow.
"""

import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

BASE_URL = "http://127.0.0.1:8000"

def test_single_search(query: str, test_id: str = ""):
    """Test a single search request"""
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{BASE_URL}/search",
            json={"query": query, "limit": 10},
            timeout=10
        )
        
        response_time = time.time() - start_time
        
        print(f"[{test_id}] Query: '{query}' -> Status: {response.status_code} ({response_time:.3f}s)")
        
        if response.status_code == 200:
            data = response.json()
            print(f"    Results: {data['totalCount']} files, Search time: {data['searchTime']:.3f}s")
            return True, response.status_code, response_time
        elif response.status_code == 499:
            print(f"    ⚠️  Search was superseded by newer request")
            return False, response.status_code, response_time
        elif response.status_code == 404:
            print(f"    ℹ️  No results found")
            return False, response.status_code, response_time
        else:
            print(f"    ❌ Error: {response.text}")
            return False, response.status_code, response_time
            
    except requests.exceptions.Timeout:
        response_time = time.time() - start_time
        print(f"[{test_id}] Query: '{query}' -> TIMEOUT ({response_time:.3f}s)")
        return False, 408, response_time
    except Exception as e:
        response_time = time.time() - start_time
        print(f"[{test_id}] Query: '{query}' -> ERROR: {e} ({response_time:.3f}s)")
        return False, 500, response_time

def get_backend_status():
    """Get current backend status"""
    try:
        response = requests.get(f"{BASE_URL}/status", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Status check failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"Cannot get status: {e}")
        return None

def test_rapid_invalidation():
    """Test rapid search requests to verify invalidation"""
    print("\n🔥 Testing Rapid Search Invalidation")
    print("-" * 50)
    
    queries = ["rapid1", "rapid2", "rapid3", "rapid4", "rapid5"]
    
    # Get initial generation
    initial_status = get_backend_status()
    if initial_status:
        initial_gen = initial_status.get("search", {}).get("current_generation", 0)
        print(f"Initial generation: {initial_gen}")
    
    # Send rapid requests
    results = []
    for i, query in enumerate(queries):
        success, status, time_taken = test_single_search(query, f"RAPID-{i+1}")
        results.append((success, status, time_taken))
        time.sleep(0.05)  # 50ms between requests
    
    # Get final generation
    final_status = get_backend_status()
    if final_status:
        final_gen = final_status.get("search", {}).get("current_generation", 0)
        print(f"Final generation: {final_gen}")
        if initial_status:
            print(f"Generation increment: {final_gen - initial_gen}")
    
    # Analyze results
    successful = sum(1 for success, _, _ in results if success)
    superseded = sum(1 for _, status, _ in results if status == 499)
    
    print(f"\nResults: {successful} successful, {superseded} superseded")
    print(f"Expected: Most should be superseded except the last one")

def test_concurrent_searches():
    """Test concurrent searches using threading"""
    print("\n🔄 Testing Concurrent Searches")
    print("-" * 50)
    
    def search_worker(query, worker_id):
        return test_single_search(query, f"WORKER-{worker_id}")
    
    # Start 5 concurrent searches
    queries = [f"concurrent{i}" for i in range(5)]
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all searches at once
        futures = [
            executor.submit(search_worker, query, i+1)
            for i, query in enumerate(queries)
        ]
        
        # Collect results
        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"Worker failed: {e}")
    
    successful = sum(1 for success, _, _ in results if success)
    superseded = sum(1 for _, status, _ in results if status == 499)
    
    print(f"\nConcurrent Results: {successful} successful, {superseded} superseded")

def test_generation_progression():
    """Test that generation numbers increase correctly"""
    print("\n📈 Testing Generation Progression")
    print("-" * 50)
    
    generations = []
    
    for i in range(5):
        # Get status before search
        status = get_backend_status()
        if status:
            gen_before = status.get("search", {}).get("current_generation", 0)
        else:
            gen_before = "unknown"
        
        # Perform search
        test_single_search(f"progression{i}", f"GEN-{i+1}")
        
        # Get status after search
        status = get_backend_status()
        if status:
            gen_after = status.get("search", {}).get("current_generation", 0)
            generations.append((gen_before, gen_after))
            print(f"    Generation: {gen_before} -> {gen_after}")
        
        time.sleep(0.1)
    
    print(f"\nGeneration progression: {generations}")

def main():
    print("🧪 Simple Search Generation Test")
    print("="*50)
    
    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Backend is not healthy")
            return
        print("✅ Backend is healthy")
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("Make sure the backend is running on http://127.0.0.1:8000")
        return
    
    # Run tests
    try:
        # Basic functionality test
        print("\n🔍 Testing Basic Search")
        print("-" * 50)
        test_single_search("python", "BASIC-1")
        test_single_search("test", "BASIC-2")
        
        # Test rapid invalidation
        test_rapid_invalidation()
        
        # Test concurrent searches
        test_concurrent_searches()
        
        # Test generation progression
        test_generation_progression()
        
        print("\n✅ All tests completed!")
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()