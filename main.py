import os
from indexer import Indexer
from fileobserver import FileChangeHandler
from watchdog.observers import Observer


def main():
    root_dir = os.path.abspath("./test")

    indexer = Indexer()

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

            results = indexer.search(query)

            if not results:
                print("No files found.")
            else:
                print(f"Found {len(results)} files:")
                for i, result in enumerate(results):
                    print(f"{i}. {result}")
    
    except KeyboardInterrupt:
        print("Exiting...")
        pass
    finally:
        print("Stopping file watcher...")
        observer.stop()
        observer.join()
            



if __name__ == "__main__":
    main()