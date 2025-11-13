print("Loading...")

import sys
import utils.config as config
from utils.functions import log, cleanup_all, select_mode


def main():
    if len(sys.argv) < 2:
        print("Error: No input provided\n")
        print("Usage:")
        print("  python app.py ./data.zip")
        print("  python app.py ./data.zip ./html/")
        print("  python app.py https://github.com/ichiro-its/repository")
        print("  python app.py ./data.zip --keep --verbose")
        sys.exit(1)

    # Parse arguments
    input_path = sys.argv[1]
    target_folder = None

    for arg in sys.argv[2:]:
        if arg in ("--keep", "--keep-index"):
            config.KEEP_INDEX = True
        elif arg == "--verbose":
            config.VERBOSE = True
        elif not target_folder:
            target_folder = arg

    # Add context
    from utils.extract import add_context

    context, is_codebase = add_context(input_path, target_folder)
    if not context:
        cleanup_all()
        sys.exit(1)

    if is_codebase:
        from utils.query import query_code

        query_code()
    else:
        # Load RAG system
        log("\nLoading RAG system...")
        from utils.htmlcontext import load_rag_system
        from utils.query import query_mode

        store, index, emb = load_rag_system()
        if store is None:
            print("Error: Failed to load RAG system")
            cleanup_all()
            sys.exit(1)

        # Mode selection
        select_mode()

        # Enter query mode
        query_mode(store, index, emb)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup_all()
