import asyncio
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from agt_mcp.configuration.models import Configuration
from agt_mcp.configuration.server import ServerConfig
from agt_mcp.core.errors import AuthenticationError, AuthorizationError
from agt_mcp.credentials.providers import CredentialReference, MountedFileCredentialProvider
from agt_mcp.mcp.authentication import ConfiguredTokenVerifier

ROOT = Path(__file__).resolve().parents[2]


def remote(**changes):
    return {
        "transport": "http",
        "host": "0.0.0.0",
        "authorization": {"mode": "local-read-only", "environment_ids": ["demo"]},
        "http_token": {
            "provider": "environment",
            "reference": "AGT_HTTP_TOKEN",
            "environment_id": "demo",
        },
        **changes,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"http_token": None},
        {"transport": "stdio"},
        {"allowed_hosts": ["*"]},
        {"allowed_hosts": ["https://example.com"]},
        {"allowed_hosts": []},
        {"allowed_hosts": ["example.com:8000"]},
        {"http_token": {"provider": "vault", "reference": "TOKEN", "environment_id": "demo"}},
        {
            "http_token": {
                "provider": "environment",
                "reference": "TOKEN",
                "environment_id": "other",
            }
        },
    ],
)
def test_remote_configuration_fails_closed(changes):
    with pytest.raises(ValidationError):
        ServerConfig.model_validate(remote(**changes))


def test_local_default_and_explicit_authenticated_remote():
    assert ServerConfig().host == "127.0.0.1"
    assert ServerConfig.model_validate(remote()).host == "0.0.0.0"


@pytest.mark.parametrize("value", [None, "short", "x" * 4097, "é" * 32, "x" * 32 + " "])
def test_invalid_http_credential_is_not_accepted(monkeypatch, value):
    monkeypatch.delenv("AGT_HTTP_TOKEN", raising=False)
    if value is not None:
        monkeypatch.setenv("AGT_HTTP_TOKEN", value)
    verifier = ConfiguredTokenVerifier(ServerConfig.model_validate(remote()).http_token)
    with pytest.raises(AuthenticationError):
        asyncio.run(verifier.initialize())


def test_token_requires_initialization_and_constant_identity(monkeypatch):
    token = "unit-test-reader-credential-" + "x" * 32
    verifier = ConfiguredTokenVerifier(ServerConfig.model_validate(remote()).http_token)
    assert asyncio.run(verifier.verify_token(token)) is None
    monkeypatch.setenv("AGT_HTTP_TOKEN", token)
    asyncio.run(verifier.initialize())
    assert token not in repr(verifier.secret)
    assert asyncio.run(verifier.verify_token("wrong")) is None
    assert asyncio.run(verifier.verify_token(token)).client_id == "local-client"


@pytest.mark.parametrize(
    "case",
    ["valid", "missing", "empty", "large", "encoding", "scope", "path", "provider", "relative"],
)
def test_mounted_credentials_are_bounded_and_scoped(tmp_path, case):
    path = tmp_path / "token"
    path.write_bytes(b"x" * 32)
    if case == "empty":
        path.write_bytes(b"")
    if case == "large":
        path.write_bytes(b"x" * 4097)
    if case == "encoding":
        path.write_bytes(b"\xff")
    if case == "missing":
        path.unlink()
    reference = CredentialReference(
        provider="environment" if case == "provider" else "mounted-file",
        reference="file:relative" if case == "relative" else "file:" + path.as_posix(),
        environment_id="other" if case == "scope" else "demo",
    )
    provider = MountedFileCredentialProvider(
        "demo", frozenset() if case == "path" else frozenset({reference.reference})
    )
    if case == "valid":
        assert asyncio.run(provider.resolve(reference)).get_secret_value() == "x" * 32
        verifier = ConfiguredTokenVerifier(reference)
        asyncio.run(verifier.initialize())
        assert asyncio.run(verifier.verify_token("x" * 32))
    else:
        with pytest.raises((AuthenticationError, AuthorizationError)):
            asyncio.run(provider.resolve(reference))


def documents():
    return [
        d for p in (ROOT / "deploy").rglob("*.yaml") for d in yaml.safe_load_all(p.read_text()) if d
    ]


def test_all_deployment_rbac_is_read_only_and_no_secret_access():
    roles = [d for d in documents() if d["kind"] in {"Role", "ClusterRole"}]
    assert roles and all(d["kind"] == "Role" for d in roles)
    for role in roles:
        for rule in role["rules"]:
            assert set(rule["verbs"]) <= {"get", "list"}
            assert "*" not in (*rule["apiGroups"], *rule["resources"], *rule["verbs"])
            assert "secrets" not in rule["resources"]
    assert not any(d["kind"] == "Secret" for d in documents())
    assert {r for role in roles for rule in role["rules"] for r in rule["resources"]} >= {
        "routes",
        "apimanagers",
    }


def test_configmap_and_pod_security_contract():
    configmap = yaml.safe_load((ROOT / "deploy/base/configmap.yaml").read_text())
    config = Configuration.model_validate(yaml.safe_load(configmap["data"]["config.yaml"]))
    assert config.environments[0].runtime.authentication.mode == "in-cluster"
    assert not config.probes.enabled and not config.observability.sources
    pod = yaml.safe_load((ROOT / "deploy/base/deployment.yaml").read_text())["spec"]["template"][
        "spec"
    ]
    assert pod["serviceAccountName"] == "agt-mcp"
    assert pod["securityContext"]["runAsNonRoot"] and "runAsUser" not in pod["securityContext"]
    container = pod["containers"][0]
    assert container["securityContext"] == {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "capabilities": {"drop": ["ALL"]},
    }
    assert pod["terminationGracePeriodSeconds"] > config.mcp.server.shutdown_timeout_seconds
    assert container["readinessProbe"]["httpGet"]["path"] == "/readyz"
    assert container["livenessProbe"]["httpGet"]["path"] == "/livez"
    assert container["resources"]["requests"] and container["resources"]["limits"]


def test_docker_build_context_excludes_secrets_and_development():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "USER 10001:0" in dockerfile and '"--transport", "http"' in dockerfile
    assert 'ENTRYPOINT ["python", "-m", "agt_mcp", "serve"]' in dockerfile
    assert ".[dev]" not in dockerfile and "COPY . " not in dockerfile
    assert "--no-index" in dockerfile and "--constraint requirements.lock" in dockerfile
    ignored = (ROOT / ".dockerignore").read_text().splitlines()
    assert ignored[0] == "*" and not any(x.startswith("!config") for x in ignored)
