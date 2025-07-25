import os
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db.indexer import Indexer
from db.searcher import Searcher

from processing.file_processor import FileProcessor
from processing.file_processing_queue import FileProcessingQueue, FileTask, TaskType

from filesystem.filechangehandler import FileChangeHandler
from watchdog.observers import Observer

# Global instances
file_processing_queue = None
file_processing_workers = []
searcher = None
file_observer = None
search_executor = None
indexing_executor = None
current_directory = None
indexing_progress = {
    "is_indexing": False,
    "current_file": None,
    "files_processed": 0,
    "total_files": 0,
    "progress": 0.0
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
    global file_processing_queue, file_processing_workers, searcher, search_executor, indexing_executor
    
    print("Starting FastAPI backend...")
    
    # Initialize components
    file_processing_queue = FileProcessingQueue()
    searcher = Searcher()
    
    # Start file processing workers
    start_file_processing_workers(num_workers=4)
    
    # Create thread pools
    search_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="search")
    indexing_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="indexing")
    
    # Set default directory and start indexing
    default_dir = os.path.abspath("./test-files")
    if os.path.exists(default_dir):
        print(f"Starting initial indexing of {default_dir}...")
        # Run initial indexing synchronously during startup
        index_directory_sync(default_dir)
        print("Initial indexing completed, application ready")
    
    print("FastAPI backend started successfully")
    
    yield
    
    # Shutdown
    print("Shutting down FastAPI backend...")
    
    if file_observer:
        file_observer.stop()
        file_observer.join()
    
    if file_processing_queue:
        stop_file_processing_workers()
    
    if search_executor:
        search_executor.shutdown(wait=True)
    
    if indexing_executor:
        indexing_executor.shutdown(wait=True)
    
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

def start_file_processing_workers(num_workers: int = 4):
    """Start file processing worker threads."""
    global file_processing_workers, file_processing_queue
    
    print(f"Starting {num_workers} file processing workers...")
    
    for i in range(num_workers):
        worker = threading.Thread(
            target=file_processing_worker_loop,
            name=f"FileProcessor-{i}",
            daemon=True
        )
        worker.start()
        file_processing_workers.append(worker)
    
    print(f"Started {len(file_processing_workers)} file processing workers")

def stop_file_processing_workers():
    """Stop all file processing worker threads gracefully."""
    global file_processing_workers, file_processing_queue
    
    print("Stopping file processing workers...")
    
    if file_processing_queue:
        file_processing_queue.shutdown()
    
    # Wait for all workers to finish
    for worker in file_processing_workers:
        worker.join(timeout=5.0)
    
    file_processing_workers.clear()
    print("File processing workers stopped")

def file_processing_worker_loop():
    """Main loop for file processing worker threads."""
    global file_processing_queue
    
    # Each worker gets its own FileProcessor instance
    processor = FileProcessor()
    worker_name = threading.current_thread().name
    
    print(f"Worker {worker_name} started")
    
    while not file_processing_queue.is_shutdown():
        task = file_processing_queue.get_task(timeout=1.0)
        if task is None:
            continue
        
        try:
            success = processor.process_task(task)
            file_processing_queue.task_completed(task, success)
            
        except Exception as e:
            print(f"Worker {worker_name} error processing {task.file_path}: {e}")
            file_processing_queue.task_completed(task, False)
    
    print(f"Worker {worker_name} stopped")

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
    global indexing_progress, file_observer, current_directory, file_processing_queue
    
    try:
        indexing_progress.update({
            "is_indexing": True,
            "current_file": None,
            "files_processed": 0,
            "total_files": 0,
            "progress": 0.0
        })
        
        print(f"Starting indexing of directory: {directory_path}")
        
        # Stop existing file watcher
        if file_observer:
            file_observer.stop()
            file_observer.join()
        
        # Walk directory and add ALL files to queue (let workers decide what to process)
        files_added = 0
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                task = FileTask(
                    task_type=TaskType.INDEX_FILE,
                    file_path=file_path
                )
                file_processing_queue.add_task(task)
                files_added += 1
        
        indexing_progress["total_files"] = files_added
        print(f"Added {files_added} files to processing queue")
        
        # Wait for all tasks to complete and track progress
        while True:
            # Get progress from the queue
            queue_progress = file_processing_queue.get_progress()
            
            # Update our indexing progress
            total_completed = queue_progress['total_processed'] + queue_progress['total_failed']
            progress = total_completed / files_added if files_added > 0 else 1.0
            
            indexing_progress.update({
                "files_processed": total_completed,
                "progress": progress
            })
            
            # Check if all tasks are complete
            if not queue_progress['is_processing'] and queue_progress['queue_size'] == 0:
                break
                
            time.sleep(0.5)  # Check every 500ms
        
        # Final progress update
        final_progress = file_processing_queue.get_progress()
        indexing_progress.update({
            "is_indexing": False,
            "current_file": None,
            "files_processed": final_progress['total_processed'],
            "total_files": files_added,
            "progress": 1.0
        })
        
        # Start new file watcher
        file_watcher = FileChangeHandler(file_processing_queue)
        file_observer = Observer()
        file_observer.schedule(file_watcher, path=directory_path, recursive=True)
        file_observer.start()
        
        current_directory = directory_path
        final_stats = file_processing_queue.get_progress()
        print(f"Completed processing {final_stats['total_processed']} files from {directory_path} ({final_stats['total_failed']} failed)")
        
    except Exception as e:
        print(f"Indexing error: {e}")
        indexing_progress.update({
            "is_indexing": False,
            "current_file": None,
            "files_processed": 0,
            "total_files": 0,
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
            "file_processing_queue": file_processing_queue is not None and file_processing_queue.is_running(),
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")