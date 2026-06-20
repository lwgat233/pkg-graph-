"""
递归依赖解析引擎。

核心数据结构：
- nodes: dict[name] -> PkgNode  已解析的节点
- edges: list[DepEdge]          有向边
- visited: set[name]            已访问（避免重复递归）
- version_conflicts: list        同名不同版本的冲突记录
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .resolvers import BaseResolver, PkgNode, DepEdge


@dataclass
class ResolveResult:
    """完整的递归解析结果。"""
    nodes: dict[str, PkgNode] = field(default_factory=dict)
    edges: list[DepEdge] = field(default_factory=list)
    # 冲突
    missing_pkgs: list[str] = field(default_factory=list)       # 系统中不存在的包
    version_conflicts: list[str] = field(default_factory=list)  # "同名不同版本"报告
    dep_conflicts: list[str] = field(default_factory=list)     # 依赖内冲突
    # 下载清单 (不在本地已安装列表中的)
    to_download: list[str] = field(default_factory=list)


class ResolverEngine:
    """递归依赖解析引擎。

    核心规则：
    1. 同名即停止递归（避免循环）
    2. 同名不同版本 → 记录冲突，不深入递归
    3. 只递归 depends（硬依赖），recommends/suggests 只记录一级
    """

    def __init__(self, resolver: BaseResolver, max_depth: int = 20):
        self.resolver = resolver
        self.max_depth = max_depth

    def resolve(self, pkg_names: list[str],
                include_build: bool = False,
                include_recommends: bool = False,
                include_suggests: bool = False,
                include_conflicts: bool = False) -> ResolveResult:
        """从一组根包名开始递归解析依赖图。"""

        result = ResolveResult()
        # 已安装包的版本记录 (name -> version)，用于判定 to_download
        installed: dict[str, str] = {}

        # BFS queue: (pkg_name, depth, parent_name, rel_type)
        queue: deque[tuple[str, int, Optional[str], str]] = deque()
        for name in pkg_names:
            queue.append((name, 0, None, "root"))

        while queue:
            name, depth, parent, rel_type = queue.popleft()

            # 深度限制
            if depth > self.max_depth:
                continue

            # 同名检查 → 已解析过就跳过（但记录边）
            if name in result.nodes:
                if parent and parent != name:
                    result.edges.append(DepEdge(
                        source=parent, target=name, rel_type=rel_type
                    ))
                continue

            # 查询包信息
            node = self.resolver.query(
                name,
                build=include_build,
                recommends=include_recommends,
                suggests=include_suggests,
                conflicts=include_conflicts,
            )

            if node.version == "error":
                # 查询失败，记录为缺失
                result.missing_pkgs.append(name)
                result.nodes[name] = PkgNode(name=name, version="missing", system=self.resolver.system)
                if parent:
                    result.edges.append(DepEdge(source=parent, target=name, rel_type=rel_type))
                continue

            result.nodes[name] = node
            installed[name] = node.version

            # 记录边
            if parent:
                result.edges.append(DepEdge(source=parent, target=name, rel_type=rel_type))

            # 收集冲突信息
            if include_conflicts and node.conflicts:
                for c in node.conflicts:
                    result.dep_conflicts.append(f"{name} 与 {c} 冲突")

            # 递归进入 depends（硬依赖）
            for dep_name in node.depends:
                if dep_name and dep_name != name:
                    queue.append((dep_name, depth + 1, name, "depends"))

            # 一级记录 build-depends（不递归）
            if include_build:
                for bdep in node.build_depends:
                    if bdep and bdep != name:
                        result.edges.append(DepEdge(source=name, target=bdep, rel_type="build-depends"))
                        if bdep not in result.nodes:
                            bnode = self.resolver.query(bdep)
                            result.nodes[bdep] = bnode
                            installed[bdep] = bnode.version

            # 一级记录 recommends（不递归）
            if include_recommends:
                for rec in node.recommends:
                    if rec and rec != name:
                        result.edges.append(DepEdge(source=name, target=rec, rel_type="recommends"))
                        if rec not in result.nodes:
                            rnode = self.resolver.query(rec)
                            result.nodes[rec] = rnode

            # 一级记录 suggests（不递归）
            if include_suggests:
                for sug in node.suggests:
                    if sug and sug != name:
                        result.edges.append(DepEdge(source=name, target=sug, rel_type="suggests"))
                        if sug not in result.nodes:
                            snode = self.resolver.query(sug)
                            result.nodes[sug] = snode

        # 生成下载清单：依赖图中存在但本机未安装的包
        # (这里简化为所有不在初始根包列表中的包)
        for name in result.nodes:
            if name not in pkg_names and result.nodes[name].version != "missing":
                result.to_download.append(name)

        return result
