import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network is outside Sprint 0")

    monkeypatch.setattr("socket.create_connection", blocked)
    monkeypatch.setattr("socket.getaddrinfo", blocked)


@pytest.fixture
def bundle_data():
    return json.loads((ROOT / "tests/fixtures/bundle.json").read_text(encoding="utf-8"))
