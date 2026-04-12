"""
chromadb_store.py
-----------------
All ChromaDB logic lives here. Nothing else in the project touches ChromaDB directly.

Three things this file does:
    1. store(chunks)      — embed and save chunks into ChromaDB
    2. query(text)        — semantic search, returns top-k results
    3. delete_file(path)  — remove all chunks that came from a specific file

How to use:
    from chromadb_store import store, query, delete_file

    store(chunks)                          # save after ingestion
    results = query("validate JWT token")  # search
    delete_file("src/UserService.java")    # re-ingest a file cleanly
"""

import json
import os
import shutil

# ── HuggingFace Caching Configuration (MUST be before SentenceTransformer import) ──
# Force models to be cached locally and reused across runs
_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
os.environ["HF_HOME"] = _cache_dir
os.environ["TRANSFORMERS_CACHE"] = os.path.join(_cache_dir, "transformers")
os.environ["HF_DATASETS_CACHE"] = os.path.join(_cache_dir, "datasets")
os.environ["HF_HUB_CACHE"] = os.path.join(_cache_dir, "hub")
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "300"  # 5 minutes timeout

import chromadb
from sentence_transformers import SentenceTransformer
import torch

# ── Singletons (loaded once, reused) ──────────────────────────────────────
_model      = None
_collection = None

PERSIST_DIR      = "./chroma_store"
COLLECTION_NAME  = "codebase_chunks"


def _ensure_clean_db():
    """Check if database is corrupted and reset if needed."""
    if os.path.exists(PERSIST_DIR):
        try:
            # Try to access the database
            client = chromadb.PersistentClient(path=PERSIST_DIR)
            # Try to list collections - this will trigger HNSW errors if corrupt
            client.list_collections()
            print("[DEBUG] Database health check passed", flush=True)
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


print("[MODULE INIT] Checking database integrity...", flush=True)
try:
    _ensure_clean_db()
except Exception as init_err:
    print(f"[WARNING] Database check failed during init: {init_err}", flush=True)
    # Continue anyway - will handle on first use



def _get_model():
    global _model
    if _model is None:
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        print(f"[GPU INIT] Loading embedding model: {model_name}...", flush=True)
        print(f"[GPU INIT] Cache directory: {os.environ.get('HF_HUB_CACHE')}", flush=True)
        try:
            # GPU-first strategy: try to load on GPU with optimization flags
            try:
                _model = SentenceTransformer(
                    model_name,
                    device="cuda",
                    trust_remote_code=True,
                    model_kwargs={"torch_dtype": torch.float16}  # Use half precision for smaller footprint
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


def _get_collection():
    global _collection
    if _collection is None:
        try:
            client      = chromadb.PersistentClient(path=PERSIST_DIR)
            _collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            print("[DEBUG] Collection loaded successfully", flush=True)
        except Exception as e:
            # If collection is corrupted, try to delete and recreate
            print(f"[WARNING] Error loading collection: {e}", flush=True)
            print("[INFO] Attempting to reset collection...", flush=True)
            try:
                import shutil
                if os.path.exists(PERSIST_DIR):
                    shutil.rmtree(PERSIST_DIR)
                    print(f"[INFO] Deleted corrupted {PERSIST_DIR}", flush=True)
                
                client      = chromadb.PersistentClient(path=PERSIST_DIR)
                _collection = client.get_or_create_collection(
                    name=COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
                print("[INFO] Collection recreated successfully", flush=True)
            except Exception as reset_err:
                print(f"[ERROR] Failed to reset collection: {reset_err}", flush=True)
                raise
    return _collection


# ══════════════════════════════════════════════════════════════════════════════
# STORE
# ══════════════════════════════════════════════════════════════════════════════

def store(chunks: list[dict]) -> int:
    """
    Embed and store a list of chunks into ChromaDB with GPU optimization.
    
    Designed for GPU inference with strict batch size of 2 to maximize
    throughput while minimizing memory footprint.

    Parameters
    ----------
    chunks : list of chunk dicts from chunker.build_chunks()

    Returns
    -------
    Number of chunks stored.
    """
    if not chunks:
        return 0

    model      = _get_model()
    collection = _get_collection()

    # GPU-optimized: hardcoded batch size of 2 for consistent memory profile
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
            # Encode with batch size 2 - optimal for GPU throughput
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=False  # Keep as tensors for better GPU handling
            )

            ids = [c["chunk_id"] for c in batch]
            documents = texts
            metadatas = [_to_metadata(c) for c in batch]
            embeds = [e.tolist() if hasattr(e, 'tolist') else e for e in embeddings]

            print(f"[BATCH {current_batch}/{batch_count}] Upserting to ChromaDB...", flush=True)
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeds,
                metadatas=metadatas,
            )
            total_stored += len(batch)
            print(f"[BATCH {current_batch}/{batch_count}] ✓ Stored. Total: {total_stored}/{len(chunks)}", flush=True)
            
            # Clear GPU cache aggressively after each batch for memory efficiency
            torch.cuda.empty_cache()
                
        except RuntimeError as e:
            if "out of memory" in str(e).lower() or "cuda" in str(e).lower():
                print(f"[ERROR-BATCH {current_batch}] GPU OOM: {e}", flush=True)
                print(f"[FALLBACK] Moving model to CPU and retrying...", flush=True)
                
                # Move model to CPU permanently and retry with larger batch
                model.to("cpu")
                batch_size = 8  # Larger batches on CPU are safe
                
                # Retry this batch on CPU
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
            # Handle ChromaDB internal errors (like corrupted index)
            if any(x in str(e).lower() for x in ["internal", "hnsw", "index", "compaction"]):
                print(f"[ERROR-BATCH {current_batch}] ChromaDB internal error: {e}", flush=True)
                print(f"[RECOVERY] Attempting to reset and retry...", flush=True)
                
                # Force reinit of collection
                global _collection
                _collection = None
                
                # Try again with fresh collection
                try:
                    collection = _get_collection()
                    ids = [c["chunk_id"] for c in batch]
                    documents = [c["chunk_text"] for c in batch]
                    metadatas = [_to_metadata(c) for c in batch]
                    embeds = [e.tolist() if hasattr(e, 'tolist') else e for e in embeddings]
                    
                    collection.upsert(
                        ids=ids,
                        documents=documents,
                        embeddings=embeds,
                        metadatas=metadatas,
                    )
                    total_stored += len(batch)
                    print(f"[BATCH {current_batch}] ✓ Recovery successful", flush=True)
                except Exception as retry_err:
                    print(f"[ERROR-BATCH {current_batch}] Recovery failed: {retry_err}", flush=True)
                    raise
            else:
                print(f"[ERROR-BATCH {current_batch}] Unexpected error: {e}", flush=True)
                raise
    
    print(f"[SUCCESS] Stored all {total_stored} chunks to ChromaDB", flush=True)
    return total_stored


