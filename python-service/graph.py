"""
graph.py
--------
Takes source code, parses it with tree-sitter, and builds a graph.

A graph is just two plain lists:
    nodes  - list of dicts, each dict is one class/method/function/field
    edges  - list of dicts, each dict is one relationship (CONTAINS, CALLS, INHERITS...)

Every node looks like:
    {
        "id":          "com.example.UserService.getUser",   # unique dotted path
        "kind":        "method",                            # class/method/function/field/...
        "language":    "java",
        "name":        "getUser",
        "parent_id":   "com.example.UserService",
        "source":      "public User getUser(...) { ... }",  # raw source of this node
        "signature":   "public User getUser(int id)",
        "docstring":   "Returns a user by ID.",
        "return_type": "User",
        "parameters":  [{"name": "id", "type": "int"}],
        "calls":       ["userRepository.findById", "log.info"],
        "line_start":  12,
        "line_end":    20,
    }

Every edge looks like:
    {
        "kind":      "CONTAINS",   # CONTAINS / CALLS / INHERITS / IMPLEMENTS / USES
        "source_id": "com.example.UserService",
        "target_id": "com.example.UserService.getUser",
    }

How to use:
    from graph import build_graph

    graph = build_graph(source_code, file_path="src/UserService.java", language="java")
    print(graph["nodes"])
    print(graph["edges"])
"""

from tree_sitter import Language, Parser
import tree_sitter_java as tsjava
import tree_sitter_python as tspython

