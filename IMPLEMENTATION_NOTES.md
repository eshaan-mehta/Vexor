# Implementation Notes

## Code Quality Principles
- **Modular**: Each component has a single responsibility
- **Clean**: Clear naming, minimal complexity, well-structured
- **Readable**: Self-documenting code with clear intent
- **No Duplication**: Refactor existing code rather than duplicate functionality
- **Architecture**: Improve file/class structure if current design isn't intuitive

## Current Code Analysis
- `main.py`: FastAPI backend (recently converted)
- `db/indexer.py`: File indexing with batch processing (needs queue-based refactor)
- `db/searcher.py`: Search functionality (likely needs minimal changes)
- `filesystem/filechangehandler.py`: File watcher (needs integration with queue)

## Refactoring Strategy
1. Analyze existing code for reusable components
2. Identify architectural improvements needed
3. Refactor rather than duplicate functionality
4. Maintain clear separation of concerns
5. Document changes and reasoning at each step

## Task 1 Corrections
- **REMOVED**: Priority system (was overcomplicating the design)
- **SIMPLIFIED**: Queue uses simple FIFO with `queue.Queue`
- **MOVE OPERATIONS**: Single `MOVE_FILE` task type, worker handles delete+add
- **CLEAN DESIGN**: Straightforward queue aligned with original design