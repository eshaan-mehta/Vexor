#!/usr/bin/env python3
"""
Test runner for the file search application with enhanced formatting.
"""

import sys
import unittest
import os

# Add parent directory to path so we can import from the main project
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ColoredTestResult(unittest.TextTestResult):
    """Custom test result class with colored output and better formatting."""
    
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.test_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.error_count = 0
    
    def startTest(self, test):
        super().startTest(test)
        self.test_count += 1
        
        # Print test header
        print(f"\n{'='*80}")
        print(f"🧪 TEST {self.test_count}: {test._testMethodName}")
        print(f"📝 Description: {test._testMethodDoc.strip() if test._testMethodDoc else 'No description'}")
        print(f"{'='*80}")
    
    def addSuccess(self, test):
        super().addSuccess(test)
        self.success_count += 1
        print(f"✅ RESULT: PASSED")
        print(f"📊 Expected: Test should complete without errors")
        print(f"📊 Actual: Test completed successfully")
    
    def addError(self, test, err):
        super().addError(test, err)
        self.error_count += 1
        print(f"❌ RESULT: ERROR")
        print(f"📊 Expected: Test should complete without errors")
        print(f"📊 Actual: Test encountered an error")
        print(f"🔍 Error Details:")
        print(f"   {err[1]}")
    
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.failure_count += 1
        print(f"❌ RESULT: FAILED")
        print(f"📊 Expected: Test assertions should pass")
        print(f"📊 Actual: Test assertion failed")
        print(f"🔍 Failure Details:")
        print(f"   {err[1]}")
    
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        print(f"⏭️  RESULT: SKIPPED")
        print(f"📊 Reason: {reason}")


class EnhancedTestRunner(unittest.TextTestRunner):
    """Enhanced test runner with better formatting."""
    
    def __init__(self, **kwargs):
        kwargs['resultclass'] = ColoredTestResult
        kwargs['verbosity'] = 0  # We handle our own output
        super().__init__(**kwargs)
    
    def run(self, test):
        print(f"\n🚀 Starting Test Suite")
        print(f"📦 Total Tests: {test.countTestCases()}")
        print(f"{'='*80}")
        
        result = super().run(test)
        
        # Print summary
        print(f"\n{'='*80}")
        print(f"📋 TEST SUMMARY")
        print(f"{'='*80}")
        print(f"🧪 Total Tests: {result.test_count}")
        print(f"✅ Passed: {result.success_count}")
        print(f"❌ Failed: {result.failure_count}")
        print(f"💥 Errors: {result.error_count}")
        print(f"⏭️  Skipped: {len(result.skipped) if hasattr(result, 'skipped') else 0}")
        
        if result.wasSuccessful():
            print(f"🎉 OVERALL RESULT: ALL TESTS PASSED!")
        else:
            print(f"💔 OVERALL RESULT: SOME TESTS FAILED")
        
        print(f"{'='*80}")
        
        return result


def run_queue_tests():
    """Run queue manager tests with enhanced formatting."""
    print("🔧 FILE PROCESSING QUEUE TESTS")
    
    # Import and run tests
    from tests.test_file_processing_queue import TestFileProcessingQueue
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestFileProcessingQueue)
    
    # Run tests with enhanced runner
    runner = EnhancedTestRunner()
    result = runner.run(suite)
    
    return result.wasSuccessful()


def main():
    """Main test runner."""
    print("🔍 VEXOR SEARCH ENGINE - TEST SUITE")
    print("=" * 80)
    
    success = True
    
    # Run queue tests
    if not run_queue_tests():
        success = False
    
    print(f"\n{'='*80}")
    if success:
        print("🎊 FINAL RESULT: ALL TEST SUITES PASSED!")
        sys.exit(0)
    else:
        print("💥 FINAL RESULT: SOME TEST SUITES FAILED!")
        sys.exit(1)


if __name__ == '__main__':
    main()