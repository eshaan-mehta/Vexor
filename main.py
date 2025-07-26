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

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db.searcher import Searcher

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
indexing_progress = {
    "isIndexing": False,
    "currentFile": None,
    "filesProcessed": 0,
    "totalFiles": 0,
    "progress": 0.0
}

# Status tracking for detailed reporting
processing_stats = {
    "success": 0,
    "skipped": 0,
    "hidden": 0,
    "large": 0,
    "failure": 0
}

# Pydantic models for API
class SearchRequest(BaseModel):
    query: str
    limit: int = 10

class SearchResult(BaseModel):
    fileName: str
    filePath: str
    score: float
    fileType: str
    lastModified: str

class SearchResponse(BaseModel):
    results: List[SearchResult]
    totalCount: int
    searchTime: float
    requestId: str

class DirectorySelectionRequest(BaseModel):
    directoryPath: str

class IndexingProgress(BaseModel):
    isIndexing: bool
    currentFile: Optional[str]
    filesProcessed: int
    totalFiles: int
    progress: float

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global file_processing_queue, file_processing_workers, processing_stats, searcher, search_executor, indexing_executor, file_observer, current_directory
    
    print("Starting FastAPI backend...")
    
    # Initialize database and create collections if they don't exist
    db_client = initialize_database()
    
    # Initialize components
    file_processing_queue = FileProcessingQueue()
    searcher = Searcher(client=db_client)
    
    # Start file processing workers
    start_file_processing_workers(
        file_processing_queue=file_processing_queue,
        file_processing_workers=file_processing_workers,
        processing_stats=processing_stats,
        num_workers=10
    )
    
    # Create thread pools
    search_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="search")
    indexing_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="indexing")
    
    # Set default directory and start indexing
    default_dir = os.path.expanduser("~/Desktop")
    if os.path.exists(default_dir):
        print(f"Starting initial indexing of {default_dir}...")
        # Run initial indexing asynchronously in background
        loop = asyncio.get_event_loop()
        loop.run_in_executor(indexing_executor, index_directory_sync, default_dir)
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
    
    # Set 10-second timeout for entire shutdown process
    signal.signal(signal.SIGALRM, shutdown_timeout_handler)
    signal.alarm(10)
    
    try:
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
    title="File Search API",
    description="FastAPI backend for native macOS file search application",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



