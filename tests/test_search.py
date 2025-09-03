#!/usr/bin/env python3
"""
Comprehensive test suite for generation-based search invalidation system.
Tests the ability to return results and invalidate concurrent requests.
"""

import asyncio
import aiohttp
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import sys
import os

# Test configuration
BASE_URL = "http://127.0.0.1:8000"
SEARCH_ENDPOINT = f"{BASE_URL}/search"
STATUS_ENDPOINT = f"{BASE_URL}/status"
HEALTH_ENDPOINT = f"{BASE_URL}/health"

class SearchTestResults:
    """Container for test results and statistics"""
    def __init__(self):
        self.total_requests = 0
        self.successful_responses = 0
        self.superseded_responses = 0  # 499 status
        self.timeout_responses = 0     # 408 status
        self.not_found_responses = 0   # 404 status
        self.error_responses = 0       # 500+ status
        self.response_times = []
        self.concurrent_test_results = []
        
    def add_result(self, status_code: int, response_time: float, response_data: Dict = None):
        self.total_requests += 1
        self.response_times.append(response_time)
        
        if status_code == 200:
            self.successful_responses += 1
        elif status_code == 499:
            self.superseded_responses += 1
        elif status_code == 408:
            self.timeout_responses += 1
        elif status_code == 404:
            self.not_found_responses += 1
        else:
            self.error_responses += 1
    
    def print_summary(self):
        print("\n" + "="*60)
        print("SEARCH GENERATION TEST RESULTS SUMMARY")
        print("="*60)
        print(f"Total Requests:      {self.total_requests}")
        print(f"Successful (200):    {self.successful_responses}")
        print(f"Superseded (499):    {self.superseded_responses}")
        print(f"Timeout (408):       {self.timeout_responses}")
        print(f"Not Found (404):     {self.not_found_responses}")
        print(f"Errors (5xx):        {self.error_responses}")
        
        if self.response_times:
            avg_time = sum(self.response_times) / len(self.response_times)
            min_time = min(self.response_times)
            max_time = max(self.response_times)
            print(f"\nResponse Times:")
            print(f"  Average: {avg_time:.3f}s")
            print(f"  Min:     {min_time:.3f}s")
            print(f"  Max:     {max_time:.3f}s")
        
        print("="*60)

async def check_backend_health():
    """Check if the backend is running and healthy"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(HEALTH_ENDPOINT, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Backend is healthy: {data}")
                    return True
                else:
                    print(f"❌ Backend health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        return False

async def get_backend_status():
    """Get current backend status including search generation info"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(STATUS_ENDPOINT, timeout=5) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"❌ Status check failed: {response.status}")
                    return None
    except Exception as e:
        print(f"❌ Cannot get backend status: {e}")
        return None

async def single_search_request(query: str, session: aiohttp.ClientSession, test_id: str = "") -> Dict[str, Any]:
    """Perform a single search request and return detailed results"""
    start_time = time.time()
    
    try:
        payload = {"query": query, "limit": 10}
        async with session.post(SEARCH_ENDPOINT, json=payload, timeout=10) as response:
            response_time = time.time() - start_time
            
            try:
                response_data = await response.json()
            except:
                response_data = {"error": "Could not parse JSON response"}
            
            result = {
                "test_id": test_id,
                "query": query,
                "status_code": response.status,
                "response_time": response_time,
                "response_data": response_data,
                "timestamp": time.time()
            }
            
            # Log the result
            status_emoji = "✅" if response.status == 200 else "❌" if response.status >= 500 else "⚠️"
            print(f"{status_emoji} {test_id}: Query '{query}' -> {response.status} ({response_time:.3f}s)")
            
            return result
            
    except asyncio.TimeoutError:
        response_time = time.time() - start_time
        print(f"⏰ {test_id}: Query '{query}' -> TIMEOUT ({response_time:.3f}s)")
        return {
            "test_id": test_id,
            "query": query,
            "status_code": 408,
            "response_time": response_time,
            "response_data": {"error": "Request timeout"},
            "timestamp": time.time()
        }
    except Exception as e:
        response_time = time.time() - start_time
        print(f"💥 {test_id}: Query '{query}' -> ERROR: {e} ({response_time:.3f}s)")
        return {
            "test_id": test_id,
            "query": query,
            "status_code": 500,
            "response_time": response_time,
            "response_data": {"error": str(e)},
            "timestamp": time.time()
        }

