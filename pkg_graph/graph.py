"""
Graphviz 依赖图生成器。

支持用户自定义颜色方案，通过 --color 传入 JSON 文件或直接字符串。
默认颜色方案：
  depends        → #e74c3c (红)
  build-depends  → #3498db (蓝)
  recommends     → #2ecc71 (绿)
  suggests       → #f39c12 (橙)
  conflicts      → #9b59b6 (紫)
  root           → #1abc9c (青)
  missing        → #95a5a6 (灰)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .engine import ResolveResult, DepEdge


# ── default color scheme ────────────────────────────────────────────

DEFAULT_COLORS = {
    "depends":       "#e74c3c",  # red
    "build-depends": "#3498db",  # blue
    "recommends":    "#2ecc71",  # green
    "suggests":      "#f39c12",  # orange
    "conflicts":     "#9b59b6",  # purple
    "root":          "#1abc9c",  # teal
    "missing":       "#95a5a6",  # grey
    "node":          "#ecf0f1",  # light grey bg
    "edge":          "#7f8c8d",  # default edge
    "font":          "#2c3e50",  # dark text
}

# Human-readable labels
REL_LABELS = {
    "depends":       "Depends",
    "build-depends": "Build-Dep",
    "recommends":    "Recommends",
    "suggests":      "Suggests",
    "conflicts":     "Conflicts",
}


def load_colors(source: Optional[str] = None) -> dict[str, str]:
    """Load color scheme from a JSON file or JSON string. Merges with defaults."""
    colors = dict(DEFAULT_COLORS)
    if source is None:
        return colors

    # Try as file path first
    path = Path(source)
    if path.exists():
        raw = path.read_text()
    else:
        raw = source

    try:
        user_colors = json.loads(raw)
        colors.update(user_colors)
    except json.JSONDecodeError:
        pass

    return colors


def build_dot(result: ResolveResult,
              root_pkgs: list[str],
              colors: Optional[dict[str, str]] = None,
              title: str = "Package Dependency Graph") -> str:
    """Generate a Graphviz DOT string from a resolve result."""

    if colors is None:
        colors = DEFAULT_COLORS

    lines = [
        f'digraph "{title}" {{',
        '  rankdir=TB;',
        '  bgcolor="white";',
        '  node [shape=box, style=filled, fillcolor="#ecf0f1", fontcolor="#2c3e50", fontname="sans-serif", fontsize=11];',
        '  edge [fontname="sans-serif", fontsize=9, color="#7f8c8d"];',
        '',
        f'  label="{title}";',
        '  labelloc=t;',
        '  fontsize=16;',
        '  fontname="sans-serif";',
        '',
    ]

    # Nodes
    for name, node in result.nodes.items():
        is_root = name in root_pkgs
        is_missing = node.version == "missing"

        if is_missing:
            fill = colors.get("missing", DEFAULT_COLORS["missing"])
            label = f"{name}\\n[未找到]"
        elif is_root:
            fill = colors.get("root", DEFAULT_COLORS["root"])
            label = f"{name}\\nv{node.version}"
        else:
            fill = colors.get("node", DEFAULT_COLORS["node"])
            label = f"{name}\\nv{node.version}"

        node_id = _safe_id(name)
        lines.append(f'  {node_id} [label="{label}", fillcolor="{fill}"];')

    lines.append("")

    # Edges
    for edge in result.edges:
        src = _safe_id(edge.source)
        tgt = _safe_id(edge.target)
        edge_color = colors.get(edge.rel_type, colors.get("edge", "#7f8c8d"))
        edge_label = REL_LABELS.get(edge.rel_type, edge.rel_type)

        style = "dashed" if edge.rel_type in ("recommends", "suggests") else "solid"
        lines.append(
            f'  {src} -> {tgt} '
            f'[label="{edge_label}", color="{edge_color}", fontcolor="{edge_color}", style={style}];'
        )

    lines.append("}")
    return "\n".join(lines)


def build_json_report(result: ResolveResult,
                      root_pkgs: list[str],
                      colors: Optional[dict[str, str]] = None) -> dict:
    """Generate a JSON report."""
    if colors is None:
        colors = DEFAULT_COLORS

    nodes = {}
    for name, node in result.nodes.items():
        nodes[name] = {
            "version": node.version,
            "system": node.system,
            "is_root": name in root_pkgs,
            "depends": node.depends,
            "build_depends": node.build_depends,
            "recommends": node.recommends,
            "suggests": node.suggests,
            "conflicts": node.conflicts,
        }

    edges = []
    for e in result.edges:
        edges.append({
            "source": e.source,
            "target": e.target,
            "type": e.rel_type,
        })

    return {
        "title": "Package Dependency Report",
        "system": result.nodes[root_pkgs[0]].system if root_pkgs and root_pkgs[0] in result.nodes else "unknown",
        "root_packages": root_pkgs,
        "total_nodes": len(result.nodes),
        "total_edges": len(result.edges),
        "nodes": nodes,
        "edges": edges,
        "conflicts": {
            "missing_packages": result.missing_pkgs,
            "version_conflicts": result.version_conflicts,
            "dep_conflicts": result.dep_conflicts,
        },
        "to_download": result.to_download,
        "colors": colors,
    }


def _safe_id(name: str) -> str:
    """Make a DOT-safe identifier from a package name."""
    # Replace special chars
    safe = name.replace("-", "_").replace(".", "_").replace("+", "_")
    if not safe[0].isalpha() and safe[0] != '_':
        safe = "n_" + safe
    return safe
