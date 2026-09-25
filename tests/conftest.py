import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption(
        "--scenario-acceptance",
        action="store_true",
        help="Require diagnostic PASS, including known capability gaps",
    )


@pytest.fixture(autouse=True)
def no_network(monkeypatch, request):
    import socket

    original = socket.getaddrinfo

    def loopback_only(host, *args, **kwargs):
        if host not in ("127.0.0.1", b"127.0.0.1"):
            raise AssertionError("Only numeric loopback is allowed in transport tests")
        return original(host, *args, **kwargs)

    def blocked(*args, **kwargs):
        raise AssertionError("External network is outside this test suite")

    monkeypatch.setattr("socket.create_connection", blocked)
    monkeypatch.setattr(
        "socket.getaddrinfo",
        loopback_only if request.node.get_closest_marker("local_transport") else blocked,
    )


@pytest.fixture
def bundle_data():
    return json.loads((ROOT / "tests/fixtures/bundle.json").read_text(encoding="utf-8"))
