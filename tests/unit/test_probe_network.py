import asyncio
import ipaddress
import ssl
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from agt_mcp.datasources.probe_network import NetworkProbeExecutor, resolve
from agt_mcp.probes.models import CAPABILITIES, ProbeRequest, ProbeType
from agt_mcp.probes.planner import target_from
from agt_mcp.probes.policy import ProbePolicy
from agt_mcp.probes.ports import ProbeFailure
from tests.correlation_support import NOW
from tests.probe_support import config


def request(cfg, kind):
    return ProbeRequest(
        id="test",
        target=target_from(cfg.endpoints[0], NOW),
        probe_type=kind,
        allowed=True,
        reason="ALLOWED",
        required_capability=CAPABILITIES[kind],
    )


@pytest.mark.parametrize("case", ["policy", "dns_rebinding", "downgrade"])
def test_approved_redirect_still_requires_fresh_policy_and_dns(case, monkeypatch):
    cfg = config(protocol="https" if case == "downgrade" else "http", limits={"max_redirects": 1})
    other = cfg.endpoints[0].model_copy(
        update={"id": "redirect", "host": "other.example", "protocol": "http"}
    )
    policy = cfg.policy.environments[0].model_copy(
        update={
            "allowed_hosts": ("backend.example",)
            if case == "policy"
            else ("backend.example", "other.example"),
            "allowed_protocols": ("http", "https"),
        }
    )
    cfg = cfg.model_copy(
        update={
            "endpoints": (*cfg.endpoints, other),
            "policy": cfg.policy.model_copy(update={"environments": (policy,)}),
        }
    )
    connections = []

    class Writer:
        def write(self, data):
            pass

        async def drain(self):
            pass

        def close(self):
            pass

        async def wait_closed(self):
            pass

    async def connect(*args, **kwargs):
        connections.append(args)
        reader = asyncio.StreamReader()
        reader.feed_data(b"HTTP/1.1 302 Found\r\nLocation: http://other.example:443/\r\n\r\n")
        return reader, Writer()

    async def dns(host, port):
        return ("169.254.169.254",)

    async def tls(writer, target):
        from agt_mcp.probes.models import ProbeObservation

        return ProbeObservation(tcp_connected=True, certificate_verified=True)

    monkeypatch.setattr(asyncio, "open_connection", connect)
    executor = NetworkProbeExecutor(ProbePolicy(cfg), resolver=dns)
    monkeypatch.setattr(executor, "tls", tls)
    with pytest.raises(ProbeFailure) as caught:
        asyncio.run(
            executor.execute(
                request(cfg, ProbeType.HTTPS if case == "downgrade" else ProbeType.HTTP),
                ("10.20.1.2",),
            )
        )
    assert caught.value.blocked and len(connections) == 1
    assert caught.value.category == (
        "TARGET_BLOCKED_BY_POLICY" if case == "dns_rebinding" else "REDIRECT_BLOCKED"
    )


@pytest.mark.parametrize("code", [10, 62, 64, None])
def test_tls_expiry_hostname_and_handshake_are_distinct(code):
    class Writer:
        async def start_tls(self, *args, **kwargs):
            if code is None:
                raise ssl.SSLError("unsafe raw error")
            exc = ssl.SSLCertVerificationError()
            exc.verify_code = code
            raise exc

    cfg = config()
    with pytest.raises(ProbeFailure) as caught:
        asyncio.run(
            NetworkProbeExecutor(ProbePolicy(cfg)).tls(Writer(), target_from(cfg.endpoints[0], NOW))
        )
    obs = caught.value.observation
    assert obs.tcp_connected
    if code is None:
        assert caught.value.category == "TLS_HANDSHAKE_FAILED" and obs.tls_handshake is False
    else:
        assert caught.value.category == "TLS_VERIFICATION_FAILED"
        assert obs.certificate_verified is False and obs.tls_handshake is None
        assert obs.hostname_verified is (False if code in {62, 64} else None)
        assert obs.chain_verified is (None if code in {62, 64} else False)


def test_tcp_closes_without_sending_payload_and_close_errors(monkeypatch):
    class Writer:
        closed = False

        def close(self):
            self.closed = True

        async def wait_closed(self):
            raise OSError("already closed")

    writer = Writer()

    async def connect(*args, **kwargs):
        return None, writer

    monkeypatch.setattr(asyncio, "open_connection", connect)
    cfg = config()
    result = asyncio.run(
        NetworkProbeExecutor(ProbePolicy(cfg)).execute(request(cfg, ProbeType.TCP), ("10.20.1.2",))
    )
    assert writer.closed and result.tcp_connected


