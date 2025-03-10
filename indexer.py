import os
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Tuple
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


class Indexer:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')  

    def __init__(self, db_path: str = "./chroma"):
        os.makedirs(db_path, exist_ok=True)

        self.client = chromadb.Client(Settings(
            persist_directory=db_path,
            anonymized_telemetry=False
        ))

        self.content_collection = self.client.get_or_create_collection(
            name="file_contents",
            embedding_function=None # custom embedding
        )

        self.metadata_collection = self.client.get_or_create_collection(
            name="file_metadata",
            embedding_function=None
        )
        

    def get_file_hash(self, file_path: str) -> str:
        # TODO: Update to use file contents
        return  hashlib.sha256(file_path.encode()).hexdigest()

    def index_file(self, file_path: str, should_commit: bool = True):
        # split file into overlapping chunks, will have a seperate entry for each
        # generate hash for each chunk
        # check if hash has changed since last index
        # multi thread this part to index chunks in parallel
        # update db with new chunks
        name = os.path.basename(file_path)
        print(f"Done Indexing file: {name}")

    def index_directory(self, root_dir: str) -> int:
        # loop through dirs checking all subdirs
        # batch update db to save time (save last batch index incase of failure)
        count = 0
        return count


    def search(self, query: str) -> List[Dict[str, Any]]:
        # search db for query
        # return results
        return []

    

