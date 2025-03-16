import os
import multiprocessing
import time
import hashlib
from db.indexer import Indexer

class FileProcessor:
    def __init__(self, indexer: Indexer):
        self.indexer = indexer
        self.chunk_size = 10_000_000 # 10MB
        self.num_chunks = 4
        self.pool = multiprocessing.Pool(self.num_chunks)
        self.file_queue = multiprocessing.Queue()
        self.workers = []
        self.files_in_queue = set()

    def get_file_hash(self, file_path: str) -> str:
        return hashlib.sha256(file_path.encode()).hexdigest()
    
    def enqueue_file(self, file_path: str):
        if not file_path in self.files_in_queue:
            self.files_in_queue.add(file_path)
            self.file_queue.put(file_path)

    def work(self):
        while True:
            file_path = self.file_queue.get() # blocking
            
            if file_path is None: # shutdown signal
                break
            
            self.indexer.index_file(file_path, should_commit=False)
            self.files_in_queue.remove(file_path)
