import chromadb
import numpy as np
from datetime import datetime, timedelta
import os
from typing import List, Dict, Any, Optional, Tuple

class Searcher:
    metadata_weight = 0.75
    content_weight = 0.25

    def __init__(self):
        self.client = chromadb.Client()
        self.metadata_collection = self.client.get_collection("file_metadata")
        self.content_collection = self.client.get_collection("file_content")
    
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
        print(metadata_results)
        print(content_results)

    def __merge_results(self, metadata_results, content_results, limit):
        weighted_results = {}
        