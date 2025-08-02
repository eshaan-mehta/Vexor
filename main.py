import os
import asyncio
import threading
import time
import signal
import sys
import gc
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

# Import configuration
from config import *

# Disable ChromaDB telemetry completely
for key, value in CHROMA_ENV_VARS.items():
    os.environ[key] = value

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from db.searcher import Searcher
from models import (
    SearchRequest, SearchResult, SearchResponse, 
    DirectorySelectionRequest, IndexingProgress,
    HealthResponse, StatusResponse, DirectorySelectionResponse
)

from processing.file_processor import FileProcessor, ProcessingStatus
from processing.file_processing_queue import FileProcessingQueue, FileTask, TaskType

from filesystem.filechangehandler import FileChangeHandler
from watchdog.observers import Observer

from utils.logging_utils import thread_safe_print, get_print_lock
from utils.worker_utils import start_file_processing_workers, stop_file_processing_workers

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


# Global instances
file_processing_queue = None
file_processing_workers = []
print_lock = get_print_lock()  # Get the global print lock from utils
searcher = None
file_observer = None
search_executor = None
indexing_executor = None
current_directory = None

# Generation-based search invalidation system
search_generation = INITIAL_FILES_PROCESSED
search_generation_lock = threading.Lock()
search_semaphore = None  # Will be initialized in lifespan

indexing_progress = {
    "isIndexing": False,
    "currentFile": None,
    "filesProcessed": INITIAL_FILES_PROCESSED,
    "totalFiles": INITIAL_TOTAL_FILES,
    "progress": INITIAL_PROGRESS
}

# Status tracking for detailed reporting
processing_stats = {
    "success": INITIAL_SUCCESS_COUNT,
    "skipped": INITIAL_SKIPPED_COUNT,
    "hidden": INITIAL_HIDDEN_COUNT,
    "large": INITIAL_LARGE_COUNT,
    "failure": INITIAL_FAILURE_COUNT
}