async def test_basic_search_functionality():
    """Test 1: Basic search functionality"""
    print("\n🔍 TEST 1: Basic Search Functionality")
    print("-" * 40)
    
    test_queries = [
        "python",
        "test",
        "main",
        "file",
        "document"
    ]
    
    results = SearchTestResults()
    
    async with aiohttp.ClientSession() as session:
        for i, query in enumerate(test_queries):
            result = await single_search_request(query, session, f"BASIC-{i+1}")
            results.add_result(result["status_code"], result["response_time"], result["response_data"])
            await asyncio.sleep(0.1)  # Small delay between requests
    
    print(f"\n📊 Basic Search Results:")
    print(f"   Successful: {results.successful_responses}/{len(test_queries)}")
    return results

async def test_rapid_fire_invalidation():
    """Test 2: Rapid-fire search requests to test invalidation"""
    print("\n⚡ TEST 2: Rapid-Fire Search Invalidation")
    print("-" * 40)
    
    # Send 10 rapid requests with slight delays
    queries = [f"search{i}" for i in range(10)]
    results = SearchTestResults()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        
        for i, query in enumerate(queries):
            # Create task with small staggered delays
            task = asyncio.create_task(
                asyncio.sleep(i * 0.05) and single_search_request(query, session, f"RAPID-{i+1}")
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in completed_results:
            if isinstance(result, dict):
                results.add_result(result["status_code"], result["response_time"], result["response_data"])
    
    print(f"\n📊 Rapid-Fire Results:")
    print(f"   Successful: {results.successful_responses}")
    print(f"   Superseded: {results.superseded_responses}")
    print(f"   Expected: Most requests should be superseded except the last few")
    
    return results

async def test_concurrent_search_limits():
    """Test 3: Test concurrent search limits (semaphore)"""
    print("\n🔄 TEST 3: Concurrent Search Limits")
    print("-" * 40)
    
    # Send 6 concurrent requests (should hit the limit of 3)
    queries = [f"concurrent{i}" for i in range(6)]
    results = SearchTestResults()
    
    async with aiohttp.ClientSession() as session:
        # Start all requests simultaneously
        tasks = [
            single_search_request(query, session, f"CONCURRENT-{i+1}")
            for i, query in enumerate(queries)
        ]
        
        # Wait for all to complete
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in completed_results:
            if isinstance(result, dict):
                results.add_result(result["status_code"], result["response_time"], result["response_data"])
    
    print(f"\n📊 Concurrent Limits Results:")
    print(f"   Total requests: {len(queries)}")
    print(f"   Successful: {results.successful_responses}")
    print(f"   Superseded: {results.superseded_responses}")
    
    return results

async def test_generation_invalidation_timing():
    """Test 4: Test precise timing of generation invalidation"""
    print("\n⏱️  TEST 4: Generation Invalidation Timing")
    print("-" * 40)
    
    results = SearchTestResults()
    
    async with aiohttp.ClientSession() as session:
        # Get initial status
        initial_status = await get_backend_status()
        if initial_status:
            initial_gen = initial_status.get("search", {}).get("current_generation", 0)
            print(f"   Initial generation: {initial_gen}")
        
        # Start a long search
        task1 = asyncio.create_task(
            single_search_request("longsearch1", session, "TIMING-1")
        )
        
        # Wait a bit, then start another search
        await asyncio.sleep(0.1)
        task2 = asyncio.create_task(
            single_search_request("longsearch2", session, "TIMING-2")
        )
        
        # Wait a bit more, then start a third
        await asyncio.sleep(0.1)
        task3 = asyncio.create_task(
            single_search_request("longsearch3", session, "TIMING-3")
        )
        
        # Wait for all to complete
        result1, result2, result3 = await asyncio.gather(task1, task2, task3)
        
        for result in [result1, result2, result3]:
            results.add_result(result["status_code"], result["response_time"], result["response_data"])
        
        # Get final status
        final_status = await get_backend_status()
        if final_status:
            final_gen = final_status.get("search", {}).get("current_generation", 0)
            print(f"   Final generation: {final_gen}")
            print(f"   Generation increment: {final_gen - initial_gen if initial_status else 'N/A'}")
    
    print(f"\n📊 Timing Results:")
    print(f"   Expected: Earlier searches should be superseded")
    print(f"   Successful: {results.successful_responses}")
    print(f"   Superseded: {results.superseded_responses}")
    
    return results

async def test_search_with_no_results():
    """Test 5: Search queries that return no results"""
    print("\n🔍 TEST 5: No Results Handling")
    print("-" * 40)
    
    # Queries unlikely to return results
    no_result_queries = [
        "xyzabc123nonexistent",
        "qwertyuiopasdfgh",
        "impossiblefilename999"
    ]
    
    results = SearchTestResults()
    
    async with aiohttp.ClientSession() as session:
        for i, query in enumerate(no_result_queries):
            result = await single_search_request(query, session, f"NORESULT-{i+1}")
            results.add_result(result["status_code"], result["response_time"], result["response_data"])
    
    print(f"\n📊 No Results Test:")
    print(f"   404 responses: {results.not_found_responses}")
    print(f"   Expected: All should return 404")
    
    return results

async def test_stress_test():
    """Test 6: Stress test with many rapid requests"""
    print("\n💪 TEST 6: Stress Test")
    print("-" * 40)
    
    num_requests = 20
    queries = [f"stress{i}" for i in range(num_requests)]
    results = SearchTestResults()
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        # Create all tasks with minimal delays
        tasks = []
        for i, query in enumerate(queries):
            task = asyncio.create_task(
                single_search_request(query, session, f"STRESS-{i+1}")
            )
            tasks.append(task)
            await asyncio.sleep(0.01)  # Very small delay
        
        # Wait for all to complete
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in completed_results:
            if isinstance(result, dict):
                results.add_result(result["status_code"], result["response_time"], result["response_data"])
    
    total_time = time.time() - start_time
    
    print(f"\n📊 Stress Test Results:")
    print(f"   Total time: {total_time:.3f}s")
    print(f"   Requests/second: {num_requests/total_time:.2f}")
    print(f"   Successful: {results.successful_responses}")
    print(f"   Superseded: {results.superseded_responses}")
    
    return results

async def run_all_tests():
    """Run all test suites"""
    print("🚀 Starting Comprehensive Search Generation Tests")
    print("="*60)
    
    # Check backend health first
    if not await check_backend_health():
        print("❌ Backend is not healthy. Please start the backend first.")
        return False
    
    # Get initial status
    initial_status = await get_backend_status()
    if initial_status:
        print(f"📊 Initial Backend Status:")
        search_info = initial_status.get("search", {})
        print(f"   Generation: {search_info.get('current_generation', 'N/A')}")
        print(f"   Concurrent searches: {search_info.get('concurrent_searches', 'N/A')}")
        print(f"   Max concurrent: {search_info.get('max_concurrent_searches', 'N/A')}")
    
    # Run all tests
    all_results = SearchTestResults()
    
    test_functions = [
        test_basic_search_functionality,
        test_rapid_fire_invalidation,
        test_concurrent_search_limits,
        test_generation_invalidation_timing,
        test_search_with_no_results,
        test_stress_test
    ]
    
    for test_func in test_functions:
        try:
            test_result = await test_func()
            
            # Aggregate results
            all_results.total_requests += test_result.total_requests
            all_results.successful_responses += test_result.successful_responses
            all_results.superseded_responses += test_result.superseded_responses
            all_results.timeout_responses += test_result.timeout_responses
            all_results.not_found_responses += test_result.not_found_responses
            all_results.error_responses += test_result.error_responses
            all_results.response_times.extend(test_result.response_times)
            
            # Small delay between test suites
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"❌ Test {test_func.__name__} failed: {e}")
    
    # Print overall summary
    all_results.print_summary()
    
    # Get final status
    final_status = await get_backend_status()
    if final_status:
        print(f"\n📊 Final Backend Status:")
        search_info = final_status.get("search", {})
        print(f"   Generation: {search_info.get('current_generation', 'N/A')}")
        print(f"   Concurrent searches: {search_info.get('concurrent_searches', 'N/A')}")
    
    return True

if __name__ == "__main__":
    print("Generation-Based Search Test Suite")
    print("Make sure the backend is running on http://127.0.0.1:8000")
    print()
    
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        sys.exit(1)