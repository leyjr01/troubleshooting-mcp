import asyncio
import copy
import io
import json
from unittest.mock import AsyncMock, Mock

import pytest
import yaml
from kubernetes.aio.client.exceptions import ApiException

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    DataSourceUnavailable,
    ResourceNotFound,
    SanitizationError,
    TimeoutError,
)
from agt_mcp.core.execution import ToolName
from agt_mcp.datasources.kubernetes import client as module
from agt_mcp.datasources.kubernetes.catalog import ROUTE, TYPES
from agt_mcp.mcp.context import create_context
from tests.runtime_support import runtime_configuration


def setup_client(**overrides):
    config = runtime_configuration(**overrides)
    return module.KubernetesClient(config.environments[0]), create_context(
        config, ToolName.DISCOVER_ENVIRONMENT, "dev", None
    )


def response(data=None, status=200, raw=None):
    stream = io.BytesIO(raw if raw is not None else json.dumps(data or {}).encode())
    return Mock(status=status, content=Mock(read=AsyncMock(side_effect=stream.read)), close=Mock())


@pytest.mark.parametrize(
    "status,error",
    [
        (401, AuthenticationError),
        (403, AuthorizationError),
        (404, ResourceNotFound),
        (408, TimeoutError),
        (504, TimeoutError),
        (500, DataSourceUnavailable),
    ],
)
@pytest.mark.parametrize("sdk_exception", [False, True])
def test_http_errors_are_safe_and_do_not_read_bodies(status, error, sdk_exception):
    client, context = setup_client()
    reply = response(raw=b"Bearer PRIVATE-CREDENTIAL", status=status)
    operation = (
        AsyncMock(side_effect=ApiException(status=status, reason="PRIVATE-CREDENTIAL"))
        if sdk_exception
        else AsyncMock(return_value=reply)
    )
    with pytest.raises(error) as caught:
        asyncio.run(client._call(operation, context))
    assert "PRIVATE-CREDENTIAL" not in str(caught.value)
    reply.content.read.assert_not_called()
    if not sdk_exception:
        reply.close.assert_called_once()


@pytest.mark.parametrize(
    "raw,error",
    [
        (b"[]", SanitizationError),
        (b"invalid-json", DataSourceUnavailable),
        (b"x" * 1048577, SanitizationError),
    ],
    ids=["array", "invalid", "oversize"],
)
def test_stream_projection_limits(raw, error):
    client, context = setup_client()
    reply = response(raw=raw)
    with pytest.raises(error):
        asyncio.run(client._call(AsyncMock(return_value=reply), context))
    reply.close.assert_called_once()


def test_call_timeout_and_environment_boundary():
    client, context = setup_client()
    operation = AsyncMock(side_effect=asyncio.TimeoutError)
    with pytest.raises(TimeoutError):
        asyncio.run(client._call(operation, context))
    with pytest.raises(AuthorizationError):
        asyncio.run(client._call(operation, context.model_copy(update={"environment_id": "other"})))
    with pytest.raises(TimeoutError):
        asyncio.run(client._call(operation, context.model_copy(update={"deadline": 0})))
    assert operation.await_count == 1


@pytest.mark.parametrize("resource", [*TYPES, ROUTE], ids=lambda r: r.kind)
def test_real_sdk_generated_read_and_list_paths(resource):
    client, context = setup_client()
    client.api = Mock(call_api=AsyncMock(side_effect=lambda *a, **k: response({"items": []})))
    namespace = "example" if resource.namespaced else None

    async def run():
        assert await client.list_resources(
            resource, namespace, 7, "cursor-1", context, "metadata.name=app"
        ) == {"items": []}
        await client.read_resource(resource, namespace, "app", context)

    asyncio.run(run())
    calls = client.api.call_api.call_args_list
    assert len(calls) == 2
    assert all(c.args[1] == "GET" for c in calls)
    assert all("secrets" not in c.args[0] for c in calls)
    assert all(c.kwargs["_preload_content"] is False for c in calls)
    query = dict(
        calls[0].kwargs.get("query_params", calls[0].args[3] if len(calls[0].args) > 3 else [])
    )
    assert query["limit"] == 7 and query["continue"] == "cursor-1"


@pytest.mark.parametrize(
    "version,path", [("v1", "/api/v1"), ("apps/v1", "/apis/{group}/{version}")]
)
def test_api_discovery(version, path):
    client, context = setup_client()
    client.api = Mock(call_api=AsyncMock(return_value=response({"resources": []})))
    assert asyncio.run(client.api_resources(version, context)) == {"resources": []}
    assert client.api.call_api.call_args.kwargs["resource_path"] == path


