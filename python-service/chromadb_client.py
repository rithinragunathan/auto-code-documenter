"""
chromadb_client.py
------------------
HTTP client wrapper for remote ChromaDB server.

This module provides the same interface as the old embedded chromadb_store.py,
but communicates with a ChromaDB HTTP server instead of using embedded library.

Configuration:
    CHROMA_SERVER_HOST: Host where ChromaDB server is running (default: localhost)
    CHROMA_SERVER_PORT: Port where ChromaDB server is running (default: 8000)

To use:
    from chromadb_client import store, query, delete_file
    
    store(chunks)
    results = query("validate JWT token")
    delete_file("src/UserService.java")
"""

import os
import json

# ── HuggingFace Caching Configuration (MUST be before SentenceTransformer import) ──
_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
os.environ["HF_HOME"] = _cache_dir
os.environ["TRANSFORMERS_CACHE"] = os.path.join(_cache_dir, "transformers")
os.environ["HF_DATASETS_CACHE"] = os.path.join(_cache_dir, "datasets")
os.environ["HF_HUB_CACHE"] = os.path.join(_cache_dir, "hub")
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "300"

import chromadb
from sentence_transformers import SentenceTransformer
import torch

# ── Configuration ──────────────────────────────────────────────────
CHROMA_SERVER_HOST = os.getenv("CHROMA_SERVER_HOST", "localhost")
CHROMA_SERVER_PORT = int(os.getenv("CHROMA_SERVER_PORT", "8000"))
COLLECTION_NAME = "codebase_chunks"

# ── Singletons ──────────────────────────────────────────────────────────────
_model = None
_client = None
_collection = None


def get_server_url():
    """Get the full ChromaDB server URL."""
    return f"http://{CHROMA_SERVER_HOST}:{CHROMA_SERVER_PORT}"


def _get_model():
    """Load and return the embedding model (GPU-optimized)."""
    global _model
    if _model is None:
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        print(f"[GPU INIT] Loading embedding model: {model_name}...", flush=True)
        print(f"[GPU INIT] Cache directory: {os.environ.get('HF_HUB_CACHE')}", flush=True)
        try:
            # GPU-first strategy
            try:
                _model = SentenceTransformer(
                    model_name,
                    device="cuda",
                    trust_remote_code=True,
                    model_kwargs={"torch_dtype": torch.float16}
                )
                print("[GPU INIT] ✓ Model loaded on GPU (float16)", flush=True)
            except (RuntimeError, torch.cuda.OutOfMemoryError) as gpu_err:
                print(f"[GPU INIT] GPU memory error: {type(gpu_err).__name__}", flush=True)
                print("[GPU INIT] Falling back to CPU...", flush=True)
                _model = SentenceTransformer(
                    model_name,
                    device="cpu",
                    trust_remote_code=True
                )
                print("[GPU INIT] ✓ Model loaded on CPU", flush=True)
        except Exception as e:
            print(f"[GPU INIT] Error loading model: {e}", flush=True)
            raise
    return _model


def _get_client():
    """Connect to remote ChromaDB server."""
    global _client
    if _client is None:
        server_url = get_server_url()
        print(f"[CLIENT] Connecting to ChromaDB server at {server_url}...", flush=True)
        try:
            _client = chromadb.HttpClient(
                host=CHROMA_SERVER_HOST,
                port=CHROMA_SERVER_PORT
            )
            # Test connection by getting server info
            _client._client.heartbeat()
            print(f"[CLIENT] ✓ Connected to ChromaDB server", flush=True)
        except Exception as e:
            print(f"[CLIENT] ✗ Failed to connect: {e}", flush=True)
            print(f"[CLIENT] Make sure ChromaDB server is running at {server_url}", flush=True)
            raise
    return _client


def _get_collection():
    """Get or create the collection on the remote server."""
    global _collection
    if _collection is None:
        try:
            client = _get_client()
            _collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            print("[DEBUG] Collection loaded successfully from server", flush=True)
        except Exception as e:
            print(f"[WARNING] Error loading collection: {e}", flush=True)
            raise
    return _collection