@pytest.mark.parametrize("mode", ["literal", "hostname", "failure", "unsafe", "empty", "too_many"])
def test_dns_no_internet(mode, monkeypatch):
    async def resolver(host, port):
        if mode == "failure":
            raise OSError("untrusted secret exception")
        return (
            ()
            if mode == "empty"
            else ("10.20.1.1",) * 20
            if mode == "too_many"
            else ("169.254.169.254",)
            if mode == "unsafe"
            else ("10.20.1.1",)
        )

    async def run():
        cfg = config(host="10.20.1.1" if mode == "literal" else "backend.example")
        executor = NetworkProbeExecutor(ProbePolicy(cfg), resolver=resolver)
        if mode in {"failure", "unsafe", "empty", "too_many"}:
            with pytest.raises(ProbeFailure) as exc:
                await executor.execute(request(cfg, ProbeType.DNS), ())
            assert "secret" not in str(exc.value)
        else:
            assert (await executor.execute(request(cfg, ProbeType.DNS), ())).addresses == (
                "10.20.1.1",
            )
        assert await resolve("::1", 443) == ("::1",)

        async def fake_getaddrinfo(*args, **kwargs):
            return [(None, None, None, None, ("127.0.0.1", 443))]

        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)
        assert await resolve("localhost", 443) == ("127.0.0.1",)

    asyncio.run(run())


