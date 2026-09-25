"""Opt-in Docker build/HTTP/health/shutdown smoke; never installs Docker."""

import asyncio
import os
import secrets
import shutil
import subprocess
import time
from pathlib import Path

import httpx2
import pytest
import yaml
from fastmcp import Client

pytestmark = pytest.mark.real_lab
ROOT = Path(__file__).resolve().parents[2]


def test_container_http_and_sigterm(tmp_path):
    docker = shutil.which("docker")
    image = os.environ.get("AGT_PYTHON_IMAGE", "")
    if not docker:
        pytest.skip("Docker absent; container smoke NOT EXECUTED")
    if "@sha256:" not in image:
        pytest.skip("AGT_PYTHON_IMAGE with approved digest required")

    def run(*args, **kwargs):
        return subprocess.run(
            [docker, *args], check=True, capture_output=True, text=True, timeout=600, **kwargs
        )

    token = secrets.token_urlsafe(32)
    name = "agt-smoke-" + secrets.token_hex(5)
    configuration = yaml.safe_load((ROOT / "config/server/local.example.yaml").read_text())
    configuration["mcp"]["server"].update(
        transport="http",
        host="0.0.0.0",
        http_token={
            "provider": "environment",
            "reference": "AGT_HTTP_TOKEN",
            "environment_id": "demo",
        },
    )
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(configuration), encoding="utf-8")
    path.chmod(0o644)
    run("build", "--build-arg", f"PYTHON_IMAGE={image}", "-t", name, ".", cwd=ROOT)
    try:
        run(
            "run",
            "-d",
            "--name",
            name,
            "--read-only",
            "--user",
            "12345:0",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--tmpfs",
            "/tmp:rw,nosuid,size=134217728",
            "-e",
            "AGT_HTTP_TOKEN",
            "-p",
            "127.0.0.1::8000",
            "-v",
            f"{path}:/etc/agt/config.yaml:ro",
            name,
            env={**os.environ, "AGT_HTTP_TOKEN": token},
        )
        port = run("port", name, "8000/tcp").stdout.strip().rsplit(":", 1)[1]

        async def smoke():
            for _ in range(100):
                try:
                    async with Client(
                        f"http://127.0.0.1:{port}/mcp", auth=token, timeout=5
                    ) as client:
                        assert await client.list_tools()
                        for tool in ("system_health", "list_capabilities"):
                            assert (await client.call_tool(tool, {})).structured_content["ok"]
                        return
                except (OSError, RuntimeError, httpx2.ConnectError):
                    await asyncio.sleep(0.2)
            pytest.fail("Container MCP startup timed out")

        asyncio.run(smoke())
        started = time.monotonic()
        run("stop", "--time", "40", name)
        assert time.monotonic() - started < 45
        assert run("inspect", "--format", "{{.State.ExitCode}}", name).stdout.strip() == "0"
        logs = run("logs", name)
        assert token not in logs.stdout + logs.stderr
    finally:
        subprocess.run([docker, "rm", "-f", name], capture_output=True, timeout=30)
        subprocess.run([docker, "image", "rm", name], capture_output=True, timeout=30)
