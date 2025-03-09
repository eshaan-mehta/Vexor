import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from watchdog.events import DirModifiedEvent, FileModifiedEvent, DirCreatedEvent, FileCreatedEvent, DirMovedEvent, FileMovedEvent, DirDeletedEvent, FileDeletedEvent
import time
from typing import Any
from indexer import Indexer

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, indexer: Indexer):
        self.indexer = indexer
        self.last_modified_times = {} # map store previous modification times for debouncing
        self.debounce_time = 2  # seconds to wait before processing a change
    
    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent):
        # on modify, check if file is in queue to be indexed
        # add file to queue/list to be indexed if not already in queue
        # spawn new process that will handle indexing
        # the process will wait for the file to close before indexing
        # send a signal to the process to start indexing
        # remove the file from the queue



        if not event.is_directory and os.path.isfile(event.src_path):
            current_time = time.time()
            # Check if we've processed this file recently (debouncing)
            if event.src_path in self.last_modified_times:
                if current_time - self.last_modified_times[event.src_path] < self.debounce_time:
                    return
            
            self.last_modified_times[event.src_path] = current_time
            print(f"File modified: {event.src_path}")
            self.indexer.index_file(event.src_path)
    
    def on_created(self, event: DirCreatedEvent | FileCreatedEvent):
        if not event.is_directory and os.path.isfile(event.src_path):
            # Wait briefly to ensure file is completely written
            time.sleep(1)
            print(f"File created: {event.src_path}")
            self.indexer.index_file(event.src_path)
    
    def on_moved(self, event: DirMovedEvent | FileMovedEvent):
        if not event.is_directory:
            # Handle file rename/move
            print(f"File moved: {event.src_path} -> {event.dest_path}")
            # Remove old entry
            doc_id = self.indexer.create_document_id(event.src_path)
            self.indexer.collection.delete(ids=[doc_id])
            # Add new entry
            self.indexer.index_file(event.dest_path)
    
    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent):
        if not event.is_directory:
            print(f"File deleted: {event.src_path}")
            doc_id = self.indexer.create_document_id(event.src_path)
            self.indexer.collection.delete(ids=[doc_id])