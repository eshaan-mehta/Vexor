import os
import chromadb
import numpy as np
import logging

from chromadb.config import Settings
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from utils.math_utils import normalize_cosine_distance

logger = logging.getLogger(__name__)

class Searcher:
    metadata_weight = 0.62
    content_weight = 0.38

    def __init__(self,
                client=None,
                db_path: str = "./chroma",
                metadata_collection_name: str = "file_metadata",
                content_collection_name: str = "file_content"
                ):
        
        # Use provided client or create a new one
        if client:
            self.client = client
        else:
            self.client = chromadb.PersistentClient(
                path=db_path,
                settings=Settings(anonymized_telemetry=False)
            )

        # Use get_collection first, but fall back to get_or_create_collection if needed
        try:
            self.metadata_collection = self.client.get_collection(metadata_collection_name)
            self.content_collection = self.client.get_collection(content_collection_name)
        except Exception:
            # Fallback: create collections if they don't exist (shouldn't happen with proper initialization)
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            embedding_function = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            
            self.metadata_collection = self.client.get_or_create_collection(
                name=metadata_collection_name,
                embedding_function=embedding_function
            )
            self.content_collection = self.client.get_or_create_collection(
                name=content_collection_name,
                embedding_function=embedding_function
            )
    
    def __del__(self):
        """Destructor to ensure cleanup on garbage collection."""
        self.cleanup()

    def cleanup(self):
        """Clean up resources to prevent semaphore leaks."""
        try:
            # Clear collection references
            self.metadata_collection = None
            self.content_collection = None
            
            # Close ChromaDB client if it has a close method
            # Note: If client was shared from initialization, this will close it
            if hasattr(self.client, 'close'):
                self.client.close()
            
            # Clear client reference
            self.client = None
                
            logger.debug("Searcher resources cleaned up")
        except Exception as e:
            logger.error(f"Error during Searcher cleanup: {e}")


    def search(self, 
               query: str, 
               limit: int = 10, 
               file_types: Optional[List[str]] = None,
               date_range: Optional[Tuple[datetime, datetime]] = None,
               directories: Optional[List[str]] = None,
               min_size: Optional[int] = None,
               max_size: Optional[int] = None) -> List[Dict[str, Any]]:
        
        # Prepare filter conditions
        where_conditions = {}
        
        # if file_types:
        #     where_conditions["extension"] = {"$in": file_types}
            
        # if directories:
        #     where_conditions["parent_dir"] = {"$in": directories}
            
        # if min_size is not None:
        #     where_conditions["size_bytes"] = {"$gte": min_size}
            
        # if max_size is not None:
        #     if "size_bytes" in where_conditions:
        #         where_conditions["size_bytes"]["$lte"] = max_size
        #     else:
        #         where_conditions["size_bytes"] = {"$lte": max_size}
                
        # if date_range:
        #     start_date, end_date = date_range
        #     where_conditions["modified_time"] = {
        #         "$gte": start_date.isoformat(),
        #         "$lte": end_date.isoformat()
        #     }

        # Query metadata collection
        metadata_results = self.metadata_collection.query(
            query_texts=[query],
            n_results=limit * 2,  # Get more results to allow for filtering
            where=where_conditions if where_conditions else None
        )
        
        # Query content collection
        content_results = self.content_collection.query(
            query_texts=[query],
            n_results=limit * 2,  # Get more results to allow for filtering
            where=where_conditions if where_conditions else None
        )
        
        # Merge and score results
        return self.__merge_results(metadata_results, content_results, limit)

    def __merge_results(self, metadata_results, content_results, limit):
        weighted_results = {}

        # Process metadata results
        if metadata_results['ids']:
            for i, file_id in enumerate(metadata_results['ids'][0]):
                # Extract actual file_id from the ID format "meta-{file_id}"
                file_hash_id = file_id[5:] if file_id.startswith('meta-') else file_id

                metadata = metadata_results['metadatas'][0][i]
                distances = metadata_results.get('distances', None)
                distance = distances[0][i] if distances else 0

                metadata_score = normalize_cosine_distance(distance)

                weighted_results[file_hash_id] = {
                    "file_id": file_hash_id,
                    "metadata": metadata,
                    "raw_metadata_distance": distance,
                    "metadata_score": metadata_score * self.metadata_weight,
                    "raw_content_distance": 1.0,  # orthogonal (no content match)
                    "content_score": 0.0,
                    "total_score": metadata_score * self.metadata_weight
                }
        
        # Process content results
        if content_results['ids']:
            for i, file_id in enumerate(content_results['ids'][0]):
                # Extract actual file_id from the ID format "content-{file_id}"
                file_hash_id = file_id[8:] if file_id.startswith("content-") else file_id
                
                metadata = content_results['metadatas'][0][i]
                distances = content_results.get('distances', None)
                distance = distances[0][i] if distances else 0
                
                content_score = normalize_cosine_distance(distance)
                
                # Update existing entry or create new one
                if file_hash_id in weighted_results:
                    # Update existing entry with content score
                    result = weighted_results[file_hash_id]
                    result["content_score"] = content_score * self.content_weight
                    result["raw_content_distance"] = distance
                    result["total_score"] = result["metadata_score"] + result["content_score"]
                else:
                    # Create new entry (content match only)
                    weighted_results[file_hash_id] = {
                        "file_id": file_hash_id,
                        "metadata": metadata,
                        "raw_metadata_distance": 1.0,  # orthogonal (no metadata match)
                        "metadata_score": 0.0,
                        "raw_content_distance": distance,
                        "content_score": content_score * self.content_weight,
                        "total_score": content_score * self.content_weight
                    }
        
        # Sort by total score and return top results
        sorted_results = sorted(
            weighted_results.values(),
            key=lambda x: x["total_score"],
            reverse=True
        )[:limit]

        return sorted_results
        