# ══════════════════════════════════════════════════════════════════════════════
# QUERY
# ══════════════════════════════════════════════════════════════════════════════

def query(
    text:      str,
    top_k:     int  = 10,
    language:  str  = None,
    kind:      str  = None,
    file_path: str  = None,
) -> list[dict]:
    """
    Semantic search over stored chunks (GPU-optimized).

    Parameters
    ----------
    text      : natural-language query, e.g. "method that validates JWT"
    top_k     : number of results to return
    language  : filter by "java" or "python" (optional)
    kind      : filter by node kind like "method", "class" (optional)
    file_path : filter to one file only (optional)

    Returns
    -------
    List of result dicts sorted by score descending.
    score is between 0.0 and 1.0 — higher means more similar.
    """
    model      = _get_model()
    collection = _get_collection()

    print(f"[QUERY] Encoding query on GPU (batch_size=1)...", flush=True)
    # Single query uses batch_size=1, GPU still handles this efficiently
    query_vec = model.encode(
        text,
        batch_size=1,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=False
    ).tolist()
    
    # Clear cache after query encoding
    torch.cuda.empty_cache()

    # build optional where filter
    where = _build_where(language=language, kind=kind, file_path=file_path)

    print(f"[QUERY] Searching ChromaDB for top {top_k} results...", flush=True)
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
            "score":        round(1.0 - results["distances"][0][i], 4),
            "chunk_id":     results["ids"][0][i],
            "node_id":      meta.get("node_id", ""),
            "kind":         meta.get("kind", ""),
            "language":     meta.get("language", ""),
            "name":         meta.get("name", ""),
            "qualified_name": meta.get("qualified_name", ""),
            "signature":    meta.get("signature", ""),
            "file_path":    meta.get("file_path", ""),
            "line_start":   meta.get("line_start", ""),
            "document":     results["documents"][0][i],
        })
    
    print(f"[QUERY] ✓ Found {len(output)} results", flush=True)
    return output


# ══════════════════════════════════════════════════════════════════════════════
# GET ALL CHUNKS
# ══════════════════════════════════════════════════════════════════════════════

def get_all_chunks() -> list[dict]:
    """
    Retrieve all chunks from the collection (used by IngestionPipeline).

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
            "chunk_id":      results["ids"][i],
            "node_id":       meta.get("node_id", ""),
            "kind":          meta.get("kind", ""),
            "language":      meta.get("language", ""),
            "name":          meta.get("name", ""),
            "qualified_name": meta.get("qualified_name", ""),
            "file_path":     meta.get("file_path", ""),
            "source":        meta.get("source", ""),
            "parent_id":     meta.get("parent_id", ""),
            "signature":     meta.get("signature", ""),
            "line_start":    meta.get("line_start", ""),
            "line_end":      meta.get("line_end", ""),
            "chunk_text":    results["documents"][i],
        })
    return output


# ══════════════════════════════════════════════════════════════════════════════
# DELETE
# ══════════════════════════════════════════════════════════════════════════════

def delete_file(file_path: str) -> None:
    """Remove all chunks that came from the given file_path."""
    try:
        collection = _get_collection()
        # Only try to delete if the collection has data
        count = collection.count()
        if count > 0:
            collection.delete(where={"file_path": file_path})
            print(f"Deleted previous chunks for {file_path}", flush=True)
    except Exception as e:
        # If deletion fails (usually due to index corruption), just skip
        # The collection will be fresh or overwritten anyway
        print(f"[INFO] Skipping delete for {file_path} (index may be initializing): {type(e).__name__}", flush=True)


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
        "node_id":       safe(chunk.get("node_id")),
        "kind":          safe(chunk.get("kind")),
        "language":      safe(chunk.get("language")),
        "name":          safe(chunk.get("name")),
        "qualified_name":safe(chunk.get("qualified_name")),
        "file_path":     safe(chunk.get("file_path")),
        "parent_id":     safe(chunk.get("parent_id")),
        "signature":     safe(chunk.get("signature")),
        "line_start":    safe(chunk.get("line_start")),
        "line_end":      safe(chunk.get("line_end")),
    }


def _build_where(language=None, kind=None, file_path=None):
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