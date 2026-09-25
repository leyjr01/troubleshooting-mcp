import asyncio
import socket
from pathlib import Path
from unittest.mock import AsyncMock

import httpx2 as httpx
import pytest
import uvicorn
import yaml
from fastmcp import Client

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.errors import DataSourceUnavailable
from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.server import create_server
from tests.integration.test_mcp_server import config
from tests.unit.test_deployment_readiness import remote


@pytest.mark.local_transport
def test_authenticated_http_health_acl_and_graceful_shutdown(monkeypatch, caplog):
    token = "http-test-credential-" + "x" * 32
    monkeypatch.setenv("AGT_HTTP_TOKEN", token)
    data = config().model_dump()
    settings = data["mcp"]["server"]
    settings.update(remote(authorization=settings["authorization"]))
    runtime = build_runtime(Configuration.model_validate(data))
    runtime.discovery.close = AsyncMock(wraps=runtime.discovery.close)
    server = create_server(runtime)
    app = server.http_app(
        path="/mcp", host_origin_protection=True, allowed_hosts=["127.0.0.1"], allowed_origins=[]
    )

    async def run():
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            http_server = uvicorn.Server(
                uvicorn.Config(app, log_config=None, access_log=False, timeout_graceful_shutdown=2)
            )
            task = asyncio.create_task(http_server.serve(sockets=[listener]))
            try:
                for _ in range(100):
                    if http_server.started:
                        break
                    if task.done():
                        await task
                    await asyncio.sleep(0.01)
                assert http_server.started and runtime.ready
                url = f"http://127.0.0.1:{port}"
                async with httpx.AsyncClient(trust_env=False) as http:
                    assert (await http.get(url + "/livez")).json() == {"status": "alive"}
                    assert (await http.get(url + "/readyz")).json() == {"status": "healthy"}
                    runtime.ready = False
                    assert (await http.get(url + "/readyz")).status_code == 503
                    assert (await http.get(url + "/livez")).status_code == 200
                    runtime.ready = True
                    assert (await http.post(url + "/mcp")).status_code == 401
                    assert (
                        await http.post(url + "/mcp", headers={"Authorization": "Bearer wrong"})
                    ).status_code == 401
                    assert (
                        await http.post(
                            url + "/mcp",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Origin": "https://untrusted.invalid",
                            },
                        )
                    ).status_code == 403
                async with Client(url + "/mcp", auth=token) as client:
                    assert await client.list_tools()
                    assert (await client.call_tool("system_health", {})).structured_content["data"][
                        "status"
                    ] == "healthy"
                    assert (await client.call_tool("list_capabilities", {})).structured_content[
                        "ok"
                    ]
                    denied = (
                        await client.call_tool(
                            "system_health",
                            {"environment_id": "other", "correlation_id": "token=" + token},
                        )
                    ).structured_content
                    assert not denied["ok"] and denied["error"] == "authorization"
            finally:
                http_server.should_exit = True
                await asyncio.wait_for(task, 5)
            assert not runtime.ready
            runtime.discovery.close.assert_awaited_once()

    asyncio.run(run())
    assert token not in caplog.text


def test_unavailable_cluster_does_not_break_health(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    document = yaml.safe_load((root / "deploy/base/configmap.yaml").read_text())
    data = yaml.safe_load(document["data"]["config.yaml"])
    data["mcp"]["server"]["http_token"].update(provider="environment", reference="AGT_HTTP_TOKEN")
    monkeypatch.setenv("AGT_HTTP_TOKEN", "unavailable-cluster-test-" + "x" * 32)
    runtime = build_runtime(Configuration.model_validate(data))
    client = runtime.discovery.adapters["cluster"].client
    client.open = AsyncMock(side_effect=DataSourceUnavailable())

    async def run():
        async with Client(create_server(runtime)) as mcp:
            client.open.assert_not_awaited()
            failure = (
                await mcp.call_tool("discover_environment", {"query": {}})
            ).structured_content
            assert not failure["ok"]
            healthy = (await mcp.call_tool("system_health", {})).structured_content
            assert healthy["ok"] and healthy["data"]["status"] == "healthy"
            assert runtime.ready
        assert not runtime.ready

    asyncio.run(run())
