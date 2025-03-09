./import os
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Tuple
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


class Indexer:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')  

    def __init__(self, db_path: str = "./chroma_db"):
        self.client = chromadb.Client(Settings(
            persist_directory=db_path,
            anonymized_telemetry=False
        ))

        self.collection = self.client.get_or_create_collection(
            name="files",
            embedding_function=None # custom embedding
        )
        

    def get_file_hash(self, file_path: str):
        pass

    def index_file(file_path: str, should_commit: bool = True):
        # check hash to see if different
        # index based on file type
        # update in db
        pass

    def index_files(root_dir: str):
        # split files into chunks
        # loop through dirs checking all subdirs and indexing each file
        # batch update db to save time (save last batch index incase of failure)
        pass

    

