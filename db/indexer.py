import os
import hashlib
import mimetypes
import chromadb

from datetime import datetime
from dataclasses import asdict
from typing import Dict, Any, List, Tuple
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from sentence_transformers import SentenceTransformer
from pathlib import Path

from models.filemetadata import FileMetadata


class Indexer:
    embedding_function = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")  

    def __init__(self, 
            db_path: str = "./chroma", 
            metadata_collection_name: str = "file_metadata",
            content_collection_name: str = "file_content"
        ):
        os.makedirs(db_path, exist_ok=True)

        self.client = chromadb.Client(Settings(
            persist_directory=db_path,
            anonymized_telemetry=False
        ))

        self.content_collection = self.client.get_or_create_collection(
            name=content_collection_name,
            embedding_function=self.embedding_function,
            metadata = {
                "hnsw:space": "cosine",  # cosine better for text embeddings
                "hnsw:construction_ef": 100,  # size of candidates during indexing (default = 100)
                "hnsw:search_ef": 100,  # size of candidates during searching (default = 100)
                "hnsw:M": 16  # max neighbours in node graph (default = 16)
            }
        )

        self.metadata_collection = self.client.get_or_create_collection(
            name=metadata_collection_name,
            embedding_function=self.embedding_function,
            metadata = {
                "hnsw:space": "cosine",  # cosine better for text embeddings
                "hnsw:construction_ef": 100,  # size of candidates during indexing (default = 100)
                "hnsw:search_ef": 100,  # size of candidates during searching (default = 100)
                "hnsw:M": 16  # max neighbours in node graph (default = 16)
            }
        )
        
    def get_file_hash(self, file_path: str) -> str:
        # TODO: Update to use file contents
        return  hashlib.sha256(file_path.encode()).hexdigest()

    def __extract_metadata(self, file_path: str) -> FileMetadata:
        stat = os.stat(file_path)
        path = Path(file_path)
        
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = "application/octet-stream"  # Default binary type


        return FileMetadata(
            file_id=self.get_file_hash(file_path),
            name=path.name,
            extension=path.suffix.lower(),
            path=str(path),
            parent_dir=str(path.parent),
            size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            accessed_at=datetime.fromtimestamp(stat.st_atime).isoformat(),
            mime_type=mime_type,
        )

    def __extract_content(self, file_path: str, mime_type: str) -> str:
        if not mime_type.startswith("text/"):
            raise Exception("File type not text")
        
        try:
            with open(file_path, 'r', encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            return None

    def index_file(self, file_path: str, should_commit: bool = True) -> bool:
        if os.path.isdir(file_path) or not os.path.exists(file_path):
            return False
        
        name = os.path.basename(file_path)
        
        # skip hidden files
        if name.startswith(".") or name.startswith("__"):
            print(f"\nSkipping hidden file: {name}")
            return False
            
        # skip large files until TODO: chunking
        if os.path.getsize(file_path) > 10_000_000: # 10MB
            print(f"\nSkipping large file: {name}")
            return False
        
        try:
            metadata = self.__extract_metadata(file_path)

            # TODO: check if file already exists in db and hasnt changed since last time
            if result := self.metadata_collection.get(where={"file_id": metadata.file_id}):
                # check if file has changed since last index
                print(result)
                if result["metadatas"] and len(result["metadatas"]) > 0:
                    existing_metadata = result["metadatas"][0]
                    if existing_metadata["modified_at"] == metadata.modified_at:
                        print(f"No change in: {name}")
                        return False


            self.metadata_collection.add(
                documents=[str(metadata)],
                metadatas=[asdict(metadata)],
                ids=[f"meta-{metadata.file_id}"]
            )

            content = self.__extract_content(file_path, metadata.mime_type)
            if content:
                self.content_collection.add(
                    documents=[content],
                    metadatas=[asdict(metadata)],
                    ids=[f"content-{metadata.file_id}"]
                )

            # split file into overlapping chunks, will have a seperate entry for each
            # generate hash for each chunk
            # check if hash has changed since last index
            # multi thread this part to index chunks in parallel
            # update db with new chunks
            print(f"Done Indexing file: {name}")
            return True
        except Exception as e:
            print(f"Could not index file: {name}")
            print(f"Error: {e}")
            return False


    def index_directory(self, root_dir: str) -> int:
        if not os.path.exists(root_dir):
            raise FileNotFoundError(f"Directory not found: {root_dir}")

        # loop through dirs checking all subdirs
        count = 0
        for path, dirs, files in os.walk(root_dir):
            for file in files:
                file_path = os.path.join(path, file)
                try:
                    success = self.index_file(file_path, should_commit=True)
                    if success:
                        count += 1
                    
                except Exception as e:
                    print(f"Exception indexing {file_path}: {e}")

        return count