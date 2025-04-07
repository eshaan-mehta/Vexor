from dataclasses import dataclass
from datetime import datetime

@dataclass
class SearchResult:
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

    def __str__(self) -> str:
        """Human-readable string representation of the FileMetadata."""
        return (f"File: {self.name} ({self.extension})\n"
                f"Id: {self.file_id}\n"
                f"Path: {self.path}\n"
                f"Parent Dir: {self.parent_dir}\n"
                f"Size: {self.size} bytes\n"
                f"Created At: {self.created_at}\n"
                f"Modified At: {self.modified_at}\n"
                f"Accessed At: {self.accessed_at}\n"
                f"Type: {self.mime_type}")
    
    def __repr__(self) -> str:
        """Developer-friendly string representation of the FileMetadata."""
        return (f"FileMetadata(file_id='{self.file_id[:8]}...', "
                f"name='{self.name}', "
                f"extension='{self.extension}', "
                f"path={self.path},"
                f"parent_dir={self.parent_dir},"
                f"size={self.size}, "
                f"created_at={self.created_at}, "
                f"modified_at={self.modified_at}, "
                f"accessed_at={self.accessed_at}, "
                f"mime_type='{self.mime_type}')")
