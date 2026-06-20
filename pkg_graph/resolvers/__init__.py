"""
Base resolver + data model for package dependency queries.

All resolvers return a PkgInfo dict:
{
    "name": str,
    "version": str,
    "depends": [str, ...],
    "build-depends": [str, ...],
    "recommends": [str, ...],
    "suggests": [str, ...],
    "conflicts": [str, ...],
    "system": str,
}
"""

from __future__ import annotations

import json
import subprocess
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"


# ── data model ──────────────────────────────────────────────────────

@dataclass
class DepEdge:
    """A directed edge in the dependency graph."""
    source: str          # package name that depends
    target: str          # package name being depended on
    rel_type: str        # "depends" | "build-depends" | "recommends" | "suggests"
    constraint: str = "" # version constraint string, e.g. ">= 1.2.3"


@dataclass
class PkgNode:
    """A node in the resolved dependency graph."""
    name: str
    version: str = "unknown"
    system: str = ""
    depends: list[str] = field(default_factory=list)
    build_depends: list[str] = field(default_factory=list)
    recommends: list[str] = field(default_factory=list)
    suggests: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    # cross-system "same name different version" tracking
    alt_versions: dict[str, str] = field(default_factory=dict)  # system -> version


# ── base resolver ───────────────────────────────────────────────────

class BaseResolver(ABC):
    """Abstract resolver. Subclasses implement _query(pkg_name) -> PkgNode."""

    system: str = "unknown"

    @abstractmethod
    def query(self, pkg_name: str, *, build: bool = False,
              recommends: bool = False, suggests: bool = False,
              conflicts: bool = False) -> PkgNode:
        ...

    @staticmethod
    def _parse_name(raw: str) -> str:
        """Strip version constraints from a dep string. 'libfoo (>= 1.0)' -> 'libfoo'."""
        # Remove version constraints in parentheses
        raw = re.sub(r'\s*\([^)]*\)', '', raw)
        # Remove arch qualifiers like :amd64
        raw = re.sub(r':[a-zA-Z0-9_-]+', '', raw)
        # Remove version ops at end
        raw = re.sub(r'\s*[<>=!]+\s*\S+$', '', raw)
        return raw.strip()

    @staticmethod
    def _parse_raw_list(raw: str) -> list[str]:
        """Parse a raw string of space/comma-separated deps into a clean list."""
        if not raw or raw in ("None", "none", ""):
            return []
        # Split on spaces and commas
        items = re.split(r'[,\s]+', raw)
        return [i.strip() for i in items if i.strip()]


# ── apt resolver ────────────────────────────────────────────────────

class AptResolver(BaseResolver):
    system = "apt"

    def query(self, pkg_name: str, **flags) -> PkgNode:
        args = [str(SCRIPTS_DIR / "apt-deps.sh"), pkg_name]
        if flags.get("build"):
            args.append("--build")
        if flags.get("recommends"):
            args.append("--recommends")
        if flags.get("suggests"):
            args.append("--suggests")
        if flags.get("conflicts"):
            args.append("--conflicts")

        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            return PkgNode(name=pkg_name, system="apt", version="error")

        return PkgNode(
            name=data.get("name", pkg_name),
            version=data.get("version", "unknown"),
            system="apt",
            depends=[self._parse_name(d) for d in data.get("depends", [])],
            build_depends=[self._parse_name(d) for d in data.get("build-depends", [])],
            recommends=[self._parse_name(d) for d in data.get("recommends", [])],
            suggests=[self._parse_name(d) for d in data.get("suggests", [])],
            conflicts=[self._parse_name(d) for d in data.get("conflicts", [])],
        )


# ── dnf / yum resolver ──────────────────────────────────────────────

class DnfResolver(BaseResolver):
    system = "dnf"

    def query(self, pkg_name: str, **flags) -> PkgNode:
        args = [str(SCRIPTS_DIR / "dnf-deps.sh"), pkg_name]
        if flags.get("build"):
            args.append("--build")
        if flags.get("recommends"):
            args.append("--recommends")
        if flags.get("suggests"):
            args.append("--suggests")
        if flags.get("conflicts"):
            args.append("--conflicts")

        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            return PkgNode(name=pkg_name, system="dnf", version="error")

        sys_name = data.get("system", "dnf")
        return PkgNode(
            name=data.get("name", pkg_name),
            version=data.get("version", "unknown"),
            system=sys_name,
            depends=[self._parse_name(d) for d in data.get("depends", [])],
            build_depends=[],
            recommends=[self._parse_name(d) for d in data.get("recommends", [])],
            suggests=[self._parse_name(d) for d in data.get("suggests", [])],
            conflicts=[self._parse_name(d) for d in data.get("conflicts", [])],
        )


# ── pacman resolver ─────────────────────────────────────────────────

class PacmanResolver(BaseResolver):
    system = "pacman"

    def query(self, pkg_name: str, **flags) -> PkgNode:
        args = [str(SCRIPTS_DIR / "pacman-deps.sh"), pkg_name]
        if flags.get("build"):
            args.append("--build")
        if flags.get("recommends") or flags.get("suggests"):
            args.append("--recommends")
        if flags.get("conflicts"):
            args.append("--conflicts")

        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            return PkgNode(name=pkg_name, system="pacman", version="error")

        return PkgNode(
            name=data.get("name", pkg_name),
            version=data.get("version", "unknown"),
            system="pacman",
            depends=[self._parse_name(d) for d in data.get("depends", [])],
            build_depends=[self._parse_name(d) for d in data.get("build-depends", [])],
            recommends=[self._parse_name(d) for d in data.get("recommends", [])],
            suggests=[self._parse_name(d) for d in data.get("suggests", [])],
            conflicts=[self._parse_name(d) for d in data.get("conflicts", [])],
        )


# ── factory ─────────────────────────────────────────────────────────

def detect_system() -> Optional[str]:
    """Auto-detect which package manager is available on this system."""
    checks = [
        ("apt", ["dpkg-query", "-W"]),
        ("dnf", ["dnf", "--version"]),
        ("pacman", ["pacman", "-V"]),
    ]
    for name, cmd in checks:
        try:
            subprocess.run(cmd, capture_output=True, timeout=5, check=True)
            return name
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def get_resolver(system: Optional[str] = None) -> BaseResolver:
    """Factory: return the appropriate resolver for the system."""
    if system is None:
        system = detect_system()
    if system is None:
        raise RuntimeError(
            "无法自动检测包管理器。请用 --system apt|dnf|pacman 显式指定。"
        )

    resolvers = {
        "apt": AptResolver,
        "dnf": DnfResolver,
        "yum": DnfResolver,
        "pacman": PacmanResolver,
    }
    cls = resolvers.get(system)
    if cls is None:
        raise ValueError(f"不支持的系统: {system}。可选: apt, dnf, pacman")
    return cls()
