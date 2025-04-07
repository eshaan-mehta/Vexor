import os
from db.indexer import Indexer
from db.searcher import Searcher
from filesystem.filechangehandler import FileChangeHandler
from watchdog.observers import Observer


def main():
    root_dir = os.path.abspath("./test")

    indexer = Indexer() # file indexer
    searcher = Searcher() # search engine

    print(f"Started indexing directory: {root_dir}")
    count = indexer.index_directory(root_dir)
    print(f"Done indexing directory: {root_dir}. Indexed {count} files.")

    # Setup file watcher
    print("Starting file watcher...")
    fileWatcher = FileChangeHandler(indexer)
    observer = Observer()
    observer.schedule(fileWatcher, path=root_dir, recursive=True)
    observer.start() # start observer thread to watch for file changes
    
    try:
        while True:
            query = input("\nEnter a search query (or 'quit' to exit): ")
            if query == "quit":
                break

            results = searcher.search(query)

            if not results:
                print("No files found.")
            else:
                for result in results:
                    print(f"File: {result['metadata']['name']}")
                    print(f"Path: {result['metadata']['path']}")
                    print(
                        f"Score: {result['total_score']:.4f} "
                        f"(Metadata: {result['metadata_score']:.4f}, Content: {result['content_score']:.4f}) "
                        f"(Raw Metadata: {result['raw_metadata_distance']:.4f}, Raw Content: {result['raw_content_distance']:.4f})"
                    )
                    # print(f"Preview: {search_engine.get_file_preview(result['file_id'])[:100]}...")
                    print("-" * 50)
    
    except KeyboardInterrupt:
        print("Exiting...")
        pass
    finally:
        print("Stopping file watcher...")
        observer.stop() # stop file watcher thread
        observer.join()
            



if __name__ == "__main__":
    main()