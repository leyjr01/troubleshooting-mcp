"""Offline structural checks complement the manual architecture/security review."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = [
    *ROOT.glob("*.md"),
    *ROOT.glob("docs/**/*.md"),
    *ROOT.glob("knowledge/**/*.md"),
    *ROOT.glob("mappings/**/*.md"),
    *ROOT.glob("tests/scenarios/**/*.md"),
    *ROOT.glob("scripts/**/*.md"),
]


def test_local_documentation_links():
    checked = 0
    for path in DOCS:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if target.startswith(("https://", "http://", "#")):
                continue
            assert (path.parent / target.split("#")[0]).exists(), (path, target)
            checked += 1
    assert checked >= 10


def test_adr_completeness():
    adrs = sorted((ROOT / "docs/adr").glob("[0-9]*.md"))
    assert len(adrs) == 13
    for index, path in enumerate(adrs, 1):
        assert path.name.startswith(f"{index:04d}-")
        text = path.read_text(encoding="utf-8")
        for section in ("Status", "Context", "Decision", "Consequences", "Alternatives Considered"):
            assert f"## {section}" in text


def test_catalog_and_scenarios():
    catalog = (ROOT / "docs/architecture/mcp-tools.md").read_text(encoding="utf-8")
    tools = catalog.split("\n## ")[1:]
    assert len(tools) == 24
    for tool in tools:
        for field in (
            "Purpose:",
            "Inputs:",
            "Outputs:",
            "Permissions:",
            "Side effects:",
            "Security considerations:",
        ):
            assert field in tool
    scenarios = sorted((ROOT / "tests/scenarios").glob("[0-9]*/README.md"))
    assert len(scenarios) == 12
    for scenario in scenarios:
        text = scenario.read_text(encoding="utf-8").lower()
        for field in (
            "symptom",
            "topology",
            "input evidence",
            "expected findings",
            "root cause",
            "expected rejected hypotheses",
            "expected recommendation",
        ):
            assert field in text


def test_core_dependency_direction():
    forbidden = (
        "agt_mcp.gateways",
        "agt_mcp.datasources",
        "agt_mcp.configuration",
        "agt_mcp.mcp",
        "agt_mcp.rag",
        "kubernetes",
        "fastmcp",
        "requests",
        "httpx",
    )
    for path in (ROOT / "src/agt_mcp/core").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(name.startswith(forbidden) for name in imports), path