# ── Language singletons ────────────────────────────────────────────────────
_JAVA_LANG   = Language(tsjava.language())
_PYTHON_LANG = Language(tspython.language())


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def build_graph(source: str, file_path: str = "", language: str = "java") -> dict:
    """
    Parse source code and return a graph dict with 'nodes' and 'edges'.

    Parameters
    ----------
    source    : full source text of one file
    file_path : path to the file (used only for building unique node IDs)
    language  : "java" or "python"

    Returns
    -------
    { "nodes": [...], "edges": [...], "file_path": ..., "language": ... }
    """
    src_bytes = source.encode("utf-8")

    if language == "java":
        parser = Parser(language=_JAVA_LANG)
        tree   = parser.parse(src_bytes)
        nodes, edges = _parse_java(tree.root_node, src_bytes)

    elif language == "python":
        parser = Parser(language=_PYTHON_LANG)
        tree   = parser.parse(src_bytes)
        nodes, edges = _parse_python(tree.root_node, src_bytes, file_path)

    else:
        raise ValueError(f"Unsupported language: {language}. Use 'java' or 'python'.")

    return {
        "nodes":     nodes,
        "edges":     edges,
        "file_path": file_path,
        "language":  language,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _children_of_type(node, *types):
    return [c for c in node.children if c.type in types]


def _find_all(node, target: str):
    results = []
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type == target:
            results.append(n)
        stack.extend(reversed(n.children))
    return results


def _node(kind, node_id, name, language, **extra) -> dict:
    return {
        "id":          node_id,
        "kind":        kind,
        "language":    language,
        "name":        name,
        "parent_id":   extra.pop("parent_id", None),
        "source":      extra.pop("source", ""),
        "signature":   extra.pop("signature", ""),
        "docstring":   extra.pop("docstring", ""),
        "return_type": extra.pop("return_type", ""),
        "parameters":  extra.pop("parameters", []),
        "calls":       extra.pop("calls", []),
        "line_start":  extra.pop("line_start", None),
        "line_end":    extra.pop("line_end", None),
        **extra,
    }


def _edge(kind: str, source_id: str, target_id: str) -> dict:
    return {"kind": kind, "source_id": source_id, "target_id": target_id}


# ══════════════════════════════════════════════════════════════════════════════
# JAVA PARSER
# ══════════════════════════════════════════════════════════════════════════════

def _parse_java(root, src: bytes):
    nodes = []
    edges = []

    # ── package name ─────────────────────────────────────────────────────
    package_name = ""
    for pkg in _children_of_type(root, "package_declaration"):
        for c in pkg.children:
            if c.type in ("scoped_identifier", "identifier"):
                package_name = _text(c, src)
                break

    # ── imports ───────────────────────────────────────────────────────────
    imports = []
    for imp in _children_of_type(root, "import_declaration"):
        for c in imp.children:
            if c.type in ("scoped_identifier", "identifier"):
                imports.append(_text(c, src))

    # ── classes / interfaces / enums ─────────────────────────────────────
    type_kinds = (
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
    )
    for type_node in _children_of_type(root, *type_kinds):
        _java_class(type_node, src, package_name, imports, nodes, edges)

    return nodes, edges


def _java_class(type_node, src, package_name, imports, nodes, edges):
    kind_map = {
        "interface_declaration": "interface",
        "enum_declaration":      "enum",
    }
    kind = kind_map.get(type_node.type, "class")

    name_node = type_node.child_by_field_name("name")
    if not name_node:
        return
    class_name = _text(name_node, src)
    class_id   = f"{package_name}.{class_name}" if package_name else class_name

    # superclass
    extends = None
    sc = type_node.child_by_field_name("superclass")
    if sc:
        for c in sc.children:
            if c.type == "type_identifier":
                extends = _text(c, src)
                break

    # interfaces
    implements = []
    si = type_node.child_by_field_name("interfaces") or type_node.child_by_field_name("extends_interfaces")
    if si:
        for c in si.children:
            if c.type == "type_identifier":
                implements.append(_text(c, src))
            elif c.type == "type_list":
                for tc in c.children:
                    if tc.type == "type_identifier":
                        implements.append(_text(tc, src))

    nodes.append(_node(
        kind, class_id, class_name, "java",
        source    = _text(type_node, src).split("{")[0].strip(),
        extends   = extends,
        implements= implements,
        imports   = imports,
        line_start= type_node.start_point[0] + 1,
        line_end  = type_node.end_point[0] + 1,
    ))

    if package_name:
        edges.append(_edge("CONTAINS", package_name, class_id))
    if extends:
        edges.append(_edge("INHERITS", class_id, extends))
    for iface in implements:
        edges.append(_edge("IMPLEMENTS", class_id, iface))

    body = (type_node.child_by_field_name("body")
            or next((c for c in type_node.children if c.type == "class_body"), None))
    if not body:
        return

    # fields
    for fd in _children_of_type(body, "field_declaration"):
        ft   = fd.child_by_field_name("type")
        mods = _java_modifiers(fd, src)
        ft_str = _text(ft, src) if ft else ""
        for decl in _find_all(fd, "variable_declarator"):
            vn = decl.child_by_field_name("name")
            if not vn:
                continue
            field_name = _text(vn, src)
            field_id   = f"{class_id}.{field_name}"
            nodes.append(_node(
                "field", field_id, field_name, "java",
                parent_id  = class_id,
                source     = f"{' '.join(mods)} {ft_str} {field_name};".strip(),
                return_type= ft_str,
                line_start = fd.start_point[0] + 1,
                line_end   = fd.end_point[0] + 1,
            ))
            edges.append(_edge("CONTAINS", class_id, field_id))

    # methods
    method_decls = _children_of_type(body, "method_declaration")
    for md in method_decls:
        mn = md.child_by_field_name("name")
        if not mn:
            continue
        method_name = _text(mn, src)
        method_id   = f"{class_id}.{method_name}"
        ret         = md.child_by_field_name("type")
        return_type = _text(ret, src) if ret else "void"
        params      = _java_params(md.child_by_field_name("parameters"), src)
        mods        = _java_modifiers(md, src)
        param_str   = ", ".join(f"{p['type']} {p['name']}" for p in params)
        signature   = f"{' '.join(mods)} {return_type} {method_name}({param_str})".strip()
        doc         = _java_docstring(md, src)
        calls       = _java_calls(md.child_by_field_name("body"), src)

        nodes.append(_node(
            "method", method_id, method_name, "java",
            parent_id  = class_id,
            source     = _text(md, src),
            signature  = signature,
            docstring  = doc or "",
            return_type= return_type,
            parameters = params,
            calls      = calls,
            line_start = md.start_point[0] + 1,
            line_end   = md.end_point[0] + 1,
        ))
        edges.append(_edge("CONTAINS", class_id, method_id))
        for call in calls:
            edges.append(_edge("CALLS", method_id, call))

    # constructors
    for ctor in _children_of_type(body, "constructor_declaration"):
        ctor_id   = f"{class_id}.<init>"
        params    = _java_params(ctor.child_by_field_name("parameters"), src)
        mods      = _java_modifiers(ctor, src)
        param_str = ", ".join(f"{p['type']} {p['name']}" for p in params)
        signature = f"{' '.join(mods)} {class_name}({param_str})".strip()
        doc       = _java_docstring(ctor, src)
        calls     = _java_calls(
            ctor.child_by_field_name("body") or ctor.child_by_field_name("constructor_body"),
            src,
        )

        nodes.append(_node(
            "constructor", ctor_id, "<init>", "java",
            parent_id  = class_id,
            source     = _text(ctor, src),
            signature  = signature,
            docstring  = doc or "",
            parameters = params,
            calls      = calls,
            line_start = ctor.start_point[0] + 1,
            line_end   = ctor.end_point[0] + 1,
        ))
        edges.append(_edge("CONTAINS", class_id, ctor_id))
        for call in calls:
            edges.append(_edge("CALLS", ctor_id, call))


def _java_modifiers(node, src):
    mods_node = node.child_by_field_name("modifiers")
    if not mods_node:
        return []
    accepted = {"public","private","protected","static","final","abstract","synchronized"}
    return [_text(c, src) for c in mods_node.children if c.type in accepted]


def _java_params(params_node, src):
    if not params_node:
        return []
    result = []
    for c in params_node.children:
        if c.type in ("formal_parameter", "spread_parameter"):
            t = c.child_by_field_name("type")
            n = c.child_by_field_name("name")
            result.append({
                "type": _text(t, src) if t else "",
                "name": _text(n, src) if n else "",
            })
    return result


def _java_docstring(node, src):
    parent = node.parent
    if not parent:
        return None
    prev = None
    for c in parent.children:
        if c.id == node.id:
            break
        if c.type == "block_comment":
            prev = c
        elif c.type not in ("modifiers", "annotation", "marker_annotation"):
            prev = None
    if prev:
        raw = _text(prev, src).strip()
        if raw.startswith("/**"):
            return raw
    return None


def _java_calls(body, src):
    if not body:
        return []
    seen = set()
    result = []
    for inv in _find_all(body, "method_invocation"):
        obj  = inv.child_by_field_name("object")
        name = inv.child_by_field_name("name")
        if not name:
            continue
        call = f"{_text(obj, src)}.{_text(name, src)}" if obj else _text(name, src)
        if call not in seen:
            seen.add(call)
            result.append(call)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# PYTHON PARSER
# ══════════════════════════════════════════════════════════════════════════════

def _parse_python(root, src: bytes, file_path: str):
    import os
    nodes = []
    edges = []

    module_name = os.path.splitext(os.path.basename(file_path))[0] if file_path else "module"

    for child in root.children:
        actual = _unwrap_decorated(child)
        if actual.type == "class_definition":
            _python_class(actual, src, module_name, nodes, edges)
        elif actual.type == "function_definition":
            _python_function(actual, src, module_name, nodes, edges)

    return nodes, edges


def _unwrap_decorated(node):
    if node.type != "decorated_definition":
        return node
    for c in node.children:
        if c.type in ("class_definition", "function_definition"):
            return c
    return node


def _python_class(class_node, src, module_name, nodes, edges):
    name_node = class_node.child_by_field_name("name")
    if not name_node:
        return
    class_name = _text(name_node, src)
    class_id   = f"{module_name}.{class_name}"

    # bases
    extends = None
    bases   = []
    args    = class_node.child_by_field_name("superclasses")
    if args:
        bases = [_text(c, src) for c in args.children if c.type in ("identifier", "attribute")]
    if bases:
        extends = bases[0]

    body    = class_node.child_by_field_name("body")
    doc     = _python_docstring(body, src) if body else None

    nodes.append(_node(
        "class", class_id, class_name, "python",
        source    = f"class {class_name}" + (f"({extends})" if extends else ""),
        docstring = doc or "",
        extends   = extends,
        line_start= class_node.start_point[0] + 1,
        line_end  = class_node.end_point[0] + 1,
    ))

    if extends:
        edges.append(_edge("INHERITS", class_id, extends))

    if not body:
        return

    method_nodes = []
    for c in body.children:
        actual = _unwrap_decorated(c)
        if actual.type == "function_definition":
            method_nodes.append(actual)

    for fn in method_nodes:
        _python_function(fn, src, class_id, nodes, edges)


def _python_function(fn_node, src, parent_id, nodes, edges):
    name_node = fn_node.child_by_field_name("name")
    if not name_node:
        return
    fn_name = _text(name_node, src)
    fn_id   = f"{parent_id}.{fn_name}"

    params_node = fn_node.child_by_field_name("parameters")
    params      = _python_params(params_node, src) if params_node else []

    ret_node    = fn_node.child_by_field_name("return_type")
    return_type = _text(ret_node, src).lstrip("->").strip() if ret_node else ""

    param_str  = ", ".join(
        f"{p['name']}: {p['type']}" if p["type"] else p["name"]
        for p in params
    )
    signature  = f"def {fn_name}({param_str})" + (f" -> {return_type}" if return_type else "")

    body  = fn_node.child_by_field_name("body")
    doc   = _python_docstring(body, src) if body else None
    calls = _python_calls(body, src) if body else []

    nodes.append(_node(
        "function", fn_id, fn_name, "python",
        parent_id  = parent_id,
        source     = _text(fn_node, src),
        signature  = signature,
        docstring  = doc or "",
        return_type= return_type,
        parameters = params,
        calls      = calls,
        line_start = fn_node.start_point[0] + 1,
        line_end   = fn_node.end_point[0] + 1,
    ))
    edges.append(_edge("CONTAINS", parent_id, fn_id))
    for call in calls:
        edges.append(_edge("CALLS", fn_id, call))


def _python_params(params_node, src):
    result = []
    for c in params_node.children:
        if c.type == "identifier":
            name = _text(c, src)
            if name not in ("self", "cls"):
                result.append({"name": name, "type": ""})
        elif c.type == "typed_parameter":
            nn = next((x for x in c.children if x.type == "identifier"), None)
            tn = c.child_by_field_name("type")
            name = _text(nn, src) if nn else ""
            if name not in ("self", "cls"):
                result.append({"name": name, "type": _text(tn, src) if tn else ""})
        elif c.type in ("default_parameter", "typed_default_parameter"):
            nn = c.child_by_field_name("name")
            tn = c.child_by_field_name("type")
            name = _text(nn, src) if nn else ""
            if name not in ("self", "cls"):
                result.append({"name": name, "type": _text(tn, src) if tn else ""})
    return result


def _python_docstring(body, src):
    for c in body.children:
        if c.type == "expression_statement":
            for sub in c.children:
                if sub.type == "string":
                    raw = _text(sub, src).strip()
                    for q in ('"""', "'''", '"', "'"):
                        if raw.startswith(q) and raw.endswith(q) and len(raw) > 2 * len(q):
                            return raw[len(q):-len(q)].strip()
            break
    return None


def _python_calls(body, src):
    seen = set()
    result = []
    for call_node in _find_all(body, "call"):
        fn = call_node.child_by_field_name("function")
        if not fn:
            continue
        if fn.type == "attribute":
            obj  = fn.child_by_field_name("object")
            attr = fn.child_by_field_name("attribute")
            call = f"{_text(obj, src)}.{_text(attr, src)}" if obj and attr else _text(fn, src)
        else:
            call = _text(fn, src)
        if call not in seen:
            seen.add(call)
            result.append(call)
    return result