# Pydantic models are now imported from models.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global file_processing_queue, file_processing_workers, processing_stats, searcher, search_executor, indexing_executor, file_observer, current_directory
    
    print("Starting FastAPI backend...")
    
    # Initialize database and create collections if they don't exist
    db_client = initialize_database(CHROMA_DB_PATH)
    
    # Initialize components
    file_processing_queue = FileProcessingQueue()
    searcher = Searcher(client=db_client)
    
    # Start file processing workers
    start_file_processing_workers(
        file_processing_queue=file_processing_queue,
        file_processing_workers=file_processing_workers,
        processing_stats=processing_stats,
        num_workers=NUM_FILE_PROCESSING_WORKERS
    )
    
    # Create thread pools
    search_executor = ThreadPoolExecutor(max_workers=NUM_CONCURRENT_SEARCHERS_ALLOWED, thread_name_prefix="search")
    indexing_executor = ThreadPoolExecutor(max_workers=MAX_INDEXING_THREADS, thread_name_prefix="indexing")
    
    # Initialize search semaphore to limit concurrent searches
    global search_semaphore
    search_semaphore = asyncio.Semaphore(NUM_CONCURRENT_SEARCHERS_ALLOWED)
    
    # Set default directory and start indexing
    default_dir = os.path.expanduser(DEFAULT_DIRECTORY)
    if os.path.exists(default_dir):
         # Start file observer for the default directory
        print(f"Starting file observer for {default_dir}...")
        file_watcher = FileChangeHandler(file_processing_queue)
        file_observer = Observer()
        file_observer.schedule(file_watcher, path=default_dir, recursive=True)
        file_observer.start()
        
        print(f"Starting initial indexing of {default_dir}...")
        # Run initial indexing asynchronously using executor (proper async/await)
        loop = asyncio.get_event_loop()
        
        # Schedule the task but don't await it (fire and forget)
        _ = loop.run_in_executor(indexing_executor, index_directory_sync, default_dir)
        print("Initial indexing started in background, application ready")
    
    print("FastAPI backend started successfully")
    
    yield
    
    # Shutdown
    print("Shutting down FastAPI backend...")
    
    # Set overall shutdown timeout to prevent hanging
    import signal
    
    def shutdown_timeout_handler(signum, frame):
        print("Shutdown timeout reached - forcing immediate exit")
        import os
        os._exit(1)
    
    # Set timeout for entire shutdown process
    signal.signal(signal.SIGALRM, shutdown_timeout_handler)
    signal.alarm(SHUTDOWN_TIMEOUT_SECONDS)
    
    try:
        # Invalidate any ongoing search requests by incrementing generation
        global search_generation
        with search_generation_lock:
            search_generation += 1
            print(f"Invalidating ongoing searches (generation now {search_generation})")
        
        if file_observer:
            print("Stopping file observer...")
            file_observer.stop()
            # Don't wait for join - it might hang
            
        if file_processing_queue:
            print("Stopping file processing workers...")
            stop_file_processing_workers(
                file_processing_queue=file_processing_queue,
                file_processing_workers=file_processing_workers
            )
        
        # Shutdown executors with timeout protection (non-blocking)
        print("Shutting down thread executors...")
        
        if search_executor:
            try:
                search_executor.shutdown(wait=False)
                print("Search executor shutdown initiated")
            except Exception as e:
                print(f"Error shutting down search executor: {e}")
        
        if indexing_executor:
            try:
                indexing_executor.shutdown(wait=False)
                print("Indexing executor shutdown initiated")
            except Exception as e:
                print(f"Error shutting down indexing executor: {e}")
    
    except Exception as e:
        print(f"Error during initial shutdown: {e}")
    
    # Explicit cleanup for all components that might have resources
    try:
        print("Cleaning up resources...")
        
        # Clean up searcher
        if searcher:
            try:
                searcher.cleanup()
                print("Searcher cleaned up")
            except Exception as e:
                print(f"Error cleaning up searcher: {e}")
        
        # Clean up file processing queue
        if file_processing_queue:
            try:
                file_processing_queue.cleanup()
                print("File processing queue cleaned up")
            except Exception as e:
                print(f"Error cleaning up file processing queue: {e}")
        
        # Clean up file observer
        if file_observer:
            try:
                if hasattr(file_observer, 'cleanup'):
                    file_observer.cleanup()
                print("File observer cleaned up")
            except Exception as e:
                print(f"Error cleaning up file observer: {e}")
        
        # Clear all global references to trigger __del__ methods
        searcher = None
        file_processing_queue = None
        file_observer = None
        search_executor = None
        indexing_executor = None
        
        # Clear worker list
        file_processing_workers.clear()
        
        # Force garbage collection to ensure all __del__ methods are called
        gc.collect()
        
        # Cancel the shutdown timeout
        signal.alarm(0)
        print("All resources cleaned up successfully")
        
    except Exception as e:
        print(f"Error during resource cleanup: {e}")
        # Still try garbage collection even if cleanup failed
        try:
            gc.collect()
        except:
            pass
        # Cancel timeout even if cleanup failed
        signal.alarm(0)
    
    print("FastAPI backend shutdown complete")

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan
)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,  # Configure appropriately for production
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)


def initialize_database(db_path, 
                       metadata_collection_name: str = METADATA_COLLECTION_NAME,
                       content_collection_name: str = CONTENT_COLLECTION_NAME):
    """
    Initialize ChromaDB database and create collections if they don't exist.
    This ensures the searcher can connect to existing collections.
    """
    try:
        print("Initializing database...")
        
        # Create database directory if it doesn't exist
        os.makedirs(db_path, exist_ok=True)
        
        # Initialize ChromaDB client with telemetry completely disabled
        settings = Settings(
            anonymized_telemetry=False,
            allow_reset=True,
            is_persistent=True
        )
        
        client = chromadb.PersistentClient(
            path=db_path,
            settings=settings
        )
        
        # Create embedding function
        embedding_function = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL_NAME)
        
        # Create or get collections
        metadata_collection = client.get_or_create_collection(
            name=metadata_collection_name,
            embedding_function=embedding_function,
            metadata={
                "hnsw:space": HNSW_SPACE,
                "hnsw:construction_ef": HNSW_CONSTRUCTION_EF,
                "hnsw:search_ef": HNSW_SEARCH_EF,
                "hnsw:M": HNSW_M
            }
        )
        
        content_collection = client.get_or_create_collection(
            name=content_collection_name,
            embedding_function=embedding_function,
            metadata={
                "hnsw:space": HNSW_SPACE,
                "hnsw:construction_ef": HNSW_CONSTRUCTION_EF,
                "hnsw:search_ef": HNSW_SEARCH_EF,
                "hnsw:M": HNSW_M
            }
        )
        
        print(f"Database initialized successfully:")
        print(f"  - Metadata collection: {metadata_collection.name} ({metadata_collection.count()} items)")
        print(f"  - Content collection: {content_collection.name} ({content_collection.count()} items)")
        
        # Return the client for reuse by searcher
        return client
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