def kube_document():
    return {
        "apiVersion": "v1",
        "kind": "Config",
        "current-context": "dev",
        "contexts": [
            {
                "name": "dev",
                "context": {"cluster": "dev-cluster", "user": "reader", "namespace": "example"},
            }
        ],
        "clusters": [
            {
                "name": "dev-cluster",
                "cluster": {"server": "https://cluster.invalid", "certificate-authority": "ca.crt"},
            }
        ],
        "users": [
            {
                "name": "reader",
                "user": {
                    "token": "SYNTHETIC-TOKEN",
                    "client-certificate": "client.crt",
                    "client-key": "client.key",
                },
            }
        ],
    }


def test_kubeconfig_is_per_instance_and_never_persisted(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(kube_document()))
    before = path.read_bytes()
    client, _ = setup_client(authentication={"kubeconfig": str(path), "context": "dev"})
    loaded = []

    async def load(document, **kwargs):
        loaded.append((document, kwargs))
        kwargs["client_configuration"].host = "https://cluster.invalid"

    monkeypatch.setattr(module.sdk_config, "load_kube_config_from_dict", load)
    api = Mock(close=AsyncMock())
    factory = Mock(return_value=api)
    monkeypatch.setattr(module.sdk, "ApiClient", factory)

    async def run():
        assert await client.open() == "example"
        assert await client.open() == "example"
        await client.close()
        await client.close()

    asyncio.run(run())
    assert len(loaded) == 1 and path.read_bytes() == before
    assert loaded[0][0]["users"][0]["user"]["client-key"] == str(tmp_path / "client.key")
    assert loaded[0][0]["clusters"][0]["cluster"]["certificate-authority"] == str(
        tmp_path / "ca.crt"
    )
    assert "persist_config" not in loaded[0][1]
    assert factory.call_args.kwargs["configuration"].debug is False
    api.close.assert_awaited_once()
    assert client._temp is None


@pytest.mark.parametrize("mutation", ["cluster", "context", "user", "exec", "auth-provider"])
def test_kubeconfig_rejects_misbinding_and_credential_execution(tmp_path, mutation):
    document = copy.deepcopy(kube_document())
    if mutation == "cluster":
        document["contexts"][0]["context"]["cluster"] = "other"
    elif mutation == "context":
        document["contexts"] = []
    elif mutation == "user":
        document["users"] = []
    else:
        document["users"][0]["user"][mutation] = {"command": "never-run"}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(document))
    client, _ = setup_client(authentication={"kubeconfig": str(path), "context": "dev"})
    with pytest.raises(AuthenticationError):
        asyncio.run(client.open())


@pytest.mark.parametrize(
    "host,verify,error",
    [
        ("https://cluster.invalid", True, None),
        ("http://cluster.invalid", True, ConfigurationError),
        ("https://user:password@cluster.invalid", True, ConfigurationError),
        ("https://cluster.invalid", False, ConfigurationError),
    ],
)
def test_incluster_tls_isolation(host, verify, error, monkeypatch):
    client, _ = setup_client(authentication={"mode": "in-cluster"})
    configurations = []

    def load(*, client_configuration):
        configurations.append(client_configuration)
        client_configuration.host = host
        client_configuration.verify_ssl = verify

    monkeypatch.setattr(module.sdk_config, "load_incluster_config", load)
    monkeypatch.setattr(module.sdk, "ApiClient", Mock(return_value=Mock(close=AsyncMock())))
    if error:
        with pytest.raises(error):
            asyncio.run(client.open())
    else:
        asyncio.run(client.open())
        asyncio.run(client.close())
    assert len(configurations) == 1


@pytest.mark.parametrize(
    "failure,error", [(asyncio.TimeoutError, TimeoutError), (ValueError, AuthenticationError)]
)
def test_auth_errors_are_sanitized(monkeypatch, failure, error):
    client, _ = setup_client()
    monkeypatch.setattr(client, "_kubeconfig", AsyncMock(side_effect=failure("PRIVATE-TOKEN")))
    with pytest.raises(error) as caught:
        asyncio.run(client.open())
    assert "PRIVATE-TOKEN" not in str(caught.value)


def test_missing_runtime_rejected():
    config = runtime_configuration().model_dump()
    config["environments"][0]["runtime"] = None
    with pytest.raises(ConfigurationError):
        module.KubernetesClient(Configuration.model_validate(config).environments[0])
