"""
Pydantic models for the File Search API.
Contains all request/response models used by the FastAPI endpoints.
"""

from typing import List, Optional
from pydantic import BaseModel
from config import DEFAULT_SEARCH_LIMIT


class SearchRequest(BaseModel):
    """Request model for search endpoint"""
    query: str
    limit: int = DEFAULT_SEARCH_LIMIT


class SearchResult(BaseModel):
    """Individual search result model"""
    fileName: str
    filePath: str
    score: float
    fileType: str
    lastModified: str


class SearchResponse(BaseModel):
    """Response model for search endpoint"""
    results: List[SearchResult]
    totalCount: int
    searchTime: float
    requestId: str


class DirectorySelectionRequest(BaseModel):
    """Request model for directory selection endpoint"""
    directoryPath: str


class IndexingProgress(BaseModel):
    """Model for indexing progress information"""
    isIndexing: bool
    currentFile: Optional[str]
    filesProcessed: int
    totalFiles: int
    progress: float


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str
    timestamp: str
    services: dict


class StatusResponse(BaseModel):
    """Response model for status endpoint"""
    status: str
    current_directory: Optional[str]
    indexing: IndexingProgress
    search: dict
    timestamp: str


class DirectorySelectionResponse(BaseModel):
    """Response model for directory selection endpoint"""
    status: str
    message: str
    directory: str


class ErrorResponse(BaseModel):
    """Standard error response model"""
    detail: str
    error_code: Optional[str] = None
    timestamp: Optional[str] = None