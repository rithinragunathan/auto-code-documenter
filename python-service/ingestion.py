"""
ingest.py
---------
Entry point. Call ingest_file() or ingest_repo() — that's it.

Internally it calls:
    graph.py         → parse source → nodes + edges
    chunker.py       → nodes → embeddable text chunks
    chromadb_store.py → embed + store chunks

How to use:
    from ingest import ingest_file, ingest_repo, search

    # ingest one file
    result = ingest_file("src/UserService.java", language="java")
    print(result)
    # {'status': 'ok', 'nodes': 12, 'chunks': 9, 'stored': 9}

    # ingest a whole directory
    result = ingest_repo("./my-project")
    print(result)

    # search
    hits = search("method that saves user to database", top_k=5)
    for h in hits:
        print(h["score"], h["qualified_name"])
"""

import os
from pathlib import Path

from graph          import build_graph
from chunker        import build_chunks
import chromadb_client as db


# file extensions → language
EXT_MAP = {
    ".java": "java",
    ".py":   "python",
}


# ══════════════════════════════════════════════════════════════════════════════
# INGEST ONE FILE
# ══════════════════════════════════════════════════════════════════════════════

def ingest_file(file_path: str, language: str = None, replace: bool = True) -> dict:
    """
    Ingest a single source file.

    Parameters
    ----------
    file_path : path to the .java or .py file
    language  : "java" or "python" — auto-detected from extension if not given
    replace   : if True, delete existing chunks for this file first

    Returns
    -------
    { "status": "ok", "file": ..., "nodes": N, "chunks": N, "stored": N }
    or
    { "status": "error", "error": "..." }
    """
    path = Path(file_path)

    if not path.exists():
        return {"status": "error", "error": f"File not found: {file_path}"}

    # auto detect language
    if language is None:
        language = EXT_MAP.get(path.suffix.lower())
    if language is None:
        return {"status": "error", "error": f"Cannot detect language from '{path.suffix}'. Pass language='java' or language='python'."}

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"status": "error", "error": f"Could not read file: {e}"}

    print(f"[DEBUG] Ingesting {file_path}...", flush=True)

    # remove old chunks for this file so re-ingest is clean
    if replace:
        db.delete_file(str(path))

    # pipeline: source → graph → chunks → store
    print(f"[DEBUG] Building graph...", flush=True)
    graph  = build_graph(source, file_path=str(path), language=language)
    print(f"[DEBUG] Graph has {len(graph['nodes'])} nodes", flush=True)
    
    print(f"[DEBUG] Building chunks...", flush=True)
    chunks = build_chunks(graph)
    print(f"[DEBUG] Created {len(chunks)} chunks", flush=True)
    
    print(f"[DEBUG] Storing chunks...", flush=True)
    stored = db.store(chunks)
    print(f"[DEBUG] Stored {stored} chunks", flush=True)

    return {
        "status":   "ok",
        "file":     str(path),
        "language": language,
        "nodes":    len(graph["nodes"]),
        "edges":    len(graph["edges"]),
        "chunks":   len(chunks),
        "stored":   stored,
    }


# ══════════════════════════════════════════════════════════════════════════════
# INGEST A WHOLE REPOSITORY
# ══════════════════════════════════════════════════════════════════════════════

