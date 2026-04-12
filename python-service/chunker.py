"""
chunker.py
----------
Takes the graph (output of graph.py) and turns every node into a
"chunk" — a rich block of text that gets embedded and stored.

Why not just embed the raw source code?
    Raw code embeds poorly. "public User getUser(int id)" and
    "method that fetches a user by ID" mean the same thing but have
    very different embeddings. A natural-language chunk bridges that gap.

What a chunk looks like (for a method):
    [CLASS CONTEXT]
    class UserService extends BaseService
    Fields: private UserRepository userRepository; private Logger log;

    [METHOD] com.example.UserService.getUser
    public User getUser(int id)
    Description: Returns a user by their ID from the database.
    Returns: User
    Calls: userRepository.findById, log.info

    <raw source code>

    [NEIGHBORS] prev: public void createUser(...) | next: public void deleteUser(...)

The class context block is injected into every method chunk so that
two different classes with a method named "save" produce different embeddings.

How to use:
    from chunker import build_chunks

    chunks = build_chunks(graph)
    for chunk in chunks:
        print(chunk["chunk_text"])
        print(chunk["node_id"])
"""

# GPU-optimized: Chunk size target is <200 tokens (approx 40-50 lines of code)
# Using token-based estimation: 1 line ≈ 3-5 tokens
MAX_TOKENS   = 200
MAX_LINES    = 40  # Conservative for token limit
OVERLAP_LINES = 5   # Minimal overlap for GPU memory efficiency


def _estimate_tokens(text: str) -> int:
    """
    Conservative token estimation: ~1 token per 4 characters.
    SentenceTransformer uses WordPiece tokenization (~1-2 tokens per word).
    """
    return len(text) // 4


def build_chunks(graph: dict) -> list[dict]:
    """
    Convert all nodes in the graph into embeddable chunk dicts.

    Parameters
    ----------
    graph : dict returned by graph.build_graph()

    Returns
    -------
    list of chunk dicts, each with:
        chunk_id, node_id, kind, language, name, qualified_name,
        chunk_text, source, file_path, parent_id, signature,
        line_start, line_end
    """
    node_map = {n["id"]: n for n in graph["nodes"]}
    chunks   = []

    for node in graph["nodes"]:
        kind = node["kind"]

        if kind in ("method", "function", "constructor"):
            chunks.extend(_chunk_function(node, node_map, graph["file_path"]))

        elif kind in ("class", "interface", "enum"):
            chunks.append(_chunk_class(node, graph["file_path"]))

    return chunks


# ── Class chunk ────────────────────────────────────────────────────────────

def _chunk_class(node: dict, file_path: str) -> dict:
    parts = []
    parts.append(f"[CLASS] {node['id']}")

    header = f"{node['kind']} {node['name']}"
    if node.get("extends"):
        header += f" extends {node['extends']}"
    if node.get("implements"):
        header += f" implements {', '.join(node['implements'])}"
    parts.append(header)

    if node.get("docstring"):
        parts.append(f"Description: {node['docstring']}")

    return _make_chunk(node, "\n".join(parts), file_path)


# ── Method / function chunk ────────────────────────────────────────────────

def _chunk_function(node: dict, node_map: dict, file_path: str) -> list[dict]:
    class_ctx    = _class_context(node, node_map)
    source_lines = node["source"].splitlines()

    # short method → single chunk
    if len(source_lines) <= MAX_LINES:
        text = _build_text(node, class_ctx, node["source"])
        return [_make_chunk(node, text, file_path)]

    # long method → overlapping sub-chunks
    return _split_long(node, class_ctx, source_lines, file_path)


def _class_context(node: dict, node_map: dict) -> str:
    parent = node_map.get(node.get("parent_id", ""))
    if not parent or parent["kind"] not in ("class", "interface", "enum"):
        return ""

    lines = ["[CLASS CONTEXT]"]
    header = f"{parent['kind']} {parent['name']}"
    if parent.get("extends"):
        header += f" extends {parent['extends']}"
    if parent.get("implements"):
        header += f" implements {', '.join(parent['implements'])}"
    lines.append(header)

    # include field names so the model knows what the class holds
    if parent.get("fields_summary"):
        lines.append(f"Fields: {', '.join(parent['fields_summary'][:6])}")

    return "\n".join(lines)


def _build_text(node: dict, class_ctx: str, source_body: str) -> str:
    parts = []

    if class_ctx:
        parts.append(class_ctx)
        parts.append("")

    label = node["kind"].upper()
    parts.append(f"[{label}] {node['id']}")

    if node.get("signature"):
        parts.append(node["signature"])

    if node.get("docstring"):
        parts.append(f"Description: {node['docstring']}")

    if node.get("return_type") and node["return_type"] not in ("void", "None", ""):
        parts.append(f"Returns: {node['return_type']}")

    parts.append("")
    parts.append(source_body)

    if node.get("calls"):
        parts.append("")
        parts.append(f"[CALLS] {', '.join(node['calls'][:8])}")

    return "\n".join(parts)


def _split_long(node: dict, class_ctx: str, source_lines: list, file_path: str) -> list:
    """
    Split long methods into GPU-friendly chunks of <200 tokens each.
    """
    chunks = []
    stride = max(1, MAX_LINES - OVERLAP_LINES)
    sig_prefix = f"// Inside: {node['signature']}\n" if node.get("signature") else ""

    idx  = 0
    part = 0
    while idx < len(source_lines):
        window = source_lines[idx: idx + MAX_LINES]
        body   = sig_prefix + "\n".join(window)
        text   = _build_text(node, class_ctx, body)
        
        # Verify token count stays under 200
        token_count = _estimate_tokens(text)
        if token_count > MAX_TOKENS:
            print(f"[WARNING] Chunk {node['id']}_part{part} has {token_count} tokens (limit: {MAX_TOKENS})", flush=True)
        
        chunk  = _make_chunk(node, text, file_path)
        chunk["chunk_id"] = chunk["chunk_id"] + f"_part{part}"
        chunk["token_count"] = token_count
        chunks.append(chunk)
        idx  += stride
        part += 1

    return chunks


# ── Shared factory ─────────────────────────────────────────────────────────

def _make_chunk(node: dict, chunk_text: str, file_path: str) -> dict:
    import uuid
    return {
        "chunk_id":      str(uuid.uuid4()),
        "node_id":       node["id"],
        "kind":          node["kind"],
        "language":      node["language"],
        "name":          node["name"],
        "qualified_name":node["id"],
        "chunk_text":    chunk_text,
        "source":        node.get("source", ""),
        "file_path":     file_path,
        "parent_id":     node.get("parent_id", ""),
        "signature":     node.get("signature", ""),
        "line_start":    node.get("line_start"),
        "line_end":      node.get("line_end"),
    }