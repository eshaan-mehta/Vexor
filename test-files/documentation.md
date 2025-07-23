# Vexor Search Engine Documentation

Welcome to the **Vexor** documentation! This is a comprehensive guide to understanding and using our advanced search capabilities.

## Overview

Vexor is a powerful semantic search engine that can index and search through various file types including:

- Text documents
- Programming source code
- Web pages and markup
- Office documents
- And much more!

## Key Features

### 🔍 Semantic Search
Our search engine understands the *meaning* behind your queries, not just keyword matching.

### 📁 Multi-Format Support
Index files in dozens of formats:

```python
supported_formats = [
    "pdf", "docx", "xlsx", "pptx",
    "html", "md", "txt", "py", "js",
    "json", "yaml", "css", "sql"
]
```

### ⚡ High Performance
- Lightning-fast indexing
- Real-time search results
- Optimized for large datasets

## Getting Started

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/example/vexor.git
   cd vexor
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the indexer:
   ```python
   from db.indexer import Indexer
   indexer = Indexer()
   indexer.index_directory("./documents")
   ```

### Basic Usage

Here's a simple example of how to use Vexor:

```python
from db.searcher import Searcher

# Initialize searcher
searcher = Searcher()

# Perform semantic search
results = searcher.search("machine learning algorithms")

# Display results
for result in results:
    print(f"File: {result.filename}")
    print(f"Relevance: {result.score}")
    print(f"Content: {result.snippet}")
    print("-" * 50)
```

## Advanced Features

### Query Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `+` | Must include | `+python machine learning` |
| `-` | Must exclude | `algorithms -sorting` |
| `"..."` | Exact phrase | `"neural networks"` |
| `*` | Wildcard | `web*` (matches web, website, etc.) |

### File Type Filtering

You can limit searches to specific file types:

```python
# Search only in Python files
results = searcher.search("class definition", file_types=["py"])

# Search in documentation files
results = searcher.search("API reference", file_types=["md", "html"])
```

## Configuration

Create a `config.yaml` file to customize behavior:

```yaml
indexer:
  max_file_size: 10MB
  batch_size: 100
  
searcher:
  max_results: 50
  similarity_threshold: 0.7
  
database:
  path: "./chroma_db"
  collection_name: "documents"
```

## Troubleshooting

### Common Issues

**Q: Why aren't my files being indexed?**
A: Check if:
- File size is under the limit
- File format is supported
- File permissions allow reading

**Q: Search results are not relevant**
A: Try:
- Using more specific keywords
- Adding context to your query
- Checking for typos

**Q: Indexing is slow**
A: Consider:
- Reducing batch size
- Excluding large binary files
- Using SSD storage

## API Reference

### Indexer Class

```python
class Indexer:
    def __init__(self, db_path: str = "./chroma"):
        """Initialize the indexer with database path"""
        
    def index_file(self, file_path: str) -> bool:
        """Index a single file"""
        
    def index_directory(self, directory: str) -> int:
        """Index all files in a directory"""
```

### Searcher Class

```python
class Searcher:
    def __init__(self, db_path: str = "./chroma"):
        """Initialize the searcher"""
        
    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Perform semantic search"""
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*For more information, visit our [website](https://vexor.example.com) or contact us at support@vexor.example.com* 