"""
chromadb_server.py
------------------
Standalone ChromaDB HTTP server.

This runs as a separate service, allowing multiple clients to connect.
ChromaDB provides a built-in HTTP API that we leverage.

To run:
    python chromadb_server.py

The server will listen on http://localhost:8000
"""

import os
import sys
import shutil
import chromadb

# ── Configuration ──────────────────────────────────────────────────
PERSIST_DIR = "./chroma_store"
CHROMA_HOST = "0.0.0.0"  # Accept connections from any host
CHROMA_PORT = 8000
COLLECTION_NAME = "codebase_chunks"


def ensure_clean_db():
    """Check if database is corrupted and reset if needed."""
    if os.path.exists(PERSIST_DIR):
        try:
            # Try to access the database
            client = chromadb.PersistentClient(path=PERSIST_DIR)
            # Try to list collections - this will trigger HNSW errors if corrupt
            client.list_collections()
            print("[INFO] Database health check passed", flush=True)
            return
        except Exception as e:
            error_msg = str(e).lower()
            if any(x in error_msg for x in ["hnsw", "index", "compaction", "segment"]):
                print(f"[WARNING] Corrupted database detected: {type(e).__name__}", flush=True)
                print(f"[INFO] Deleting corrupted database at {PERSIST_DIR}", flush=True)
                try:
                    shutil.rmtree(PERSIST_DIR)
                    print(f"[SUCCESS] Database deleted, will recreate fresh", flush=True)
                except Exception as del_err:
                    print(f"[ERROR] Failed to delete: {del_err}", flush=True)
                    raise
            else:
                # Some other error - re-raise to see what it is
                raise


def start_server():
    """Initialize and start the ChromaDB HTTP server."""
    print(f"[STARTUP] Initializing ChromaDB server...", flush=True)
    print(f"[STARTUP] Persist directory: {PERSIST_DIR}", flush=True)
    print(f"[STARTUP] Listening on {CHROMA_HOST}:{CHROMA_PORT}", flush=True)

    try:
        # Check DB health
        ensure_clean_db()

        # Initialize persistent client and get HTTPServer
        client = chromadb.HttpServer(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            path=PERSIST_DIR,
        )

        print(f"[SUCCESS] ChromaDB server started successfully", flush=True)
        print(f"[INFO] Server ready at http://{CHROMA_HOST}:{CHROMA_PORT}", flush=True)

        # Server runs until KeyboardInterrupt
        client.start()

    except KeyboardInterrupt:
        print(f"\n[SHUTDOWN] Server shutting down...", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Failed to start server: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    start_server()
