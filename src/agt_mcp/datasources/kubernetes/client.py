"""Official asynchronous Kubernetes SDK boundary. Raw dictionaries stay in this package."""

import asyncio
import builtins
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from typing import Any, Protocol
from urllib.parse import urlsplit

from kubernetes.aio import client as sdk
from kubernetes.aio import config as sdk_config
from kubernetes.aio.client.exceptions import ApiException

from agt_mcp.configuration.loader import read_yaml
from agt_mcp.configuration.runtime import RuntimeEnvironment
from agt_mcp.core.errors import (
    AGTError,
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    DataSourceUnavailable,
    ResourceNotFound,
    SanitizationError,
    TimeoutError,
)
from agt_mcp.core.execution import ExecutionContext
from agt_mcp.datasources.kubernetes.catalog import ResourceType


class RuntimeClient(Protocol):
    async def open(self) -> str: ...
    async def api_resources(
        self, api_version: str, context: ExecutionContext
    ) -> dict[str, Any]: ...
    async def list_resources(
        self,
        resource: ResourceType,
        namespace: str | None,
        limit: int,
        continuation: str | None,
        context: ExecutionContext,
        field_selector: str | None = None,
    ) -> dict[str, Any]: ...
    async def read_resource(
        self, resource: ResourceType, namespace: str | None, name: str, context: ExecutionContext
    ) -> dict[str, Any]: ...
    async def close(self) -> None: ...


def status_error(status: int) -> AGTError:
    if status == 401:
        return AuthenticationError()
    if status == 403:
        return AuthorizationError()
    if status == 404:
        return ResourceNotFound()
    if status in {408, 504}:
        return TimeoutError()
    return DataSourceUnavailable()


