# Implementation Plan

## Backend Implementation (Python)

- [x] 1. Create thread-safe queue infrastructure for file processing
  - Add Python's `queue.Queue()` to handle all file processing tasks
  - Create global queue instance accessible by all processing threads
  - Add queue monitoring functions for progress tracking
  - Implement graceful shutdown mechanism for queue processing
  - _Requirements: 8.1, 8.10_

- [ ] 2. Implement unified file processing worker threads
  - Create worker thread pool with configurable size (default 4 threads)
  - Implement worker function that pulls files from shared queue using `queue.get()`
  - Add individual file processing logic (extract content, generate embeddings)
  - Implement atomic database commits for each processed file
  - Add error handling and logging for failed file processing
  - _Requirements: 8.5, 8.6, 8.7_

- [ ] 3. Create file watcher thread for real-time file monitoring
  - Implement dedicated file watcher thread using watchdog library
  - Start file watcher immediately when backend starts (before directory scanning)
  - Add file change detection for create/modify/move/delete events
  - Implement queue addition for detected file changes using `queue.put()`
  - Add debouncing logic to prevent duplicate processing of rapidly changing files
  - _Requirements: 8.2, 8.4, 8.9_

- [ ] 4. Implement directory scanner thread for initial indexing
  - Create dedicated directory scanner thread for startup indexing
  - Implement directory traversal using `os.walk()` to discover all files
  - Add files to shared processing queue without immediate processing
  - Implement progress tracking based on discovered files vs queue size
  - Ensure scanner runs concurrently with file watcher and worker threads
  - _Requirements: 8.3, 8.8_

- [ ] 5. Remove batch processing from indexer and implement individual commits
  - Remove all batch processing logic from existing indexer code
  - Update indexer to process single files with immediate database commits
  - Ensure ChromaDB operations are thread-safe and atomic
  - Remove batch backup and recovery mechanisms
  - Simplify indexer interface to handle one file at a time
  - _Requirements: 8.6, 8.7_

- [ ] 6. Update FastAPI backend with queue-based architecture
  - Integrate thread-safe queue into existing FastAPI application
  - Initialize file watcher, directory scanner, and worker threads on startup
  - Update existing endpoints to work with new queue-based system
  - Ensure single-threaded search executor remains unchanged
  - Add proper shutdown handling for all threads and queue
  - _Requirements: 8.1, 8.2, 8.5, 8.10_

- [ ] 7. Implement real-time progress tracking for queue-based processing
  - Add progress tracking based on queue size and processed file count
  - Update `/indexing-progress` endpoint to reflect queue-based metrics
  - Implement current file tracking across worker threads
  - Add total files discovered counter from directory scanner
  - Ensure progress updates are thread-safe and accurate
  - _Requirements: 8.8_

- [ ] 8. Add directory selection and reindexing functionality
  - Implement `/set-directory` endpoint with directory validation
  - Add logic to clear existing index when directory changes
  - Restart file watcher and directory scanner with new directory
  - Ensure graceful shutdown of existing processing before restart
  - Add proper error handling for invalid directory paths
  - _Requirements: 6.2, 6.3, 6.7_

- [ ] 9. Enhance search endpoint with proper thread isolation
  - Ensure search operations use dedicated single-threaded executor
  - Verify search doesn't interfere with file processing operations
  - Add request cancellation support for concurrent search requests
  - Implement proper error handling and timeout management
  - Optimize JSON serialization for search responses
  - _Requirements: 5.1, 5.2, 5.5_

- [ ] 10. Add comprehensive backend testing and validation
  - Create test scripts to validate queue-based processing
  - Test concurrent file processing with multiple worker threads
  - Validate thread safety of database operations
  - Test file watcher responsiveness to real-time changes
  - Add performance benchmarks for queue processing throughput
  - _Requirements: 8.6, 8.7_

## Frontend Implementation (Swift/SwiftUI)

- [ ] 11. Set up Swift macOS project structure and core models
  - Create new macOS app project in Xcode with SwiftUI
  - Define SearchResult, SearchRequest, SearchResponse, IndexingProgress, and DirectorySelectionRequest models
  - Add ConnectionStatus enum for connection state management
  - Create basic project structure with folders for Models, Views, Managers, and Services
  - _Requirements: 1.1, 5.2_

