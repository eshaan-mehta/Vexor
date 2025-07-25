"""
Logging utilities for thread-safe printing and logging operations.

This module provides utilities for safe logging in multi-threaded environments.
"""

import threading
from datetime import datetime

# Global print lock for thread-safe printing
_print_lock = threading.Lock()


def thread_safe_print(message: str, lock: threading.Lock = None):
    """
    Thread-safe printing function with timestamp.
    
    Args:
        message: The message to print
        lock: Optional lock to use. If None, uses the global print lock.
    """
    if lock is None:
        lock = _print_lock
        
    with lock:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Include milliseconds
        print(f"[{timestamp}] {message}")


def get_print_lock() -> threading.Lock:
    """
    Get the global print lock for use in other modules.
    
    Returns:
        threading.Lock: The global print lock
    """
    return _print_lock