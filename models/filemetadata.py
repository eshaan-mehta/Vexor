from dataclasses import dataclass
from datetime import datetime

@dataclass
class FileMetadata:
    file_id: str
    name: str
    extension: str
    path: str
    parent_dir: str
    size: int
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime
    mime_type: str