- [ ] 12. Implement SettingsManager and directory selection
  - Create SettingsManager as ObservableObject with UserDefaults persistence
  - Add first launch detection and directory selection prompt
  - Implement directory picker using NSOpenPanel for folder selection
  - Add directory validation and permission checking
  - Store selected directory path in UserDefaults for persistence
  - _Requirements: 6.1, 6.4, 6.5, 6.6_

- [ ] 13. Create CommunicationManager for HTTP requests
  - Create CommunicationManager class with URLSession and persistent connections
  - Implement search request method with JSON serialization
  - Add response deserialization with proper error handling
  - Implement exponential backoff retry logic for failed requests
  - Add request timeout handling (5 seconds)
  - _Requirements: 5.1, 5.2, 5.5_

- [ ] 14. Implement SearchManager with threading and debouncing
  - Implement SearchManager as ObservableObject with @Published properties
  - Add debounced search functionality (150ms delay after user stops typing)
  - Create background serial DispatchQueue for search operations
  - Implement request cancellation when new searches start
  - Add connection status tracking and indexing progress monitoring
  - _Requirements: 2.1, 2.3, 2.4, 5.3, 5.4_

- [ ] 15. Create basic SwiftUI search interface
  - Create SearchView with TextField for search input and List for results display
  - Add @State properties for searchText, results array, selectedIndex, and showingDirectoryPicker
  - Implement basic keyboard navigation (arrow keys, Enter, Escape)
  - Add file type icons and result formatting (name, path, relevance score)
  - Integrate directory picker UI for first launch and settings
  - _Requirements: 1.1, 1.3, 1.4, 4.1, 4.2, 4.3, 4.5, 6.1_

- [ ] 16. Add backend discovery and process management
  - Create BackendDiscovery class to scan common ports (8000, 8080, 3000)
  - Implement health check endpoint polling with exponential backoff
  - Add automatic backend process launching if not found
  - Implement connection status monitoring and reconnection logic
  - _Requirements: 3.1, 3.2, 3.3, 3.5_

- [ ] 17. Implement file opening and system integration
  - Add file opening functionality using NSWorkspace.shared.open()
  - Implement "Reveal in Finder" feature with Cmd+Enter shortcut
  - Add proper file path validation and error handling
  - Integrate with macOS default applications for file opening
  - _Requirements: 1.5, 4.4_

- [ ] 18. Add error handling and user feedback
  - Add loading states and progress indicators during search
  - Create user-friendly error messages for connection failures
  - Implement offline mode indication when backend unavailable
  - Add empty state handling when no search results found
  - Create connection status indicator in the UI
  - _Requirements: 3.4, 3.5_

- [ ] 19. Add accessibility and macOS integration features
  - Implement VoiceOver accessibility labels for all UI elements
  - Add visible focus indicators for keyboard navigation
  - Create proper macOS menu bar integration
  - Add application icon and proper app bundle configuration
  - Implement background resource management and app lifecycle handling
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 20. Add performance optimizations and caching
  - Implement result caching for recent searches (LRU cache with 50 entries)
  - Add result limiting to maximum 10 items for UI performance
  - Optimize JSON parsing and model creation on background thread
  - Implement proper memory management and resource cleanup
  - Add request deduplication for identical concurrent queries
  - _Requirements: 2.2, 2.3_

- [ ] 21. Create comprehensive test suite
  - Write unit tests for SearchManager with mocked CommunicationManager
  - Create tests for CommunicationManager with mocked network responses
  - Add model tests for JSON serialization/deserialization
  - Implement integration tests for complete search flow
  - Create UI tests for keyboard navigation and accessibility
  - _Requirements: All requirements validation_

- [ ] 22. Add final polish and deployment preparation
  - Implement proper app signing and notarization setup
  - Add application preferences and settings persistence
  - Create proper error logging and debugging capabilities
  - Add performance monitoring and search latency tracking
  - Implement graceful shutdown and cleanup procedures
  - _Requirements: 6.3, 6.5_
