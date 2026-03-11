from pathlib import Path

from graphviz import Digraph


def _safe_node_id(value):
    return value.replace("\\", "_").replace("/", "_").replace(".", "_").replace("-", "_")


def generate_architecture_diagram(files, repo_root=None):
    dot = Digraph("codebase")
    dot.attr(rankdir="LR", bgcolor="#0b1320", pad="0.45", nodesep="0.45", ranksep="0.85")
    dot.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fontname="Helvetica",
        fontsize="14",
        color="#23324d",
        fillcolor="#13203a",
        fontcolor="#f8fafc",
        margin="0.18,0.12",
    )
    dot.attr("edge", color="#5ea3ff", penwidth="1.4", arrowsize="0.8")

    resolved_root = Path(repo_root).resolve() if repo_root else None
    directories = {}
    relative_files = []

    for file_path in files:
        path = Path(file_path)
        try:
            relative_path = path.resolve().relative_to(resolved_root) if resolved_root else Path(path.name)
        except Exception:
            relative_path = Path(path.name)

        relative_files.append(relative_path)
        directory = str(relative_path.parent) if str(relative_path.parent) != "." else "root"
        directories.setdefault(directory, []).append(relative_path)

    dot.node(
        "repo",
        "Repository",
        shape="box",
        style="rounded,filled",
        fillcolor="#f7a12b",
        color="#f7a12b",
        fontcolor="#111827",
        penwidth="1.6",
    )

    priority_files = []
    for relative_path in relative_files:
        lower_name = relative_path.name.lower()
        if lower_name in {"app.py", "main.py", "server.py", "index.js"}:
            priority_files.append(relative_path)

    entry_id = None
    if priority_files:
        entry = priority_files[0]
        entry_id = _safe_node_id(str(entry))
        dot.node(entry_id, entry.name, fillcolor="#1f3257", color="#7dc1ff", penwidth="1.8")
        dot.edge("repo", entry_id, label="entry")

    for directory, file_paths in directories.items():
        cluster_name = f"cluster_{_safe_node_id(directory)}"
        label = "Root" if directory == "root" else directory
        with dot.subgraph(name=cluster_name) as subgraph:
            subgraph.attr(
                label=label,
                color="#23324d",
                fontcolor="#9cc5ff",
                style="rounded",
                bgcolor="#0f1a2d",
                margin="16",
            )
            for relative_path in file_paths[:6]:
                node_id = _safe_node_id(str(relative_path))
                subgraph.node(node_id, relative_path.name)

        anchor = _safe_node_id(str(file_paths[0]))
        dot.edge("repo", anchor, color="#ffb469" if directory == "root" else "#5ea3ff")
        if entry_id and anchor != entry_id:
            dot.edge(entry_id, anchor, style="dashed", color="#4b6b9a")

    return dot