def ingest_repo(root_dir: str, replace: bool = True) -> dict:
    """
    Recursively ingest all .java and .py files under root_dir.

    Parameters
    ----------
    root_dir : path to the root directory
    replace  : if True, delete existing chunks for each file before re-ingesting

    Returns
    -------
    Summary dict with totals and any per-file errors.
    """
    root = Path(root_dir)
    if not root.is_dir():
        return {"status": "error", "error": f"Not a directory: {root_dir}"}

    # collect supported files, skip common non-source dirs
    skip_dirs = {
        ".venv", ".env", ".git", ".gitignore",
        "node_modules", "__pycache__", "build", "target", 
        ".idea", "dist", ".cache", ".pytest_cache",
        "*.egg-info", ".tox", ".mypy_cache",
        "chroma_store",  # Skip our own database
    }
    files = []
    for ext in EXT_MAP:
        for p in root.rglob(f"*{ext}"):
            # Skip if any part of the path is in skip_dirs
            if not any(part in skip_dirs for part in p.parts):
                # Also skip if it's under .venv or other sensitive directories
                path_str = str(p).replace("\\", "/")
                if not any(skip in path_str for skip in [".venv/", "/.venv", "\\.venv", "/__pycache__", "\\.pytest"]):
                    files.append(p)
    files.sort()

    if not files:
        return {"status": "error", "error": "No supported source files found."}

    total_nodes  = 0
    total_edges  = 0
    total_chunks = 0
    total_stored = 0
    errors       = []

    for file_path in files:
        result = ingest_file(str(file_path), replace=replace)
        if result["status"] == "ok":
            total_nodes  += result["nodes"]
            total_edges  += result["edges"]
            total_chunks += result["chunks"]
            total_stored += result["stored"]
        else:
            errors.append({"file": str(file_path), "error": result["error"]})

    return {
        "status":       "ok",
        "root":         root_dir,
        "files_parsed": len(files) - len(errors),
        "files_failed": len(errors),
        "nodes":        total_nodes,
        "edges":        total_edges,
        "chunks":       total_chunks,
        "stored":       total_stored,
        "errors":       errors,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH
# ══════════════════════════════════════════════════════════════════════════════

def search(
    query:     str,
    top_k:     int  = 10,
    language:  str  = None,
    kind:      str  = None,
    file_path: str  = None,
) -> list[dict]:
    """
    Semantic search over all ingested code.

    Parameters
    ----------
    query     : natural language, e.g. "method that validates JWT token"
    top_k     : how many results to return
    language  : "java" or "python" to restrict results
    kind      : "method", "class", "function", "field" to restrict results
    file_path : restrict to one file

    Returns
    -------
    List of result dicts sorted by score (1.0 = perfect match).
    """
    return db.query(text=query, top_k=top_k, language=language, kind=kind, file_path=file_path)


# ══════════════════════════════════════════════════════════════════════════════
# RUN FROM COMMAND LINE
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# CLASS WRAPPER (for compatibility with main.py)
# ══════════════════════════════════════════════════════════════════════════════

class IngestionPipeline:
    """
    Wrapper class for the ingestion pipeline.
    Used by main.py to process a directory and return chunks.
    """
    
    def __init__(self):
        """Initialize the ingestion pipeline."""
        pass
    
    def process(self, folder_path: str) -> list[dict]:
        """
        Process a folder and return a list of chunks.
        
        Parameters
        ----------
        folder_path : path to the directory to process
        
        Returns
        -------
        list of chunk dicts from all ingested files
        """
        result = ingest_repo(folder_path, replace=True)
        
        if result["status"] != "ok":
            print(f"Error during ingestion: {result.get('error', 'Unknown error')}")
            return []
        
        # Query all chunks to return them
        all_chunks = db.get_all_chunks()
        return all_chunks


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python ingestion.py file  <path>         ingest one file")
        print("  python ingestion.py repo  <dir>          ingest a directory")
        print("  python ingestion.py query <text>         search")
        print("  python ingestion.py stats                show total chunks")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "file" and len(sys.argv) >= 3:
        result = ingest_file(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "repo" and len(sys.argv) >= 3:
        result = ingest_repo(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "query" and len(sys.argv) >= 3:
        query_text = " ".join(sys.argv[2:])
        results    = search(query_text, top_k=10)
        for r in results:
            print(f"{r['score']:.4f}  {r['kind']:<12}  {r['qualified_name']}")

    elif cmd == "stats":
        print(f"Total chunks in store: {db.total_chunks()}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)