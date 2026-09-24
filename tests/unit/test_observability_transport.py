import asyncio
import json
import ssl

import pytest
from pydantic import SecretStr

from agt_mcp.configuration.observability import ObservabilityLimits
from agt_mcp.core.errors import AuthenticationError, AuthorizationError
from agt_mcp.credentials.providers import CredentialReference
from agt_mcp.datasources.prometheus import ApprovedMetricsHTTP
from agt_mcp.probes.ports import ProbeFailure
from tests.probe_support import config as probe_config
from tests.unit.test_observability_prometheus import prometheus
from tests.unit.test_probe_network import tls_contexts as shared_tls_contexts


@pytest.fixture
def tls_contexts(tmp_path):
    return shared_tls_contexts.__wrapped__(tmp_path)


def local_source(port=443, protocol="https", **changes):
    return prometheus(
        **(
            dict(
                url=f"{protocol}://127.0.0.1:{port}/prometheus",
                network_policy=probe_config("127.0.0.1", port, protocol).policy.environments[0],
            )
            | changes
        )
    )


class Credential:
    def __init__(self, value="fake-credential-token"):
        self.value, self.calls = value, 0

    async def resolve(self, reference):
        assert reference.environment_id == "demo"
        self.calls += 1
        return SecretStr(self.value)


def credential_ref():
    return CredentialReference(
        provider="environment", reference="SPRINT8_TEST_TOKEN", environment_id="demo"
    )


class Writer:
    def __init__(self):
        self.request, self.closed = b"", False

    def write(self, data):
        self.request += data

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


def fake_transport(monkeypatch, response, cfg=None, credentials=None):
    subject = ApprovedMetricsHTTP(
        cfg or local_source(protocol="http"),
        ObservabilityLimits(max_response_bytes=1024),
        credentials,
    )
    writer = Writer()

    async def connect(host, port, **kwargs):
        assert host == "127.0.0.1"  # Numeric, policy-checked and pinned destination.
        reader = asyncio.StreamReader()
        reader.feed_data(response)
        reader.feed_eof()
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", connect)
    return subject, writer


@pytest.mark.parametrize(
    "response,body",
    [
        (b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}", b"{}"),
        (b"HTTP/1.0 200 OK\r\n\r\n{}", b"{}"),
        (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n", b"{}"),
    ],
)
def test_bounded_readonly_http_framing(monkeypatch, response, body):
    subject, writer = fake_transport(monkeypatch, response)
    assert asyncio.run(subject.get("/api/v1/query", {"query": 'up{app="x"}'})) == (200, body)
    assert writer.request.startswith(b"GET /prometheus/api/v1/query?query=")
    assert b"Authorization" not in writer.request and writer.closed
    assert b"Host: 127.0.0.1:443" in writer.request


@pytest.mark.parametrize(
    "response",
    [
        b"HTTP/9.0 200 OK\r\n\r\n",
        b"HTTP/1.1 999 Invalid\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 200 OK\r\nContent-Length: -1\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Length: 1025\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n{}",
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: gzip\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Length: 2\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n401\r\n",
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}XX",
        b"HTTP/1.1 200 OK\r\n\r\n" + b"x" * 1025,
        b"HTTP/1.1 200 OK\r\nHeader: " + b"x" * 8192 + b"\r\n\r\n",
    ],
)
def test_malformed_or_excessive_response_closes_socket(monkeypatch, response):
    subject, writer = fake_transport(monkeypatch, response)
    with pytest.raises((ValueError, asyncio.IncompleteReadError)):
        asyncio.run(subject.get("/api/v1/query", {}))
    assert writer.closed


def test_redirect_never_followed_or_location_exposed(monkeypatch):
    subject, writer = fake_transport(
        monkeypatch,
        b"HTTP/1.1 302 Found\r\nLocation: http://169.254.169.254/latest/meta-data/\r\n\r\npassword=fake",
    )
    assert asyncio.run(subject.get("/api/v1/query", {})) == (302, b"")
    assert writer.request.count(b"GET ") == 1 and writer.closed


