"""Offline smoke executed by the isolated installed-wheel interpreter."""

import asyncio
import sys
from importlib.metadata import version
from pathlib import Path

from fastmcp import Client

from agt_mcp import __version__
from agt_mcp.configuration.loader import load_configuration
from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.server import create_server


async def main():
    config = load_configuration([Path(sys.argv[1])], environ={})
    async with Client(create_server(build_runtime(config))) as client:
        result = await client.call_tool("system_health", {})
        assert result.structured_content["ok"]
        assert (
            result.structured_content["data"]["version"]
            == __version__
            == version("api-gateway-troubleshooting-mcp")
        )
        assert result.structured_content["data"]["status"] == "healthy"
    print(f"Installed wheel system_health PASS: {__version__}")


if __name__ == "__main__":
    asyncio.run(main())