class KubernetesClient:
    def __init__(self, environment: RuntimeEnvironment) -> None:
        if environment.runtime is None:
            raise ConfigurationError()
        self.environment = environment
        self.settings = environment.runtime
        self.api: Any = None
        self._temp: TemporaryDirectory[str] | None = None
        self.namespace = environment.namespace or "default"

    async def open(self) -> str:
        if self.api is not None:
            return self.namespace
        configuration = sdk.Configuration()
        try:
            async with asyncio.timeout(self.settings.timeout_seconds):
                if self.settings.authentication.mode == "in-cluster":
                    sdk_config.load_incluster_config(client_configuration=configuration)
                else:
                    await self._kubeconfig(configuration)
                address = urlsplit(configuration.host)
                if (
                    address.scheme != "https"
                    or address.username
                    or address.password
                    or not configuration.verify_ssl
                ):
                    raise ConfigurationError()
                configuration.debug = False
                self.api = sdk.ApiClient(configuration=configuration)
            return self.namespace
        except builtins.TimeoutError:
            await self.close()
            raise TimeoutError() from None
        except AGTError:
            await self.close()
            raise
        except Exception:
            await self.close()
            raise AuthenticationError() from None

    async def _kubeconfig(self, configuration: Any) -> None:
        auth = self.settings.authentication
        path = Path(auth.kubeconfig).expanduser().resolve()
        document = read_yaml(path)
        active = auth.context or document.get("current-context")
        contexts = [
            item["context"] for item in document.get("contexts", []) if item.get("name") == active
        ]
        if len(contexts) != 1 or contexts[0].get("cluster") != (
            auth.cluster or self.environment.cluster
        ):
            raise AuthenticationError()
        binding = contexts[0]
        users = [
            item.get("user", {})
            for item in document.get("users", [])
            if item.get("name") == binding.get("user")
        ]
        if len(users) != 1 or "exec" in users[0] or "auth-provider" in users[0]:
            raise AuthenticationError()
        # Resolve file references against this kubeconfig, never change global SDK defaults.
        for item in document.get("clusters", []):
            cluster = item.get("cluster", {})
            if cluster.get("certificate-authority"):
                cluster["certificate-authority"] = str(
                    path.parent / cluster["certificate-authority"]
                )
        for field in ("client-certificate", "client-key"):
            if users[0].get(field):
                users[0][field] = str(path.parent / users[0][field])
        self._temp = TemporaryDirectory(prefix="agt-kube-")
        await sdk_config.load_kube_config_from_dict(
            document,
            context=active,
            client_configuration=configuration,
            temp_file_path=self._temp.name,
        )
        self.namespace = self.environment.namespace or binding.get("namespace") or "default"

    async def _call(
        self, operation: Any, context: ExecutionContext, **kwargs: Any
    ) -> dict[str, Any]:
        if context.environment_id != self.environment.id:
            raise AuthorizationError()
        timeout = min(self.settings.timeout_seconds, context.deadline - monotonic())
        if timeout <= 0:
            raise TimeoutError()
        response: Any = None
        try:
            async with asyncio.timeout(timeout):
                response = await operation(
                    _preload_content=False, _request_timeout=timeout, **kwargs
                )
                if not 200 <= response.status < 300:
                    raise status_error(response.status)
                maximum = self.settings.discovery.limits.max_response_bytes
                raw = bytearray()
                while len(raw) <= maximum:
                    chunk = await response.content.read(min(65536, maximum + 1 - len(raw)))
                    if not chunk:
                        break
                    raw.extend(chunk)
                if len(raw) > maximum:
                    raise SanitizationError()
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise SanitizationError()
                return result
        except builtins.TimeoutError:
            raise TimeoutError() from None
        except ApiException as exc:
            raise status_error(exc.status or 0) from None
        except AGTError:
            raise
        except Exception:
            raise DataSourceUnavailable() from None
        finally:
            if response is not None:
                response.close()

    async def api_resources(self, api_version: str, context: ExecutionContext) -> dict[str, Any]:
        # SDK API discovery only; paths are built from the adapter's validated catalog.
        path = "/api/v1" if api_version == "v1" else "/apis/{group}/{version}"
        parameters = (
            {}
            if api_version == "v1"
            else dict(zip(("group", "version"), api_version.split("/"), strict=True))
        )
        return await self._call(
            self.api.call_api,
            context,
            resource_path=path,
            method="GET",
            path_params=parameters,
            auth_settings=["BearerToken"],
            header_params={"Accept": "application/json"},
        )

    def _operation(self, resource: ResourceType, verb: str) -> Any:
        instance = getattr(sdk, resource.api_class)(self.api)
        scope = "namespaced_" if resource.namespaced else ""
        if resource.api_class == "CustomObjectsApi":
            return getattr(
                instance,
                f"{verb}_{'namespaced' if resource.namespaced else 'cluster'}_custom_object",
            )
        return getattr(instance, f"{verb}_{scope}{resource.method_suffix}")

    def _arguments(self, resource: ResourceType, namespace: str | None) -> dict[str, Any]:
        args: dict[str, Any] = {"namespace": namespace} if resource.namespaced else {}
        if resource.api_class == "CustomObjectsApi":
            args.update(
                group=resource.api_version.split("/")[0],
                version=resource.api_version.split("/")[1],
                plural=resource.plural,
            )
        return args

    async def list_resources(
        self,
        resource: ResourceType,
        namespace: str | None,
        limit: int,
        continuation: str | None,
        context: ExecutionContext,
        field_selector: str | None = None,
    ) -> dict[str, Any]:
        args = self._arguments(resource, namespace)
        args.update(limit=limit)
        if continuation:
            args["_continue"] = continuation
        if field_selector:
            args["field_selector"] = field_selector
        return await self._call(self._operation(resource, "list"), context, **args)

    async def read_resource(
        self, resource: ResourceType, namespace: str | None, name: str, context: ExecutionContext
    ) -> dict[str, Any]:
        verb = "get" if resource.api_class == "CustomObjectsApi" else "read"
        args = self._arguments(resource, namespace)
        return await self._call(self._operation(resource, verb), context, name=name, **args)

    async def close(self) -> None:
        if self.api is not None:
            await self.api.close()
            self.api = None
        if self._temp is not None:
            self._temp.cleanup()
            self._temp = None