# ══════════════════════════════════════════════════════════════════════════════
# STORE
# ══════════════════════════════════════════════════════════════════════════════

def store(chunks: list[dict]) -> int:
    """
    Embed and store a list of chunks into remote ChromaDB server.
    
    Embeddings are computed locally using GPU, then sent to server.

    Parameters
    ----------
    chunks : list of chunk dicts from chunker.build_chunks()

    Returns
    -------
    Number of chunks stored.
    """
    if not chunks:
        return 0

    model = _get_model()
    collection = _get_collection()

    batch_size = 2
    
    # Ensure model is on GPU
    try:
        device = next(model.parameters()).device
        print(f"[GPU OPTIMIZATION] Model device: {device} | Batch size: {batch_size}", flush=True)
    except StopIteration:
        print(f"[GPU OPTIMIZATION] Could not determine device, assuming CPU", flush=True)
    
    total_stored = 0
    batch_count = (len(chunks) + batch_size - 1) // batch_size
    
    for batch_idx in range(0, len(chunks), batch_size):
        batch = chunks[batch_idx:batch_idx + batch_size]
        current_batch = batch_idx // batch_size + 1
        
        print(f"[BATCH {current_batch}/{batch_count}] Processing {len(batch)} chunks...", flush=True)
        
        texts = [c["chunk_text"] for c in batch]
        
        try:
            # Encode locally with GPU
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=False
            )

            ids = [c["chunk_id"] for c in batch]
            documents = texts
            metadatas = [_to_metadata(c) for c in batch]
            embeds = [e.tolist() if hasattr(e, 'tolist') else e for e in embeddings]

            print(f"[BATCH {current_batch}/{batch_count}] Upserting to ChromaDB server...", flush=True)
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeds,
                metadatas=metadatas,
            )
            total_stored += len(batch)
            print(f"[BATCH {current_batch}/{batch_count}] ✓ Stored. Total: {total_stored}/{len(chunks)}", flush=True)
            
            # Clear GPU cache
            torch.cuda.empty_cache()
                
        except RuntimeError as e:
            if "out of memory" in str(e).lower() or "cuda" in str(e).lower():
                print(f"[ERROR-BATCH {current_batch}] GPU OOM: {e}", flush=True)
                print(f"[FALLBACK] Moving model to CPU and retrying...", flush=True)
                
                model.to("cpu")
                batch_size = 8
                
                embeddings = model.encode(
                    texts,
                    batch_size=batch_size,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
                
                ids = [c["chunk_id"] for c in batch]
                documents = texts
                metadatas = [_to_metadata(c) for c in batch]
                embeds = [e.tolist() if hasattr(e, 'tolist') else e for e in embeddings]
                
                collection.upsert(
                    ids=ids,
                    documents=documents,
                    embeddings=embeds,
                    metadatas=metadatas,
                )
                total_stored += len(batch)
                print(f"[BATCH {current_batch}/{batch_count}] ✓ CPU fallback OK. Continuing on CPU.", flush=True)
            else:
                print(f"[ERROR-BATCH {current_batch}] Runtime error: {e}", flush=True)
                raise
        except Exception as e:
            print(f"[ERROR-BATCH {current_batch}] Error: {e}", flush=True)
            raise
    
    print(f"[SUCCESS] Stored all {total_stored} chunks to ChromaDB server", flush=True)
    return total_stored


# ══════════════════════════════════════════════════════════════════════════════
# QUERY
# ══════════════════════════════════════════════════════════════════════════════

def query(
    text: str,
    top_k: int = 10,
    language: str = None,
    kind: str = None,
    file_path: str = None,
) -> list[dict]:
    """
    Semantic search over stored chunks.
    
    Embeddings computed locally, search performed on remote server.

    Parameters
    ----------
    text : natural-language query
    top_k : number of results
    language : filter by language (optional)
    kind : filter by kind (optional)
    file_path : filter by file (optional)

    Returns
    -------
    List of result dicts sorted by score descending.
    """
    model = _get_model()
    collection = _get_collection()

    print(f"[QUERY] Encoding query on GPU...", flush=True)
    query_vec = model.encode(
        text,
        batch_size=1,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=False
    ).tolist()
    
    torch.cuda.empty_cache()

    where = _build_where(language=language, kind=kind, file_path=file_path)

    print(f"[QUERY] Searching ChromaDB server for top {top_k} results...", flush=True)
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        output.append({
            "score": round(1.0 - results["distances"][0][i], 4),
            "chunk_id": results["ids"][0][i],
            "node_id": meta.get("node_id", ""),
            "kind": meta.get("kind", ""),
            "language": meta.get("language", ""),
            "name": meta.get("name", ""),
            "qualified_name": meta.get("qualified_name", ""),
            "signature": meta.get("signature", ""),
            "file_path": meta.get("file_path", ""),
            "line_start": meta.get("line_start", ""),
            "document": results["documents"][0][i],
        })
    
    print(f"[QUERY] ✓ Found {len(output)} results", flush=True)
    return output


# ══════════════════════════════════════════════════════════════════════════════
# GET ALL CHUNKS
# ══════════════════════════════════════════════════════════════════════════════

def get_all_chunks() -> list[dict]:
    """
    Retrieve all chunks from the server collection.

    Returns
    -------
    List of all chunk dicts with metadata.
    """
    collection = _get_collection()

    results = collection.get(
        include=["documents", "metadatas"],
    )

    output = []
    for i in range(len(results["ids"])):
        meta = results["metadatas"][i]
        output.append({
            "chunk_id": results["ids"][i],
            "node_id": meta.get("node_id", ""),
            "kind": meta.get("kind", ""),
            "language": meta.get("language", ""),
            "name": meta.get("name", ""),
            "qualified_name": meta.get("qualified_name", ""),
            "file_path": meta.get("file_path", ""),
            "source": meta.get("source", ""),
            "parent_id": meta.get("parent_id", ""),
            "signature": meta.get("signature", ""),
            "line_start": meta.get("line_start", ""),
            "line_end": meta.get("line_end", ""),
            "chunk_text": results["documents"][i],
        })
    return output


# ══════════════════════════════════════════════════════════════════════════════
# DELETE
# ══════════════════════════════════════════════════════════════════════════════

def delete_file(file_path: str) -> None:
    """Remove all chunks that came from the given file_path."""
    try:
        collection = _get_collection()
        count = collection.count()
        if count > 0:
            collection.delete(where={"file_path": file_path})
            print(f"Deleted previous chunks for {file_path}", flush=True)
    except Exception as e:
        print(f"[INFO] Skipping delete for {file_path}: {type(e).__name__}", flush=True)


def total_chunks() -> int:
    """Return total number of chunks currently stored."""
    return _get_collection().count()


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _to_metadata(chunk: dict) -> dict:
    """
    ChromaDB metadata values must be scalar (str, int, float, bool).
    Convert any non-scalar to a string.
    """
    def safe(v):
        if isinstance(v, (str, int, float, bool)):
            return v
        if v is None:
            return ""
        return json.dumps(v)

    return {
        "node_id": safe(chunk.get("node_id")),
        "kind": safe(chunk.get("kind")),
        "language": safe(chunk.get("language")),
        "name": safe(chunk.get("name")),
        "qualified_name": safe(chunk.get("qualified_name")),
        "file_path": safe(chunk.get("file_path")),
        "parent_id": safe(chunk.get("parent_id")),
        "signature": safe(chunk.get("signature")),
        "line_start": safe(chunk.get("line_start")),
        "line_end": safe(chunk.get("line_end")),
    }


def _build_where(language=None, kind=None, file_path=None):
    """Build ChromaDB where filter clause."""
    clauses = []
    if language:
        clauses.append({"language": language})
    if kind:
        clauses.append({"kind": kind})
    if file_path:
        clauses.append({"file_path": file_path})

    if len(clauses) == 0:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}
