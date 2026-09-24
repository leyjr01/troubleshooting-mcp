import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "package",
    [
        "core",
        "observability",
        "correlation",
        "troubleshooting",
        "trace",
        "probes",
        "gateways/threescale",
    ],
)
def test_provider_implementation_stays_outside_neutral_and_semantic_packages(package):
    for path in (ROOT / "src/agt_mcp" / package).glob("*.py"):
        imports = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(
            name.startswith(
                ("fastmcp", "kubernetes", "httpx", "requests", "agt_mcp.datasources.prometheus")
            )
            for name in imports
        ), path
