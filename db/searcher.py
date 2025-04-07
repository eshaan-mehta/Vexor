import os
import chromadb
import numpy as np

from chromadb.config import Settings
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from utils.math_utils import normalize_cosine_distance

class Searcher:
    metadata_weight = 0.62
    content_weight = 0.38

    def __init__(self,
                db_path: str = "./chroma",
                metadata_collection_name: str = "file_metadata",
                content_collection_name: str = "file_content"
                ):
        
        self.client = chromadb.Client(Settings(
            persist_directory=db_path,
            anonymized_telemetry=False
        ))

        self.metadata_collection = self.client.get_collection(metadata_collection_name)
        self.content_collection = self.client.get_collection(content_collection_name)
    
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

        if metadata_results['ids']:
            for i, file_id in enumerate(metadata_results['ids'][0]):
                # extract actual file_id from the ID format "meta-{file_id}"
                file_hash_id = file_id[5:] if file_id.startswith('meta-') else file_id

                metadata = metadata_results['metadatas'][0][i] # type FileMetadata
                distances = metadata_results.get('distances', None)
                distance = distances[0][i] if distances else 0

                metadata_score = normalize_cosine_distance(distance)

                #TODO: create model for this
                weighted_results[file_hash_id] = {
                    "id": file_hash_id,
                    "metadata": metadata, # contains all file metadata
                    "raw_metadata_distance": distance,
                    "metadata_score": metadata_score*self.metadata_weight,
                    "raw_content_distance": 1, # orthogonal
                    "content_score": 0,
                    "total_score": metadata_score # currently this is unweighted in the event that there is no corresponding match in the content collection
                }
        
        if content_results['ids']:
            for i, file_id in enumerate(content_results['ids'][0]):
                # Extract actual file_id from the ID format "content-{file_id}"
                file_hash_id = file_id[8:] if file_id.startswith("content-") else file_id
                
                # Get metadata and distance
                metadata = content_results['metadatas'][0][i]
                distances = content_results.get('distances', None)
                distance = distances[0][i] if distances else 0
                
                content_score = normalize_cosine_distance(distance)
                
                # update existing entry or create new one
                if (result := weighted_results.get(file_hash_id, None)):
                    result["content_score"] = content_score * self.content_weight
                    result["total_score"] = result["metadata_score"] + result["content_score"] # these are weighted scores
                    result["raw_content_distance"] = distance
                else:
                    weighted_results[file_hash_id] = {
                        "file_id": file_hash_id,
                        "metadata": metadata,
                        "raw_metadata_distance": 1, # orthogonal
                        "metadata_score": 0,
                        "raw_content_distance": distance,
                        "content_score": content_score * self.content_weight,
                        "total_score": content_score
                    }
        
        # Sort by total score and return top results
        sorted_results = sorted(
            weighted_results.values(),
            key=lambda x: x["total_score"],
            reverse=True
        )[:limit]

        return sorted_results
        