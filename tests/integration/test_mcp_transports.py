"""Real process/loopback smoke tests using the documented module entrypoint."""

import asyncio
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parents[2]
ARGS = ["-m", "agt_mcp", "serve", "--file", "config/server/local.example.yaml"]


def test_stdio_entrypoint(tmp_path):
    log = tmp_path / "stdio.log"

    async def scenario():
        transport = StdioTransport(
            command=sys.executable, args=ARGS, cwd=str(ROOT), keep_alive=False, log_file=log
        )
        async with Client(transport, timeout=10) as client:
            assert len(await client.list_tools()) == 7
            response = await client.call_tool("discover_gateway", {"gateway_id": "gateway-01"})
            assert response.structured_content["ok"]
            invalid = await client.call_tool(
                "system_health", {"principal": "synthetic-leak"}, raise_on_error=False
            )
            assert invalid.is_error

    asyncio.run(scenario())
    text = log.read_text(encoding="utf-8")
    assert "synthetic-leak" not in text
    assert "tool_finished" in text


@pytest.mark.local_transport
def test_http_entrypoint(tmp_path):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    log = tmp_path / "http.log"
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, *ARGS, "--transport", "http", "--port", str(port)],
            cwd=ROOT,
            stdout=output,
            stderr=output,
        )

        async def scenario():
            for _ in range(150):
                if process.poll() is not None:
                    pytest.fail("HTTP process exited before readiness")
                try:
                    reader, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    await asyncio.sleep(0.1)
            else:
                pytest.fail("HTTP server did not become ready")
            async with Client(f"http://127.0.0.1:{port}/mcp", timeout=10) as client:
                assert len(await client.list_tools()) == 7
                response = await client.call_tool("system_health", {})
                assert response.structured_content["ok"]
                assert response.structured_content["data"]["status"] == "healthy"
            # Exercise browser-origin protection without an HTTP client dependency.
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(
                (
                    f"POST /mcp HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                    "Origin: https://untrusted.invalid\r\nContent-Length: 0\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
            )
            await writer.drain()
            status = await reader.readline()
            writer.close()
            await writer.wait_closed()
            assert b"403" in status, status

        try:
            asyncio.run(asyncio.wait_for(scenario(), timeout=30))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    assert "tool_finished" in log.read_text(encoding="utf-8")


def test_server_startup_failure_uses_stderr():
    result = subprocess.run(
        [sys.executable, "-m", "agt_mcp", "serve"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "FAIL: configuration" in result.stderr
