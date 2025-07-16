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

# New imports for file type support
import chardet
from PyPDF2 import PdfReader
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
from bs4 import BeautifulSoup
import markdown

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

    def __detect_encoding(self, file_path: str) -> str:
        """Detect file encoding using chardet"""
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            return result['encoding'] or 'utf-8'

    def __extract_text_content(self, file_path: str) -> str:
        """Extract content from text files with proper encoding detection"""
        encoding = self.__detect_encoding(file_path)
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, TypeError):
            # Fallback to utf-8 with error handling
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except Exception:
                return None

    def __extract_pdf_content(self, file_path: str) -> str:
        """Extract text content from PDF files"""
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting PDF content: {e}")
            return None

    def __extract_docx_content(self, file_path: str) -> str:
        """Extract text content from DOCX files"""
        try:
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting DOCX content: {e}")
            return None

    def __extract_excel_content(self, file_path: str) -> str:
        """Extract text content from Excel files"""
        try:
            workbook = load_workbook(file_path, data_only=True)
            text = ""
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                text += f"Sheet: {sheet_name}\n"
                for row in sheet.iter_rows(values_only=True):
                    row_text = "\t".join([str(cell) if cell is not None else "" for cell in row])
                    if row_text.strip():
                        text += row_text + "\n"
                text += "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting Excel content: {e}")
            return None

    def __extract_pptx_content(self, file_path: str) -> str:
        """Extract text content from PowerPoint files"""
        try:
            prs = Presentation(file_path)
            text = ""
            for slide_num, slide in enumerate(prs.slides, 1):
                text += f"Slide {slide_num}:\n"
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
                text += "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting PPTX content: {e}")
            return None

    def __extract_html_content(self, file_path: str) -> str:
        """Extract text content from HTML files"""
        try:
            encoding = self.__detect_encoding(file_path)
            with open(file_path, 'r', encoding=encoding) as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)
            return text
        except Exception as e:
            print(f"Error extracting HTML content: {e}")
            return None

    def __extract_markdown_content(self, file_path: str) -> str:
        """Extract text content from Markdown files"""
        try:
            encoding = self.__detect_encoding(file_path)
            with open(file_path, 'r', encoding=encoding) as f:
                md_content = f.read()
            
            # Convert markdown to HTML then extract text
            html = markdown.markdown(md_content)
            soup = BeautifulSoup(html, 'html.parser')
            return soup.get_text()
        except Exception as e:
            print(f"Error extracting Markdown content: {e}")
            return None

    def __extract_content(self, file_path: str, mime_type: str) -> str:
        """Extract content from various file types"""
        file_extension = Path(file_path).suffix.lower()
        
        # PDF files
        if mime_type == "application/pdf" or file_extension == ".pdf":
            return self.__extract_pdf_content(file_path)
        
        # Microsoft Office files
        elif mime_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"] or file_extension == ".docx":
            return self.__extract_docx_content(file_path)
        
        elif mime_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"] or file_extension in [".xlsx", ".xlsm"]:
            return self.__extract_excel_content(file_path)
        
        elif mime_type in ["application/vnd.openxmlformats-officedocument.presentationml.presentation"] or file_extension == ".pptx":
            return self.__extract_pptx_content(file_path)
        
        # HTML and XML files
        elif mime_type in ["text/html", "application/xhtml+xml"] or file_extension in [".html", ".htm", ".xhtml"]:
            return self.__extract_html_content(file_path)
        
        # Markdown files
        elif mime_type == "text/markdown" or file_extension in [".md", ".markdown"]:
            return self.__extract_markdown_content(file_path)
        
        # Programming language files and other text files
        elif (mime_type and mime_type.startswith("text/")) or file_extension in [
            ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h", 
            ".cs", ".php", ".rb", ".go", ".rs", ".swift", ".kt", ".scala",
            ".css", ".scss", ".sass", ".less", ".json", ".xml", ".yaml", ".yml",
            ".ini", ".cfg", ".conf", ".log", ".sql", ".sh", ".bash", ".zsh",
            ".txt", ".csv", ".tsv"
        ]:
            return self.__extract_text_content(file_path)
        
        else:
            print(f"Unsupported file type: {mime_type} for {file_path}")
            return None

    def index_file(self, file_path: str, should_commit: bool = True) -> bool:
        if os.path.isdir(file_path) or not os.path.exists(file_path):
            return False
        
        name = os.path.basename(file_path)
        
        # skip hidden files
        if name.startswith(".") or name.startswith("__"):
            print(f"\nSkipping hidden file: {name}")
            return False
            
        # Skip large files until TODO: chunking (different limits for different file types)
        file_size = os.path.getsize(file_path)
        file_extension = Path(file_path).suffix.lower()
        
        # Different size limits for different file types
        size_limits = {
            # Text files - smaller limit
            'text': 5_000_000,  # 5MB
            # Office documents - larger limit as they often contain more content
            'office': 20_000_000,  # 20MB
            # PDFs - larger limit
            'pdf': 50_000_000,  # 50MB
            # Default
            'default': 10_000_000  # 10MB
        }
        
        if file_extension == ".pdf":
            size_limit = size_limits['pdf']
        elif file_extension in [".docx", ".xlsx", ".pptx"]:
            size_limit = size_limits['office']
        elif file_extension in [".txt", ".md", ".py", ".js", ".html", ".css"]:
            size_limit = size_limits['text']
        else:
            size_limit = size_limits['default']
            
        if file_size > size_limit:
            print(f"\nSkipping large file: {name} ({file_size:,} bytes > {size_limit:,} limit)")
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