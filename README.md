本项目由ai生成
# pkg-graph

跨 Linux 发行版的**离线**递归依赖分析与可视化工具。

支持 apt (Debian/Ubuntu)、dnf/yum (RHEL/Fedora)、pacman (Arch) 三大主流包管理系统。

## 功能

- 递归解析硬依赖（depends），一级记录软依赖（recommends / suggests / build-depends）
- 同名包自动去重，避免循环递归
- 冲突检测：依赖内冲突 + 系统中缺失的包
- 生成下载清单
- 输出格式：JSON 报告 + Graphviz DOT 文件 + SVG 依赖图
- **自定义颜色**：通过 JSON 文件自定义每种依赖类型的颜色

## 安装

```bash
cd pkg-graph
pip install -e .        # 开发模式安装
# 可选：安装 graphviz 用于 SVG 渲染
# apt install graphviz   (Debian/Ubuntu)
# pacman -S graphviz     (Arch)
```

依赖要求：
- Python >= 3.10
- graphviz (可选，用于 SVG 渲染)

## 使用

```bash
# 自动检测系统，分析单个包
pkg-graph bash

# 分析多个根包
pkg-graph nginx openssl postgresql

# 显式指定系统
pkg-graph --system apt nginx

# 包含软依赖
pkg-graph --recommends --suggests --conflicts nginx

# 自定义输出路径（生成 output.dot, output.json, output.svg）
pkg-graph -o output bash

# 只输出 JSON 到 stdout
pkg-graph --json-only bash > deps.json

# 只输出 DOT 到 stdout（可 pipe 给 dot）
pkg-graph --dot-only bash | dot -Tsvg -o deps.svg

# 自定义颜色方案
pkg-graph --color my-colors.json bash
```

## 颜色自定义

默认颜色方案：

| 类型 | 颜色 | 说明 |
|------|------|------|
| depends | `#e74c3c` | 红色，实线 |
| build-depends | `#3498db` | 蓝色，虚线 |
| recommends | `#2ecc71` | 绿色，虚线 |
| suggests | `#f39c12` | 橙色，虚线 |
| conflicts | `#9b59b6` | 紫色 |
| root | `#1abc9c` | 青色（根节点） |
| missing | `#95a5a6` | 灰色（未找到的包） |
| node | `#ecf0f1` | 浅灰背景 |
| edge | `#7f8c8d` | 默认边颜色 |

通过 JSON 文件自定义（只需覆盖想要修改的颜色即可）：

```json
{
  "depends": "#ff6b6b",
  "build-depends": "#4ecdc4",
  "root": "#00d2d3"
}
```

```bash
pkg-graph --color colors.json bash
```

也可以直接传 JSON 字符串（shell 注意转义）：

```bash
pkg-graph --color '{"depends":"#ff0000","root":"#00ff00"}' bash
```

## 输出说明

| 文件 | 内容 |
|------|------|
| `*.dot` | Graphviz DOT 格式依赖图 |
| `*.json` | 完整 JSON 报告（节点、边、冲突、下载清单） |
| `*.svg` | 自动生成的 SVG 图（需安装 graphviz） |

### JSON 报告结构

```json
{
  "title": "Package Dependency Report",
  "system": "apt",
  "root_packages": ["bash"],
  "total_nodes": 3,
  "total_edges": 2,
  "nodes": {
    "bash": {
      "version": "5.2.37-2+b8",
      "system": "apt",
      "is_root": true,
      "depends": ["base-files", "debianutils"],
      "build_depends": [],
      "recommends": [],
      "suggests": [],
      "conflicts": []
    }
  },
  "edges": [
    {"source": "bash", "target": "base-files", "type": "depends"}
  ],
  "conflicts": {
    "missing_packages": ["base-files"],
    "version_conflicts": [],
    "dep_conflicts": []
  },
  "to_download": ["base-files", "debianutils"],
  "colors": { ... }
}
```

## 项目结构

```
pkg-graph/
├── pkg_graph/              # Python 包
│   ├── __init__.py
│   ├── cli.py              # CLI 入口
│   ├── engine.py           # 递归解析引擎
│   ├── graph.py            # Graphviz DOT + JSON 报告生成
│   └── resolvers/
│       └── __init__.py     # 解析器基类 + apt/dnf/pacman 实现
├── scripts/                # Shell 脚本（系统对接层）
│   ├── apt-deps.sh         # Debian/Ubuntu
│   ├── dnf-deps.sh         # RHEL/Fedora
│   └── pacman-deps.sh      # Arch Linux
├── sample-colors.json      # 示例自定义颜色文件
├── tests/                  # 测试
├── pyproject.toml
└── README.md
```

## 工作原理

1. **系统检测**：自动检测可用的包管理器（dpkg-query → dnf → pacman）
2. **Shell 脚本查询**：调用对应脚本，从本地包管理数据库获取依赖信息
3. **递归解析**：BFS 遍历硬依赖树，同名去重避免循环
4. **冲突分析**：对比依赖图与本地已安装包，标记缺失和冲突
5. **图形生成**：输出 JSON 报告 + Graphviz DOT 文件

## 局限

- 仅离线分析（解析本地包管理器缓存）
- 硬依赖才递归；软依赖只记录一级
- 跨发行版同名不同版本的深度追踪待实现
