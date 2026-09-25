# Installation and quickstart — v1.0.0

Use Python 3.12. Windows PowerShell: `python -m venv .venv`, then use
`.venv/Scripts/python.exe` in place of `python`. Linux: `.venv/bin/python`.

For an approved built release wheel (substitute its actual path):

```sh
python -m pip install --constraint requirements.lock dist/api_gateway_troubleshooting_mcp-1.0.0-py3-none-any.whl
python -m agt_mcp validate-config --file config/server/local.example.yaml
python -m agt_mcp serve --file config/server/local.example.yaml
```

The source distribution includes config/docs/deployment artifacts; the runtime
wheel includes only package code/metadata. Keep reviewed configuration separately.
The local example is the single minimal working configuration: synthetic adapters,
no real network or credentials. Do not confuse it with live discovery.

Connect a Python MCP client using the installed FastMCP runtime:

```python
import asyncio
import sys
from fastmcp import Client


async def main():
    async with Client(
        {
            "mcpServers": {
                "agt": {
                    "command": sys.executable,
                    "args": [
                        "-m",
                        "agt_mcp",
                        "serve",
                        "--file",
                        "config/server/local.example.yaml",
                    ],
                }
            }
        }
    ) as client:
        for name, arguments in (
            ("system_health", {}),
            ("list_environments", {}),
            ("discover_gateway", {"gateway_id": "gateway-01"}),
        ):
            print((await client.call_tool(name, arguments)).structured_content)


asyncio.run(main())
```

For real `discover_environment`, configure the existing
`config/server/kubernetes.example.yaml` with your exact kubeconfig context,
namespace and reader identity, enable that tool and runtime.discover permission,
then call `discover_environment` with `{"query": {}}`. This is an explicit network
operation and is not part of the synthetic quickstart. In-cluster use the
[Kubernetes guide](../deployment/kubernetes.md); for Route/SCC/APIManager see
[OpenShift](../deployment/openshift.md). Neither guide installs 3scale.

HTTP defaults to loopback `/mcp`; remote clients need configured bearer auth,
trusted TLS termination, exact Host and network policy. See [operations](../operations/runbook.md).
No doctor command exists; use validate-config, system_health and scoped discovery.
