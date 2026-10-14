#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_check.py —— 零依赖的项目规范检查

    python scripts/style_check.py

检查项：
  1. 行宽 ≤ 88 列
  2. 行尾空白、制表符
  3. 文件结尾恰好一个换行
  4. 所有函数都有返回类型标注
  5. 非双下划线函数都有 docstring
  6. 未使用的 import
  7. `__all__` 与模块内公开定义一致（仅在模块定义了 `__all__` 时检查）

为什么自己写而不用 ruff / flake8：本项目的卖点之一是**零第三方依赖**，
连开发期的 linter 依赖也不引入。CI 会跑这个脚本，不达标直接失败。
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_WIDTH = 88

# 扫描范围：源码、测试与演示脚本
TARGETS = ("scripts", "tests")
EXTRA_FILES = ("demo.py",)


def py_files() -> list[Path]:
    """收集所有需要检查的 Python 文件。"""
    files: list[Path] = []
    for target in TARGETS:
        files.extend(sorted((ROOT / target).rglob("*.py")))
    for extra in EXTRA_FILES:
        path = ROOT / extra
        if path.exists():
            files.append(path)
    return [f for f in files if "__pycache__" not in f.parts]


def check_lines(path: Path) -> list[str]:
    """检查行宽、行尾空白、制表符与文件结尾换行。"""
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")

    if not text.endswith("\n"):
        problems.append("文件结尾缺少换行")
    elif text.endswith("\n\n"):
        problems.append("文件结尾有多余空行（应恰好一个换行）")

    for i, line in enumerate(text.splitlines(), 1):
        if len(line) > MAX_WIDTH:
            problems.append(f"L{i}: 行宽 {len(line)} > {MAX_WIDTH}")
        if line != line.rstrip():
            problems.append(f"L{i}: 行尾有空白")
        if "\t" in line:
            problems.append(f"L{i}: 含制表符")
    return problems


def imported_names(tree: ast.Module) -> list[tuple[str, int]]:
    """收集模块级 import 绑定的名字与行号（跳过 `__future__`）。"""
    names: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "__future__":
                    continue
                names.append(((alias.asname or alias.name).split(".")[0], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for alias in node.names:
                names.append((alias.asname or alias.name, node.lineno))
    return names


def collect_public_names(tree: ast.Module) -> set[str]:
    """收集模块内所有公开（不以下划线开头）的顶层定义名。"""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {n for n in names if not n.startswith("_")}


def check_ast(path: Path) -> list[str]:
    """检查返回类型标注、docstring、未使用 import 与 `__all__` 一致性。"""
    problems: list[str] = []
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is None:
                problems.append(f"L{node.lineno}: {node.name}() 缺少返回类型标注")
            if not node.name.startswith("__") and ast.get_docstring(node) is None:
                problems.append(f"L{node.lineno}: {node.name}() 缺少 docstring")

    # 未使用 import：把 import 行去掉后，名字在源码里再也搜不到就算未使用。
    # 用「全文搜索」而不是只认 ast.Name，是为了兼容字符串化的注解
    # （本项目所有模块都有 `from __future__ import annotations`）。
    imports = imported_names(tree)
    import_lines = {lineno for _, lineno in imports}
    body = "\n".join(line for i, line in enumerate(source.splitlines(), 1)
                     if i not in import_lines)
    for name, lineno in imports:
        if not re.search(rf"\b{re.escape(name)}\b", body):
            problems.append(f"L{lineno}: 未使用的 import：{name}")

    declared = None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "__all__"):
            declared = {e.value for e in node.value.elts
                        if isinstance(e, ast.Constant)}
    if declared is not None:
        public = collect_public_names(tree)
        for missing in sorted(public - declared):
            problems.append(f"`__all__` 缺少公开定义：{missing}")
        for extra in sorted(declared - public - {"__version__"}):
            problems.append(f"`__all__` 含不存在的定义：{extra}")
    return problems


def main() -> int:
    """扫描所有目标文件，打印问题并返回非零退出码（若有不达标项）。"""
    files = py_files()
    failures = 0
    for path in files:
        rel = path.relative_to(ROOT)
        try:
            problems = check_lines(path) + check_ast(path)
        except SyntaxError as exc:
            problems = [f"语法错误：{exc}"]
        if problems:
            failures += 1
            print(f"✗ {rel}")
            for p in problems:
                print(f"    {p}")
    print()
    if failures:
        print(f"✗ {failures}/{len(files)} 个文件不达标")
        return 1
    print(f"✅ 规范检查通过（{len(files)} 个文件，行宽 ≤ {MAX_WIDTH}，"
          f"返回类型与 docstring 齐全，无未使用 import）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