def get_next_search_generation():
    """Get the next search generation number (thread-safe)"""
    global search_generation
    with search_generation_lock:
        search_generation += 1
        return search_generation

def search_files_with_generation(query: str, limit: int, generation: int, request_id: str) -> Optional[List[dict]]:
    """Synchronous search function with generation-based invalidation"""
    try:
        print(f"Starting search {request_id} (gen {generation}): {query}")
        
        # Check if invalidated before starting
        with search_generation_lock:
            if generation != search_generation:
                print(f"Search {request_id} (gen {generation}) invalidated before execution (current gen {search_generation})")
                return None
        
        # Perform the actual search
        results = searcher.search(query, limit=limit)
        
        # Check if invalidated after completion
        with search_generation_lock:
            if generation != search_generation:
                print(f"Search {request_id} (gen {generation}) invalidated after execution (current gen {search_generation})")
                return None
        
        print(f"Search {request_id} (gen {generation}) completed with {len(results)} results")
        return results
        
    except Exception as e:
        print(f"Search error for {request_id} (gen {generation}): {e}")
        return None

def index_directory_sync(directory_path: str):
    """Synchronous directory indexing function to run in thread pool"""
    global indexing_progress, file_observer, current_directory, file_processing_queue, processing_stats
    
    try:
        # Reset progress and stats
        indexing_progress.update({
            "isIndexing": True,
            "currentFile": None,
            "filesProcessed": INITIAL_FILES_PROCESSED,
            "totalFiles": INITIAL_TOTAL_FILES,
            "progress": INITIAL_PROGRESS
        })
        
        # Reset processing stats
        with print_lock:
            processing_stats.update({
                "success": INITIAL_SUCCESS_COUNT,
                "skipped": INITIAL_SKIPPED_COUNT,
                "hidden": INITIAL_HIDDEN_COUNT,
                "large": INITIAL_LARGE_COUNT,
                "failure": INITIAL_FAILURE_COUNT
            })
        
        print(f"Starting indexing of directory: {directory_path}")
        
        # Walk directory and add ALL files to queue (let workers decide what to process)
        files_added = INITIAL_FILES_PROCESSED
        
        # Use configured directories to skip during indexing
        
        for root, dirs, files in os.walk(directory_path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [d for d in dirs if not (
                d.startswith('.') or 
                d.startswith('__') or 
                d.lower() in SKIP_DIRECTORIES
            )]
            
            for file in files:
                file_path = os.path.join(root, file)
                task = FileTask(
                    task_type=TaskType.INDEX_FILE,
                    file_path=file_path
                )
                file_processing_queue.add_task(task)
                files_added += 1
        
        indexing_progress["totalFiles"] = files_added
        print(f"Added {files_added} files to processing queue")
        
        # Wait for all tasks to complete and track progress with timeout
        start_time = time.time()
        timeout_seconds = INDEXING_TIMEOUT_SECONDS
        
        while True:
            # Get progress from the queue
            queue_progress = file_processing_queue.get_progress()
            
            # Update our indexing progress
            total_completed = queue_progress['total_processed'] + queue_progress['total_failed']
            progress = total_completed / files_added if files_added > INITIAL_FILES_PROCESSED else 1.0
            
            indexing_progress.update({
                "filesProcessed": total_completed,
                "progress": progress
            })
            
            # Check if all tasks are complete
            if not queue_progress['is_processing'] and queue_progress['queue_size'] == INITIAL_FILES_PROCESSED:
                print("All tasks completed successfully")
                break
            
            # Check for timeout
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_seconds:
                print(f"Indexing timeout after {timeout_seconds} seconds - forcing completion")
                print(f"Progress: {total_completed}/{files_added} files processed")
                print(f"Queue state: is_processing={queue_progress['is_processing']}, queue_size={queue_progress['queue_size']}")
                break
            
            # Alternative completion check - if we've processed all files
            if total_completed >= files_added and queue_progress['queue_size'] == INITIAL_FILES_PROCESSED:
                print("All files processed - completing indexing")
                break
            
            # Debug output every configured interval
            if elapsed_time > 0 and int(elapsed_time) % INDEXING_DEBUG_OUTPUT_INTERVAL == 0 and elapsed_time - int(elapsed_time) < 0.5:
                print(f"Indexing progress: {total_completed}/{files_added} files, queue_size={queue_progress['queue_size']}, is_processing={queue_progress['is_processing']}")
                
            time.sleep(INDEXING_PROGRESS_CHECK_INTERVAL)
        
        # Final progress update
        final_progress = file_processing_queue.get_progress()
        indexing_progress.update({
            "isIndexing": False,
            "currentFile": None,
            "filesProcessed": final_progress['total_processed'],
            "totalFiles": files_added,
            "progress": 1.0
        })
        
        current_directory = directory_path
        final_stats = file_processing_queue.get_progress()
        
        # Print detailed completion stats
        with print_lock:
            stats_copy = processing_stats.copy()
        
        print(f"Completed processing {final_stats['total_processed']} files from {directory_path}")
        print(f"  SUCCESS: {stats_copy['success']} files indexed")
        print(f"  SKIPPED: {stats_copy['skipped']} files (unchanged since last index)")
        print(f"  LARGE:   {stats_copy['large']} files (too large to process)")
        print(f"  HIDDEN:  {stats_copy['hidden']} files (hidden/temporary)")
        print(f"  FAILURE: {stats_copy['failure']} files (errors during processing)")
        print(f"  TOTAL:   {sum(stats_copy.values())} files processed")
        
    except Exception as e:
        print(f"Indexing error: {e}")
        indexing_progress.update({
            "isIndexing": False,
            "currentFile": None,
            "filesProcessed": INITIAL_FILES_PROCESSED,
            "totalFiles": INITIAL_TOTAL_FILES,
            "progress": INITIAL_PROGRESS
        })

    return

async def set_directory_internal(directory_path: str):
    """Internal function to set directory and start indexing"""
    if not os.path.exists(directory_path):
        raise HTTPException(status_code=400, detail="Directory does not exist")
    
    if not os.path.isdir(directory_path):
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    # Update file observer to watch new directory if it's different
    if current_directory != directory_path and file_observer:
        print(f"Updating file observer from {current_directory} to {directory_path}")
        # Stop watching the old directory
        file_observer.unschedule_all()
        # Start watching the new directory
        file_watcher = FileChangeHandler(file_processing_queue)
        file_observer.schedule(file_watcher, path=directory_path, recursive=True)
        print(f"File observer now watching {directory_path}")
    
    # Start indexing in background thread
    loop = asyncio.get_event_loop()
    loop.run_in_executor(indexing_executor, index_directory_sync, directory_path)

@app.post("/search", response_model=SearchResponse)
async def search_endpoint(request: SearchRequest):
    """Search for files based on query with generation-based invalidation"""
    if not searcher:
        raise HTTPException(status_code=503, detail="Search service not initialized")
    
    start_time = datetime.now()
    request_id = f"{SEARCH_REQUEST_ID_PREFIX}{int(start_time.timestamp() * 1000)}"
    
    # Get generation for this search (invalidates all previous searches)
    generation = get_next_search_generation()
    
    print(f"New search request {request_id} (gen {generation}): {request.query}")
    
    try:
        # blocks if over n requests are running
        async with search_semaphore:
            # Run search in thread pool with timeout
            loop = asyncio.get_event_loop()
            
            # Execute search with generation-based invalidation
            try:
                results = await asyncio.wait_for(
                    loop.run_in_executor(
                        search_executor,
                        search_files_with_generation,
                        request.query,
                        request.limit,
                        generation,
                        request_id
                    ),
                    timeout=SEARCH_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                print(f"Search {request_id} (gen {generation}) timed out after {SEARCH_TIMEOUT_SECONDS} seconds")
                raise HTTPException(status_code=408, detail="Search request timed out")
            
            # Check if results were invalidated
            if results is None:
                print(f"Search {request_id} (gen {generation}) was superseded by newer request")
                raise HTTPException(status_code=499, detail="Search was superseded by newer request")
            
            if not results:
                raise HTTPException(status_code=404, detail="No results found")
            
            search_time = (datetime.now() - start_time).total_seconds()
            
            # Convert results to API format
            search_results = []
            for result in results:
                metadata = result['metadata']
                search_results.append(SearchResult(
                    fileName=metadata['name'],
                    filePath=metadata['path'],
                    score=result['total_score'],
                    fileType=metadata.get('extension', ''),
                    lastModified=metadata['modified_at']
                ))
            
            print(f"Search {request_id} (gen {generation}) completed successfully in {search_time:.3f}s with {len(search_results)} results")
            
            return SearchResponse(
                results=search_results,
                totalCount=len(search_results),
                searchTime=search_time,
                requestId=request_id
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Unexpected error in search {request_id} (gen {generation}): {e}")
        raise HTTPException(status_code=500, detail=f"Internal search error: {str(e)}")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "file_processing_queue": file_processing_queue is not None and not file_processing_queue.is_shutdown(),
            "searcher": searcher is not None,
            "file_watcher": file_observer is not None and file_observer.is_alive() if file_observer else False
        }
    }

@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get backend status and indexing information"""
    # Get current search generation and semaphore status
    with search_generation_lock:
        current_gen = search_generation
    
    # Get semaphore availability (how many concurrent searches are running)
    available_search_slots = search_semaphore._value if search_semaphore else 0
    concurrent_searches = NUM_CONCURRENT_SEARCHERS_ALLOWED - available_search_slots # num running
    
    return {
        "status": "running",
        "current_directory": current_directory,
        "indexing": indexing_progress,
        "search": {
            "current_generation": current_gen,
            "concurrent_searches": concurrent_searches,
            "max_concurrent_searches": NUM_CONCURRENT_SEARCHERS_ALLOWED
        },
        "timestamp": datetime.now().isoformat()
    }

@app.post("/set-directory", response_model=DirectorySelectionResponse)
async def set_directory(request: DirectorySelectionRequest):
    """Set the directory to index and search"""
    await set_directory_internal(request.directoryPath)
    
    return {
        "status": "success",
        "message": f"Started indexing directory: {request.directoryPath}",
        "directory": request.directoryPath
    }

@app.get("/indexing-progress", response_model=IndexingProgress)
async def get_indexing_progress():
    """Get current indexing progress"""
    return IndexingProgress(**indexing_progress)

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully with timeout"""
    print(f"\nReceived signal {signum}, initiating emergency shutdown...")
    
    # Set timeout for signal handler
    def emergency_exit(signum, frame):
        print("Emergency shutdown timeout - forcing immediate exit")
        import os
        os._exit(1)
    
    signal.signal(signal.SIGALRM, emergency_exit)
    signal.alarm(EMERGENCY_SHUTDOWN_TIMEOUT_SECONDS)
    
    # Force shutdown of all components
    global file_processing_queue, file_processing_workers, file_observer, search_executor, indexing_executor, search_generation
    
    try:
        # Invalidate any ongoing search requests by incrementing generation
        with search_generation_lock:
            search_generation += 1
            print(f"Emergency stop: invalidating searches (generation now {search_generation})")
        except:
            pass
        
        # Stop file observer immediately
        if file_observer:
            print("Emergency stop: file observer...")
            try:
                file_observer.stop()
            except:
                pass
        
        # Shutdown queue and workers
        if file_processing_queue:
            print("Emergency stop: file processing queue...")
            try:
                file_processing_queue.shutdown()
            except:
                pass
        
        # Force shutdown executors
        if search_executor:
            print("Emergency stop: search executor...")
            try:
                search_executor.shutdown(wait=False)
            except:
                pass
        
        if indexing_executor:
            print("Emergency stop: indexing executor...")
            try:
                indexing_executor.shutdown(wait=False)
            except:
                pass
        
        print("Emergency shutdown completed, forcing exit...")
        
    except Exception as e:
        print(f"Error during emergency shutdown: {e}")
    
    # Cancel alarm and force exit
    signal.alarm(0)
    import os
    os._exit(1)

if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        import uvicorn
        uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level=SERVER_LOG_LEVEL)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, shutting down...")
        signal_handler(signal.SIGINT, None)