def initialize_database(db_path: str = "./chroma", 
                       metadata_collection_name: str = "file_metadata",
                       content_collection_name: str = "file_content"):
    """
    Initialize ChromaDB database and create collections if they don't exist.
    This ensures the searcher can connect to existing collections.
    """
    try:
        print("Initializing database...")
        
        # Create database directory if it doesn't exist
        os.makedirs(db_path, exist_ok=True)
        
        # Initialize ChromaDB client with telemetry disabled
        client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                is_persistent=True
            )
        )
        
        # Create embedding function
        embedding_function = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        
        # Create or get collections (this ensures they exist)
        metadata_collection = client.get_or_create_collection(
            name=metadata_collection_name,
            embedding_function=embedding_function,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 100,
                "hnsw:search_ef": 100,
                "hnsw:M": 16
            }
        )
        
        content_collection = client.get_or_create_collection(
            name=content_collection_name,
            embedding_function=embedding_function,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 100,
                "hnsw:search_ef": 100,
                "hnsw:M": 16
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

def search_files_sync(query: str, limit: int = 10) -> List[dict]:
    """Synchronous search function to run in thread pool"""
    try:
        results = searcher.search(query, limit=limit)
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []

def index_directory_sync(directory_path: str):
    """Synchronous directory indexing function to run in thread pool"""
    global indexing_progress, file_observer, current_directory, file_processing_queue, processing_stats
    
    try:
        # Reset progress and stats
        indexing_progress.update({
            "isIndexing": True,
            "currentFile": None,
            "filesProcessed": 0,
            "totalFiles": 0,
            "progress": 0.0
        })
        
        # Reset processing stats
        with print_lock:
            processing_stats.update({
                "success": 0,
                "skipped": 0,
                "hidden": 0,
                "large": 0,
                "failure": 0
            })
        
        print(f"Starting indexing of directory: {directory_path}")
        
        # Stop existing file watcher
        if file_observer:
            file_observer.stop()
            file_observer.join()
        
        # Walk directory and add ALL files to queue (let workers decide what to process)
        files_added = 0
        
        # Directories to skip during indexing
        SKIP_DIRECTORIES = {
            'venv', 'env', '.venv', '.env',  # Python virtual environments
            'node_modules', '.npm',          # Node.js
            '.git', '.svn', '.hg',          # Version control
            '__pycache__', '.pytest_cache', # Python cache
            '.tox', '.coverage',            # Python testing
            'build', 'dist', '.build',      # Build directories
            '.DS_Store', 'Thumbs.db',       # System files
            '.idea', '.vscode',             # IDE directories
            'target', 'bin', 'obj',         # Compiled output
            '.gradle', '.maven',            # Build tools
            'vendor',                       # Dependencies
        }
        
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
        
        # Wait for all tasks to complete and track progress
        while True:
            # Get progress from the queue
            queue_progress = file_processing_queue.get_progress()
            
            # Update our indexing progress
            total_completed = queue_progress['total_processed'] + queue_progress['total_failed']
            progress = total_completed / files_added if files_added > 0 else 1.0
            
            indexing_progress.update({
                "filesProcessed": total_completed,
                "progress": progress
            })
            
            # Check if all tasks are complete
            if not queue_progress['is_processing'] and queue_progress['queue_size'] == 0:
                break
                
            time.sleep(0.5)  # Check every 500ms
        
        # Final progress update
        final_progress = file_processing_queue.get_progress()
        indexing_progress.update({
            "isIndexing": False,
            "currentFile": None,
            "filesProcessed": final_progress['total_processed'],
            "totalFiles": files_added,
            "progress": 1.0
        })
        
        # Start new file watcher
        file_watcher = FileChangeHandler(file_processing_queue)
        file_observer = Observer()
        file_observer.schedule(file_watcher, path=directory_path, recursive=True)
        file_observer.start()
        
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
            "filesProcessed": 0,
            "totalFiles": 0,
            "progress": 0.0
        })

async def set_directory_internal(directory_path: str):
    """Internal function to set directory and start indexing"""
    if not os.path.exists(directory_path):
        raise HTTPException(status_code=400, detail="Directory does not exist")
    
    if not os.path.isdir(directory_path):
        raise HTTPException(status_code=400, detail="Path is not a directory")
    
    # Start indexing in background thread
    loop = asyncio.get_event_loop()
    loop.run_in_executor(indexing_executor, index_directory_sync, directory_path)

@app.post("/search", response_model=SearchResponse)
async def search_endpoint(request: SearchRequest):
    """Search for files based on query"""
    if not searcher:
        raise HTTPException(status_code=503, detail="Search service not initialized")
    
    start_time = datetime.now()
    
    # Run search in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        search_executor, 
        search_files_sync, 
        request.query, 
        request.limit
    )
    
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
    
    return SearchResponse(
        results=search_results,
        totalCount=len(search_results),
        searchTime=search_time,
        requestId=f"search-{int(start_time.timestamp())}"
    )

@app.get("/health")
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

@app.get("/status")
async def get_status():
    """Get backend status and indexing information"""
    return {
        "status": "running",
        "current_directory": current_directory,
        "indexing": indexing_progress,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/set-directory")
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
    
    # Set a 3-second timeout for signal handler
    def emergency_exit(signum, frame):
        print("Emergency shutdown timeout - forcing immediate exit")
        import os
        os._exit(1)
    
    signal.signal(signal.SIGALRM, emergency_exit)
    signal.alarm(3)
    
    # Force shutdown of all components
    global file_processing_queue, file_processing_workers, file_observer, search_executor, indexing_executor
    
    try:
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
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received, shutting down...")
        signal_handler(signal.SIGINT, None)