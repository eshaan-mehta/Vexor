"""
Configuration file for the File Search API backend.
All configurable constants are defined here for easy management.
"""

# Database Configuration
CHROMA_DB_PATH = "./.chroma"
METADATA_COLLECTION_NAME = "file_metadata"
CONTENT_COLLECTION_NAME = "file_content"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Vector Database Settings
HNSW_SPACE = "cosine"
HNSW_CONSTRUCTION_EF = 100
HNSW_SEARCH_EF = 100
HNSW_M = 16

# Threading Configuration
NUM_CONCURRENT_SEARCHERS_ALLOWED = 3
MAX_INDEXING_THREADS = 1
NUM_FILE_PROCESSING_WORKERS = 8

# Search Configuration
DEFAULT_SEARCH_LIMIT = 10
SEARCH_TIMEOUT_SECONDS = 5.0
SEARCH_REQUEST_ID_PREFIX = "search-"

# Indexing Configuration
INDEXING_TIMEOUT_SECONDS = 300  # 5 minutes
INDEXING_PROGRESS_CHECK_INTERVAL = 0.5  # 500ms
INDEXING_DEBUG_OUTPUT_INTERVAL = 30  # 30 seconds
DEFAULT_DIRECTORY = "~/Desktop"

# Server Configuration
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
SERVER_LOG_LEVEL = "info"
API_TITLE = "File Search API"
API_DESCRIPTION = "FastAPI backend for native macOS file search application"
API_VERSION = "1.0.0"

# Shutdown Configuration
SHUTDOWN_TIMEOUT_SECONDS = 10
EMERGENCY_SHUTDOWN_TIMEOUT_SECONDS = 3

# CORS Configuration
CORS_ALLOW_ORIGINS = ["*"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# Initial Progress Values
INITIAL_FILES_PROCESSED = 0
INITIAL_TOTAL_FILES = 0
INITIAL_PROGRESS = 0.0

# Processing Stats Initial Values
INITIAL_SUCCESS_COUNT = 0
INITIAL_SKIPPED_COUNT = 0
INITIAL_HIDDEN_COUNT = 0
INITIAL_LARGE_COUNT = 0
INITIAL_FAILURE_COUNT = 0

# Directory Skip Patterns for Indexing
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
    'test', 'train', 'validation'   # ML datasets
}

# Environment Variables for ChromaDB
CHROMA_ENV_VARS = {
    "ANONYMIZED_TELEMETRY": "False",
    "CHROMA_TELEMETRY_DISABLED": "True"
}