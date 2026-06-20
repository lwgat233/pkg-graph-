"""
CLI entry point for pkg-graph.

Usage:
    pkg-graph <package...> [options]
    pkg-graph --system apt nginx
    pkg-graph --color colors.json --output graph nginx openssl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .resolvers import detect_system, get_resolver
from .engine import ResolverEngine, ResolveResult
from .graph import build_dot, build_json_report, load_colors, DEFAULT_COLORS


def main():
    parser = argparse.ArgumentParser(
        prog="pkg-graph",
        description="跨 Linux 发行版的离线递归依赖分析与可视化工具",
    )
    parser.add_argument("packages", nargs="+", help="要分析的包名（一个或多个）")
    parser.add_argument("--system", choices=["apt", "dnf", "yum", "pacman"],
                        help="包管理系统 (默认自动检测)")
    parser.add_argument("--build", action="store_true", help="包含构建依赖 (build-depends)")
    parser.add_argument("--recommends", action="store_true", help="包含推荐依赖")
    parser.add_argument("--suggests", action="store_true", help="包含建议依赖")
    parser.add_argument("--conflicts", action="store_true", help="包含冲突信息")
    parser.add_argument("--depth", type=int, default=20, help="最大递归深度 (默认: 20)")
    parser.add_argument("--color", type=str,
                        help='自定义颜色方案: JSON 文件路径 或 JSON 字符串 (见 README)')
    parser.add_argument("--output", "-o", type=str,
                        help="输出基础路径 (生成 <path>.dot, <path>.svg, <path>.json)")
    parser.add_argument("--json-only", action="store_true", help="只输出 JSON 报告到 stdout")
    parser.add_argument("--dot-only", action="store_true", help="只输出 DOT 到 stdout")
    parser.add_argument("--version", action="version", version=f"pkg-graph {__version__}")

    args = parser.parse_args()

    # Detect system
    system = args.system or detect_system()
    if system is None:
        print("错误: 无法自动检测包管理系统。请用 --system 显式指定。", file=sys.stderr)
        print("支持: apt, dnf, pacman", file=sys.stderr)
        sys.exit(1)

    print(f"系统: {system}", file=sys.stderr)
    print(f"目标包: {', '.join(args.packages)}", file=sys.stderr)

    # Resolve
    resolver = get_resolver(system)
    engine = ResolverEngine(resolver, max_depth=args.depth)

    print("解析依赖中...", file=sys.stderr)
    result = engine.resolve(
        args.packages,
        include_build=args.build,
        include_recommends=args.recommends,
        include_suggests=args.suggests,
        include_conflicts=args.conflicts,
    )

    # Load colors
    colors = load_colors(args.color)

    # Summary to stderr
    print(f"  节点: {len(result.nodes)}  边: {len(result.edges)}", file=sys.stderr)
    if result.missing_pkgs:
        print(f"  缺失: {len(result.missing_pkgs)} 个包", file=sys.stderr)
    if result.dep_conflicts:
        print(f"  冲突: {len(result.dep_conflicts)} 项", file=sys.stderr)
    if result.to_download:
        print(f"  待安装: {len(result.to_download)} 个包", file=sys.stderr)

    # Output
    if args.json_only:
        report = build_json_report(result, args.packages, colors)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    if args.dot_only:
        dot = build_dot(result, args.packages, colors)
        print(dot)
        return

    # File output
    base = args.output or "pkg-graph"
    dot_path = Path(f"{base}.dot")
    json_path = Path(f"{base}.json")
    svg_path = Path(f"{base}.svg")

    # Write DOT
    dot = build_dot(result, args.packages, colors)
    dot_path.write_text(dot)
    print(f"DOT  → {dot_path}", file=sys.stderr)

    # Write JSON
    report = build_json_report(result, args.packages, colors)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"JSON → {json_path}", file=sys.stderr)

    # Try to render SVG with graphviz
    try:
        import subprocess
        subprocess.run(
            ["dot", "-Tsvg", str(dot_path), "-o", str(svg_path)],
            check=True, capture_output=True, timeout=30
        )
        print(f"SVG  → {svg_path}", file=sys.stderr)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("(安装 graphviz 可自动生成 SVG: apt install graphviz)", file=sys.stderr)

    # Print summary
    print()
    print("═══ 分析报告 ═══")
    print(f"包管理系统: {system}")
    print(f"根包: {', '.join(args.packages)}")
    print(f"依赖图: {len(result.nodes)} 个节点, {len(result.edges)} 条边")
    print()

    if result.missing_pkgs:
        print("⚠ 缺失包（系统中未找到）:")
        for p in result.missing_pkgs:
            print(f"  - {p}")
    else:
        print("✅ 所有依赖包均在系统中存在")

    if result.dep_conflicts:
        print("\n⚠ 依赖冲突:")
        for c in result.dep_conflicts:
            print(f"  - {c}")

    if result.to_download:
        print(f"\n📦 需要下载的包 ({len(result.to_download)}):")
        for p in result.to_download[:20]:
            print(f"  - {p}")
        if len(result.to_download) > 20:
            print(f"  ... 及其他 {len(result.to_download) - 20} 个")

    print(f"\n文件: {dot_path}, {json_path}")
    if svg_path.exists():
        print(f"      {svg_path}")


if __name__ == "__main__":
    main()
