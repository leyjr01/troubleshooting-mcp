"""Explicit local release operations; never publishes or changes a cluster."""

import argparse
import asyncio
import hashlib
import importlib.metadata as metadata
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    subprocess.run(args, check=True, cwd=ROOT, **kwargs)


async def catalog():
    from fastmcp import Client

    from agt_mcp.configuration.loader import load_configuration
    from agt_mcp.configuration.models import Configuration
    from agt_mcp.core.execution import TOOL_DEFINITIONS, ToolName
    from agt_mcp.mcp.bootstrap import build_runtime
    from agt_mcp.mcp.server import create_server

    data = load_configuration([ROOT / "config/server/local.example.yaml"], environ={}).model_dump()
    data["mcp"]["server"]["enabled_tools"] = list(ToolName)
    definitions = {d.name.value: d for d in TOOL_DEFINITIONS}
    async with Client(create_server(build_runtime(Configuration.model_validate(data)))) as client:
        tools = await client.list_tools()
    lines = [
        "# v1.0 MCP tool catalog",
        "",
        "Generated with `python scripts/release.py catalog` from registered tools/permissions.",
        "All tools: stable v1 input/output contract, read-only source access. Availability still",
        "requires enabled tools, scope and backend capabilities; schemas do not grant access.",
        "Output: ToolResponse (ok, request_id, correlation_id, environment_id, data, error).",
        "Nested query inputs use the published MCP JSON Schema; clients should call list_tools.",
        "Inventory is bounded/non-atomic; topology structural; diagnosis evidence-based.",
        "Knowledge is untrusted; logs/traces use fixtures; metrics use configured Prometheus.",
        "Probes are opt-in active observations, externally observable and non-idempotent.",
        "No source writes or executed recommendations; derived in-memory caches may change.",
        "",
        "| Tool | Purpose | Inputs (* required) | Permissions / capabilities | Limitations |",
        "|---|---|---|---|---|",
    ]
    for tool in sorted(tools, key=lambda t: t.name):
        d = definitions[tool.name]
        required = tool.input_schema.get("required", [])
        inputs = ", ".join(
            key + ("*" if key in required else "")
            for key in tool.input_schema.get("properties", {})
        )
        permissions = ", ".join(sorted(p.value for p in d.required_permissions))
        limits = "Configured source, scope and bounded result; no causal confirmation"
        if tool.name == "execute_probe_plan":
            limits = "Approved cached plan only; disabled by default; active network effects"
        lines.append(f"| `{tool.name}` | {d.description} | {inputs} | {permissions} | {limits} |")
    (ROOT / "docs/release/tool-catalog.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def inventory():
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    pending = [("api-gateway-troubleshooting-mcp", frozenset())]
    visited = set()
    found = {}
    while pending:
        raw_name, extras = pending.pop()
        name = canonicalize_name(raw_name)
        key = (name, extras)
        if key in visited:
            continue
        visited.add(key)
        dist = metadata.distribution(name)
        license_name = dist.metadata.get("License-Expression") or dist.metadata.get(
            "License", "UNKNOWN"
        )
        found[name] = {
            "name": dist.metadata["Name"],
            "version": dist.version,
            "license": license_name.splitlines()[0] if license_name else "UNKNOWN",
        }
        for text in dist.requires or ():
            req = Requirement(text)
            if req.marker is None or any(
                req.marker.evaluate({"extra": extra}) for extra in ("", *sorted(extras))
            ):
                pending.append((req.name, frozenset(req.extras)))
    output = {
        "scope": "Installed runtime closure; not a vulnerability scan or legal opinion",
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "dependencies": [found[k] for k in sorted(found)],
    }
    (ROOT / "docs/release/dependency-inventory.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )


def build():
    from setuptools.build_meta import build_sdist, build_wheel

    os.chdir(ROOT)
    os.environ.setdefault("SOURCE_DATE_EPOCH", "315532800")
    target = ROOT / "dist"
    target.mkdir(exist_ok=True)
    artifacts = [build_sdist(str(target)), build_wheel(str(target))]
    (target / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256((target / p).read_bytes()).hexdigest()}  {p}\n" for p in artifacts
        ),
        encoding="utf-8",
    )


def clean_install():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    wheel = ROOT / "dist" / f"api_gateway_troubleshooting_mcp-{version}-py3-none-any.whl"
    if not wheel.is_file():
        raise SystemExit("Build the wheel first")
    with tempfile.TemporaryDirectory(prefix="agt-release-") as temp:
        venv.EnvBuilder(with_pip=True).create(temp)
        python = Path(temp) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        run(
            str(python),
            "-m",
            "pip",
            "install",
            "--constraint",
            str(ROOT / "requirements.lock"),
            str(wheel),
        )
        run(
            str(python),
            str(ROOT / "scripts/smoke_installed.py"),
            str(ROOT / "config/server/local.example.yaml"),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["catalog", "inventory", "build", "clean-install", "checkpoint"]
    )
    action = parser.parse_args().action
    if action == "catalog":
        asyncio.run(catalog())
    elif action == "inventory":
        inventory()
    elif action == "build":
        build()
    elif action == "clean-install":
        clean_install()
    else:
        run(
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "release",
            "--scenario-acceptance",
            "-q",
            "--tb=short",
        )


if __name__ == "__main__":
    main()
