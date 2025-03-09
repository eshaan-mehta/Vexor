import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
from indexer import Indexer

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, search_system: Indexer):
        self.search_system = search_system
        self.last_modified_times = {}
        self.debounce_time = 2  # seconds to wait before processing a change
    
    def on_modified(self, event):
        if not event.is_directory and os.path.isfile(event.src_path):
            current_time = time.time()
            # Check if we've processed this file recently (debouncing)
            if event.src_path in self.last_modified_times:
                if current_time - self.last_modified_times[event.src_path] < self.debounce_time:
                    return
            
            self.last_modified_times[event.src_path] = current_time
            print(f"File modified: {event.src_path}")
            self.search_system.index_file(event.src_path)
    
    def on_created(self, event):
        if not event.is_directory and os.path.isfile(event.src_path):
            # Wait briefly to ensure file is completely written
            time.sleep(1)
            print(f"File created: {event.src_path}")
            self.search_system.index_file(event.src_path)
    
    def on_moved(self, event):
        if not event.is_directory:
            # Handle file rename/move
            print(f"File moved: {event.src_path} -> {event.dest_path}")
            # Remove old entry
            doc_id = self.search_system.create_document_id(event.src_path)
            self.search_system.collection.delete(ids=[doc_id])
            # Add new entry
            self.search_system.index_file(event.dest_path)
    
    def on_deleted(self, event):
        if not event.is_directory:
            print(f"File deleted: {event.src_path}")
            doc_id = self.search_system.create_document_id(event.src_path)
            self.search_system.collection.delete(ids=[doc_id])