@pytest.mark.parametrize("status,method", [(200, "HEAD"), (503, "HEAD"), (200, "GET")])
def test_local_http_observation_has_no_body_or_credentials(status, method):
    received = []

    async def handler(reader, writer):
        received.append(await reader.readuntil(b"\r\n\r\n"))
        writer.write(
            (
                f"HTTP/1.1 {status} Result\r\nContent-Length: 16\r\n"
                "Set-Cookie: secret\r\nAuthorization: secret\r\n\r\nSECRET-BODY-DATA"
            ).encode()
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def run():
        async with await asyncio.start_server(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            cfg = config("127.0.0.1", port, "http")
            cfg = cfg.model_copy(
                update={"endpoints": (cfg.endpoints[0].model_copy(update={"method": method}),)}
            )
            executor = NetworkProbeExecutor(ProbePolicy(cfg))
            result = await executor.execute(request(cfg, ProbeType.HTTP), ("127.0.0.1",))
            assert result.http_status == status and result.headers == {"content-length": "16"}
            assert "secret" not in result.model_dump_json().lower()

    asyncio.run(run())
    assert received[0].startswith(method.encode()) and b"Authorization" not in received[0]


@pytest.mark.parametrize(
    "response",
    [
        b"garbage\r\n\r\n",
        b"HTTP/1.1 999 Bad\r\n\r\n",
        b"HTTP/9.9 200 Bad\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nX: a\r\nX: b\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nBadHeader\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nX: \x01\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nX: " + b"x" * 1000 + b"\r\n\r\n",
        b"incomplete",
    ],
)
def test_http_protocol_and_header_limits(response):
    async def handler(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def run():
        async with await asyncio.start_server(handler, "127.0.0.1", 0) as server:
            cfg = config(
                "127.0.0.1",
                server.sockets[0].getsockname()[1],
                "http",
                limits={"max_header_bytes": 256},
            )
            with pytest.raises(ProbeFailure) as exc:
                await NetworkProbeExecutor(ProbePolicy(cfg)).execute(
                    request(cfg, ProbeType.HTTP), ("127.0.0.1",)
                )
            assert exc.value.category == "HTTP_PROTOCOL_ERROR"

    asyncio.run(run())


@pytest.mark.parametrize(
    "redirect", ["metadata", "credentials", "same_approved", "limit", "malformed", "query"]
)
def test_redirect_policy_rechecked(redirect):
    calls = []

    async def run():
        async def handler(reader, writer):
            data = await reader.readuntil(b"\r\n\r\n")
            calls.append(data)
            if data.startswith(b"HEAD /next "):
                response = b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
            else:
                location = {
                    "metadata": "http://169.254.169.254/latest",
                    "credentials": "http://user:password@127.0.0.1/",
                    "malformed": "http://[bad/",
                    "query": "http://127.0.0.1/?token=secret",
                }.get(redirect, f"http://127.0.0.1:{port}/next")
                response = f"HTTP/1.1 302 Found\r\nLocation: {location}\r\n\r\n".encode()
            writer.write(response)
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        async with await asyncio.start_server(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            cfg = config(
                "127.0.0.1", port, "http", limits={"max_redirects": 0 if redirect == "limit" else 1}
            )
            endpoint = cfg.endpoints[0]
            cfg = cfg.model_copy(
                update={
                    "endpoints": (
                        endpoint,
                        endpoint.model_copy(update={"id": "redirect", "path": "/next"}),
                    )
                }
            )
            executor = NetworkProbeExecutor(ProbePolicy(cfg))
            if redirect == "same_approved":
                result = await executor.execute(request(cfg, ProbeType.HTTP), ("127.0.0.1",))
                assert result.http_status == 200 and result.redirects == ("redirect",)
            else:
                with pytest.raises(ProbeFailure) as exc:
                    await executor.execute(request(cfg, ProbeType.HTTP), ("127.0.0.1",))
                assert exc.value.blocked
                assert exc.value.category == (
                    "REDIRECT_LIMIT" if redirect == "limit" else "REDIRECT_BLOCKED"
                )

    asyncio.run(run())
    assert len(calls) == (2 if redirect == "same_approved" else 1)


@pytest.fixture
def tls_contexts(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost-test")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "test-cert.pem", tmp_path / "test-key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert_path, key_path)
    client = ssl.create_default_context(cafile=str(cert_path))
    return server, client


@pytest.mark.parametrize(
    "kind,trusted", [(ProbeType.TLS, True), (ProbeType.HTTPS, True), (ProbeType.TLS, False)]
)
def test_real_local_tls_preserves_verification_stages(tls_contexts, kind, trusted):
    async def handler(reader, writer):
        data = await reader.read(4096)
        if data:
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def run():
        async with await asyncio.start_server(
            handler, "127.0.0.1", 0, ssl=tls_contexts[0]
        ) as server:
            cfg = config("127.0.0.1", server.sockets[0].getsockname()[1], "https")
            executor = NetworkProbeExecutor(
                ProbePolicy(cfg), tls_context=tls_contexts[1] if trusted else None
            )
            if trusted:
                observation = await executor.execute(request(cfg, kind), ("127.0.0.1",))
                assert (
                    observation.tcp_connected
                    and observation.tls_handshake
                    and observation.certificate_verified
                    and observation.hostname_verified
                )
                assert (
                    observation.certificate_subject and observation.valid_until and observation.sans
                )
            else:
                with pytest.raises(ProbeFailure) as exc:
                    await executor.execute(request(cfg, kind), ("127.0.0.1",))
                assert exc.value.category == "TLS_VERIFICATION_FAILED"
                assert (
                    exc.value.observation.tcp_connected
                    and exc.value.observation.certificate_verified is False
                )
                assert exc.value.observation.tls_handshake is None

    asyncio.run(run())


@pytest.mark.parametrize(
    "error,category",
    [(ConnectionRefusedError(), "CONNECTION_REFUSED"), (OSError(), "NETWORK_ERROR")],
)
def test_socket_errors_and_address_pinning(monkeypatch, error, category):
    cfg = config()
    called = []

    async def connect(host, port, **kwargs):
        called.append(host)
        raise error

    monkeypatch.setattr(asyncio, "open_connection", connect)
    with pytest.raises(ProbeFailure) as exc:
        asyncio.run(
            NetworkProbeExecutor(ProbePolicy(cfg)).execute(
                request(cfg, ProbeType.TCP), ("10.20.1.2",)
            )
        )
    assert exc.value.category == category and called == ["10.20.1.2"]


def test_verification_cannot_be_disabled_and_invalid_target_never_connects():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    with pytest.raises(ValueError):
        NetworkProbeExecutor(ProbePolicy(config()), tls_context=context)
    cfg = config()
    with pytest.raises(ProbeFailure):
        asyncio.run(
            NetworkProbeExecutor(ProbePolicy(cfg)).execute(
                request(cfg, ProbeType.TCP), ("169.254.169.254",)
            )
        )
    with pytest.raises(ProbeFailure):
        asyncio.run(
            NetworkProbeExecutor(ProbePolicy(config(endpoints=()))).execute(
                request(cfg, ProbeType.TCP), ("10.20.1.2",)
            )
        )
