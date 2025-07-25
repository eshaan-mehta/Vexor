import os
from watchdog.events import FileSystemEventHandler
from watchdog.events import DirModifiedEvent, FileModifiedEvent, DirCreatedEvent, FileCreatedEvent, DirMovedEvent, FileMovedEvent, DirDeletedEvent, FileDeletedEvent
import time
from processing.file_processing_queue import FileProcessingQueue, FileTask, TaskType

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, file_processing_queue: FileProcessingQueue):
        self.file_processing_queue = file_processing_queue
        self.last_modified_times = {} # map store previous modification times for debouncing
        self.debounce_time = 2  # seconds to wait before processing a change
    
    def __wait_until_file_is_closed(self, file_path):
        """Waits until the file is fully closed before re-indexing."""
        while True:
            try:
                # Try opening the file exclusively (will fail if another program is using it)
                with open(file_path, "rb"):
                    return True  # File is now accessible
            except IOError:
                time.sleep(1)  # Wait a bit before checking again
                
    
    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent):
        # on modify, check if file is in queue to be indexed
        # add file to queue/list to be indexed if not already in queue
        # spawn new process that will handle indexing
        # the process will wait for the file to close before indexing
        # send a signal to the process to start indexing
        # remove the file from the queue
        print(event)
        if not event.is_directory and os.path.isfile(event.src_path):
            current_time = time.time()
            # Check if we've processed this file recently (debouncing)
            if event.src_path in self.last_modified_times:
                if current_time - self.last_modified_times[event.src_path] < self.debounce_time:
                    return
            
            self.last_modified_times[event.src_path] = current_time
            print(f"\nFile modified: {event.src_path}")
            # Wait until the file is closed before indexing
            if self.__wait_until_file_is_closed(event.src_path):
                print("File is closed, adding to queue...")
                task = FileTask(
                    task_type=TaskType.INDEX_FILE,
                    file_path=event.src_path
                )
                self.file_processing_queue.add_task(task)
    
    def on_created(self, event: DirCreatedEvent | FileCreatedEvent):
        # TODO: add to index queue
        print(event)
        if not event.is_directory and os.path.isfile(event.src_path):
            # Wait briefly to ensure file is completely written
            time.sleep(1)
            print(f"\nFile created: {event.src_path}")
            task = FileTask(
                task_type=TaskType.INDEX_FILE,
                file_path=event.src_path
            )
            self.file_processing_queue.add_task(task)
    
    def on_moved(self, event: DirMovedEvent | FileMovedEvent):
        print(event)

        if not event.is_directory:
            # Handle file rename/move
            print(f"\nFile moved: {event.src_path} -> {event.dest_path}")
            # Create a move task with metadata
            task = FileTask(
                task_type=TaskType.MOVE_FILE,
                file_path=event.dest_path,
                metadata={
                    'old_path': event.src_path,
                    'new_path': event.dest_path
                }
            )
            self.file_processing_queue.add_task(task)
    
    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent):
        print(event)
        
        if not event.is_directory:
            print(f"\nFile deleted: {event.src_path}")
            task = FileTask(
                task_type=TaskType.DELETE_FILE,
                file_path=event.src_path
            )
            self.file_processing_queue.add_task(task)