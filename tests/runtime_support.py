import copy
import json
from pathlib import Path

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.errors import ResourceNotFound
from agt_mcp.core.execution import Capability, ToolName
from agt_mcp.datasources.kubernetes.catalog import ROUTE, TYPES, ResourceType

FIXTURE = Path(__file__).parent / "fixtures/runtime-resources.json"


def runtime_configuration(**overrides):
    runtime = {
        "provider": "openshift",
        "authentication": {"mode": "kubeconfig", "context": "dev", "cluster": "dev-cluster"},
        "discovery": {
            "namespaces": {"include": ["example"]},
            "cluster_scoped": True,
            "custom_resources": [
                {"group": "example.io", "version": "v1", "plural": "widgets", "kind": "Widget"}
            ],
        },
    }
    runtime.update(overrides)
    return Configuration.model_validate(
        {
            "application": {"environment": "dev", "max_payload_bytes": 1048576},
            "environments": [
                {
                    "id": "dev",
                    "name": "Development",
                    "type": "development",
                    "cluster": "dev-cluster",
                    "namespace": "example",
                    "runtime": runtime,
                }
            ],
            "mcp": {
                "server": {
                    "enabled_tools": list(ToolName),
                    "authorization": {
                        "mode": "local-read-only",
                        "environment_ids": ["dev"],
                        "permissions": list(Capability),
                    },
                }
            },
        }
    )


class FakeKubernetesClient:
    def __init__(self, resources=None):
        self.resources = json.loads(FIXTURE.read_text()) if resources is None else resources
        self.calls = []
        self.forbidden = {}
        self.api_errors = {}
        self.opened = False
        self.closed = False
        self.types = (
            *TYPES,
            ROUTE,
            ResourceType("Widget", "example.io/v1", "widgets", "CustomObjectsApi"),
        )

    async def open(self):
        self.opened = True
        return "example"

    async def api_resources(self, version, context):
        self.calls.append(("discovery", version))
        if version in self.api_errors:
            raise self.api_errors[version]()
        return {
            "resources": [
                {"name": t.plural, "verbs": ["get", "list"], "namespaced": t.namespaced}
                for t in self.types
                if t.api_version == version
            ]
        }

    async def list_resources(
        self, resource, namespace, limit, continuation, context, field_selector=None
    ):
        assert resource.kind != "Secret"
        self.calls.append(("list", resource.kind, namespace, limit, continuation, field_selector))
        if resource.kind in self.forbidden:
            raise self.forbidden[resource.kind]()
        objects = [
            r
            for r in self.resources
            if r["kind"] == resource.kind and r["metadata"].get("namespace") == namespace
        ]
        if field_selector:
            uid = field_selector.partition("=")[2]
            objects = [r for r in objects if r.get("involvedObject", {}).get("uid") == uid]
        start = int(continuation or 0)
        return {
            "items": copy.deepcopy(objects[start : start + limit]),
            "metadata": {"continue": str(start + limit) if start + limit < len(objects) else ""},
        }

    async def read_resource(self, resource, namespace, name, context):
        assert resource.kind != "Secret"
        self.calls.append(("read", resource.kind, namespace, name))
        for item in self.resources:
            if (
                item["kind"] == resource.kind
                and item["metadata"].get("namespace") == namespace
                and item["metadata"]["name"] == name
            ):
                return copy.deepcopy(item)
        raise ResourceNotFound()

    async def close(self):
        self.closed = True