@pytest.mark.parametrize("case", ["metadata", "mixed_dns", "policy", "operation"])
def test_ssrf_and_non_query_operations_blocked_before_connection(monkeypatch, case):
    subject = ApprovedMetricsHTTP(prometheus(), ObservabilityLimits())
    connections = []

    async def connect(*args, **kwargs):
        connections.append(args)
        raise AssertionError("must not connect")

    async def resolve(host, port):
        return ("10.20.1.2", "169.254.169.254") if case == "mixed_dns" else ("169.254.169.254",)

    subject.network.resolver = resolve
    monkeypatch.setattr(asyncio, "open_connection", connect)
    if case == "policy":
        subject.policy.config = subject.policy.config.model_copy(update={"endpoints": ()})
    with pytest.raises(AuthorizationError if case in {"operation", "policy"} else ProbeFailure):
        asyncio.run(
            subject.get(
                "/api/v1/admin/tsdb/delete_series" if case == "operation" else "/api/v1/query", {}
            )
        )
    assert not connections


@pytest.mark.parametrize("kind", ["missing", "newline", "empty", "valid", "json_escape"])
def test_credentials_checked_after_tls_and_echo_removed(monkeypatch, kind):
    cfg = local_source(credentials=credential_ref())
    credential = (
        None
        if kind == "missing"
        else Credential(
            "fake\r\nInjected: yes"
            if kind == "newline"
            else ""
            if kind == "empty"
            else "fake-credential-token"
        )
    )
    body = b'{"label":"fake-credential-token"}'
    if kind == "json_escape":
        body = b'{"label":"\\u0066ake-credential-token"}'
    subject, writer = fake_transport(
        monkeypatch,
        b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body,
        cfg,
        credential,
    )
    stages = []

    async def tls(writer, target):
        assert credential is None or credential.calls == 0
        stages.append("verified")

    monkeypatch.setattr(subject.network, "tls", tls)
    if kind in {"missing", "newline", "empty"}:
        with pytest.raises(AuthenticationError):
            asyncio.run(subject.get("/api/v1/query", {}))
        assert not writer.request
    else:
        status, raw = asyncio.run(subject.get("/api/v1/query", {}))
        assert status == 200 and json.loads(raw) == {"label": "[REDACTED]"}
        assert b"Authorization: Bearer fake-credential-token\r\n" in writer.request
    assert stages == ["verified"] and writer.closed


def test_plain_readiness_credential_echo_removed(monkeypatch):
    subject, _ = fake_transport(
        monkeypatch,
        b"HTTP/1.1 200 OK\r\n\r\nfake-credential-token",
        local_source(credentials=credential_ref()),
        Credential(),
    )

    async def tls(*_):
        pass

    monkeypatch.setattr(subject.network, "tls", tls)
    assert asyncio.run(subject.get("/-/ready", {})) == (200, b"[REDACTED]")


def test_tls_context_cannot_disable_verification():
    unsafe = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    unsafe.check_hostname = False
    unsafe.verify_mode = ssl.CERT_NONE
    with pytest.raises(ValueError):
        ApprovedMetricsHTTP(prometheus(), ObservabilityLimits(), tls_context=unsafe)


@pytest.mark.parametrize("trusted", [True, False])
def test_real_local_tls_custom_ca_and_authenticated_get(tls_contexts, tmp_path, trusted, caplog):
    received = []

    async def handler(reader, writer):
        try:
            raw = await reader.readuntil(b"\r\n\r\n")
            received.append(raw)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def scenario():
        async with await asyncio.start_server(
            handler, "127.0.0.1", 0, ssl=tls_contexts[0]
        ) as server:
            cfg = local_source(
                server.sockets[0].getsockname()[1],
                credentials=credential_ref(),
                tls={
                    "verify": True,
                    "ca_reference": str(tmp_path / "test-cert.pem") if trusted else None,
                },
            )
            credential = Credential()
            transport = ApprovedMetricsHTTP(cfg, ObservabilityLimits(), credential)
            if trusted:
                assert await transport.get(
                    "/api/v1/query_range", {"query": 'up{service="service"}'}
                ) == (200, b"{}")
                assert credential.calls == 1
            else:
                with pytest.raises(ProbeFailure):
                    await transport.get("/api/v1/query", {})
                assert credential.calls == 0 and not received

    asyncio.run(scenario())
    assert "fake-credential-token" not in caplog.text
    if trusted:
        assert len(received) == 1 and received[0].startswith(b"GET /prometheus/api/v1/query_range?")


def test_transport_timeout_cancels_and_closes(monkeypatch):
    subject, writer = fake_transport(monkeypatch, b"HTTP/1.1 200 OK\r\n\r\n")
    subject.limits = ObservabilityLimits(source_timeout_seconds=0.01)

    async def slow():
        await asyncio.sleep(1)

    writer.drain = slow
    with pytest.raises(TimeoutError):
        asyncio.run(subject.get("/-/ready", {}))
    assert writer.closed
