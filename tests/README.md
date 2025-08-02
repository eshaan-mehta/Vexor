# Test Suite for File Search API

This directory contains all test files for the File Search API backend.

## Test Files

### 1. `test_search_generation.py` - Comprehensive Async Test Suite

- **Purpose**: Full async test suite with detailed statistics
- **Features**:
  - 6 different test scenarios
  - Detailed timing and response analysis
  - Concurrent request testing
  - Stress testing with 20+ requests
  - Statistical summaries

### 2. `test_search_simple.py` - Simple Synchronous Tests

- **Purpose**: Easy-to-understand synchronous tests for debugging
- **Features**:
  - Basic search functionality
  - Rapid invalidation testing
  - Concurrent search testing
  - Generation progression tracking

### 3. `test_api.py` - Basic API Tests

- **Purpose**: Simple API endpoint testing
- **Features**:
  - Health check testing
  - Basic search functionality
  - Status endpoint testing

### 4. `run_tests.py` - Test Runner

- **Purpose**: Enhanced test runner with colored output
- **Features**:
  - Colored test results
  - Detailed test statistics
  - Better formatting

## Prerequisites

1. **Backend Running**: Make sure your FastAPI backend is running on `http://127.0.0.1:8000`

   ```bash
   # From project root
   python main.py
   ```

2. **Install Dependencies**:

   ```bash
   pip install aiohttp requests
   ```

3. **Test Data**: Ensure your backend has some indexed files to search

## Running the Tests

### From the tests directory:

```bash
cd tests

# Quick test (recommended for debugging)
python test_search_simple.py

# Comprehensive test suite
python test_search_generation.py

# Basic API tests
python test_api.py

# Run with test runner
python run_tests.py
```

### From the project root:

```bash
# Quick test
python tests/test_search_simple.py

# Comprehensive test suite
python tests/test_search_generation.py

# Basic API tests
python tests/test_api.py

# Run with test runner
python tests/run_tests.py
```

## What the Tests Verify

### ✅ **Basic Functionality**

- Search requests return 200 status codes
- Results contain expected fields (fileName, filePath, score, etc.)
- Response times are reasonable

### ✅ **Generation-Based Invalidation**

- Rapid successive searches invalidate previous ones
- Only the most recent search returns results (status 200)
- Previous searches return 499 "superseded" status
- Generation counter increments correctly

### ✅ **Concurrency Control**

- Maximum 3 concurrent searches (semaphore limit)
- Requests queue properly when limit is exceeded
- No resource exhaustion under load

### ✅ **Error Handling**

- Timeout handling (408 status)
- No results handling (404 status)
- Server error handling (5xx status)

### ✅ **Performance**

- Response times under reasonable limits
- System handles rapid requests without crashing
- Memory usage remains stable

## Expected Test Results

### Rapid Invalidation Test

```
[RAPID-1] Query: 'rapid1' -> Status: 499 (0.123s)
    ⚠️  Search was superseded by newer request
[RAPID-2] Query: 'rapid2' -> Status: 499 (0.145s)
    ⚠️  Search was superseded by newer request
[RAPID-5] Query: 'rapid5' -> Status: 200 (0.234s)
    Results: 3 files, Search time: 0.189s
```

### Concurrent Search Test

```
[WORKER-1] Query: 'concurrent0' -> Status: 499 (0.156s)
[WORKER-3] Query: 'concurrent2' -> Status: 200 (0.201s)
Concurrent Results: 1 successful, 4 superseded
```

### Generation Progression

```
Generation: 5 -> 6
Generation: 6 -> 7
Generation: 7 -> 8
```

## Troubleshooting

### Backend Not Responding

```bash
# Check if backend is running
curl http://127.0.0.1:8000/health

# Expected response:
{"status":"healthy","timestamp":"...","services":{...}}
```

### All Searches Return 404

- Backend might not have indexed files yet
- Check if directory indexing is complete:

```bash
curl http://127.0.0.1:8000/status
```

### Tests Timeout

- Backend might be under heavy load
- Increase timeout values in test files
- Check backend logs for errors

### Import Errors

If you get import errors when running tests, make sure you're running them correctly:

```bash
# From project root (recommended)
python tests/test_search_simple.py

# Or from tests directory
cd tests
python test_search_simple.py
```

## Test Scenarios Explained

### 1. **Basic Search Functionality**

Tests normal search operations with common queries.

### 2. **Rapid-Fire Invalidation**

Sends 10 searches with 50ms delays to test invalidation logic.

### 3. **Concurrent Search Limits**

Sends 6 simultaneous requests to test the 3-search semaphore limit.

### 4. **Generation Invalidation Timing**

Tests precise timing of when searches get invalidated.

### 5. **No Results Handling**

Tests searches that should return no results (404 status).

### 6. **Stress Test**

Sends 20+ rapid requests to test system stability.

## Interpreting Results

### ✅ **Good Results**

- Most rapid searches are superseded (499 status)
- Last search in sequence succeeds (200 status)
- Concurrent searches respect the 3-request limit
- Generation numbers increment correctly
- No 5xx server errors

### ❌ **Concerning Results**

- Multiple searches succeed when they should be superseded
- Generation numbers don't increment
- Frequent timeouts or server errors
- Memory usage grows continuously

## Adding New Tests

### Create a new test file:

```python
#!/usr/bin/env python3
"""
Description of your test
"""

import requests
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://127.0.0.1:8000"

def test_your_functionality():
    """Test description"""
    # Your test code here
    pass

if __name__ == "__main__":
    test_your_functionality()
```

### Integration with CI/CD

These tests can be integrated into automated testing pipelines:

```bash
# Run tests and capture exit code
cd tests
python test_search_simple.py
if [ $? -eq 0 ]; then
    echo "✅ Search tests passed"
else
    echo "❌ Search tests failed"
    exit 1
fi
```
