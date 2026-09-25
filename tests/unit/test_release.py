import asyncio
import json
import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest
import yaml
from fastmcp import Client
from pydantic import ValidationError

from agt_mcp import __version__
from agt_mcp.configuration.loader import load_configuration
from agt_mcp.configuration.models import Configuration
from agt_mcp.core.execution import TOOL_DEFINITIONS, ToolName
from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.server import create_server

ROOT = Path(__file__).resolve().parents[2]


def config():
    return load_configuration([ROOT / "config/server/local.example.yaml"], environ={})


def test_release_version_and_global_registered_read_only_contract():
    target = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert target == __version__ == version("api-gateway-troubleshooting-mcp") == "1.0.0"
    data = config().model_dump()
    data["mcp"]["server"]["enabled_tools"] = list(ToolName)

    async def run():
        async with Client(
            create_server(build_runtime(Configuration.model_validate(data)))
        ) as client:
            tools = await client.list_tools()
            assert {t.name for t in tools} == {d.name for d in TOOL_DEFINITIONS} == set(ToolName)
            assert len(tools) == 38
            assert all(t.annotations.read_only_hint for t in tools)
            assert all(not t.annotations.destructive_hint for t in tools)
            assert all(d.read_only for d in TOOL_DEFINITIONS)
            response = (await client.call_tool("system_health", {})).structured_content
            assert response["ok"] and response["data"]["version"] == target
            assert set(response["data"]) == {
                "server",
                "version",
                "status",
                "uptime_seconds",
                "configured_environment",
                "registered_gateways",
                "registered_datasources",
            }
            catalog = (ROOT / "docs/release/tool-catalog.md").read_text(encoding="utf-8")
            assert all(f"`{t.name}`" in catalog for t in tools)

    asyncio.run(run())


@pytest.mark.parametrize("collection", ["environments", "datasources", "gateways"])
def test_duplicate_configuration_identity_fails_early(collection):
    data = config().model_dump()
    data[collection] = [data[collection][0], data[collection][0]]
    with pytest.raises(ValidationError, match="duplicate"):
        Configuration.model_validate(data)


@pytest.mark.parametrize("path", [(), ("application",), ("mcp", "server")])
def test_unknown_configuration_field_is_never_silently_ignored(path):
    data = config().model_dump()
    node = data
    for key in path:
        node = node[key]
    node["unexpected_release_option"] = "not-a-real-secret"
    with pytest.raises(ValidationError) as exc:
        Configuration.model_validate(data)
    assert "not-a-real-secret" not in str(exc.value)


def test_all_rbac_manifests_remain_read_only():
    roles = 0
    for base in (ROOT / "deploy", ROOT / "config"):
        for path in base.rglob("*.yaml"):
            for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")):
                if not isinstance(doc, dict) or doc.get("kind") not in {"Role", "ClusterRole"}:
                    continue
                roles += 1
                for rule in doc["rules"]:
                    assert set(rule["verbs"]) <= {"get", "list"}, path
                    assert "secrets" not in rule.get("resources", []), path
                    assert "*" not in json.dumps(rule), path
    assert roles >= 2


def test_release_documents_match_target_and_no_unqualified_claim():
    notes = (ROOT / "docs/release/v1.0.0.md").read_text(encoding="utf-8")
    assert "READY WITH LIMITATIONS" in notes
    assert "NOT QUALIFIED" in notes
    for name in (
        "CHANGELOG.md",
        "SECURITY.md",
        "docs/installation/README.md",
        "docs/operations/runbook.md",
        "docs/release/compatibility.md",
    ):
        assert (ROOT / name).is_file()
