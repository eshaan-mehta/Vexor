import os
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db.indexer import Indexer
from db.searcher import Searcher
from filesystem.filechangehandler import FileChangeHandler
from watchdog.observers import Observer

# Global instances
indexer = None
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
    global indexer, searcher, search_executor, indexing_executor
    
    print("Starting FastAPI backend...")
    
    # Initialize components
    indexer = Indexer()
    searcher = Searcher()
    
    # Create thread pools
    search_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="search")
    indexing_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="indexing")
    
    # Set default directory and start indexing
    default_dir = os.path.abspath("./test-files")
    if os.path.exists(default_dir):
        await set_directory_internal(default_dir)
    
    print("FastAPI backend started successfully")
    
    yield
    
    # Shutdown
    print("Shutting down FastAPI backend...")
    
    if file_observer:
        file_observer.stop()
        file_observer.join()
    
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
    global indexing_progress, file_observer, current_directory
    
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
        
        # Index directory
        count = indexer.index_directory(directory_path, cleanup_deleted=True, use_batch=True)
        
        # Update progress
        indexing_progress.update({
            "is_indexing": False,
            "current_file": None,
            "files_processed": count,
            "total_files": count,
            "progress": 1.0
        })
        
        # Start new file watcher
        file_watcher = FileChangeHandler(indexer)
        file_observer = Observer()
        file_observer.schedule(file_watcher, path=directory_path, recursive=True)
        file_observer.start()
        
        current_directory = directory_path
        print(f"Completed indexing {count} files from {directory_path}")
        
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
            "indexer": indexer is not None,
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