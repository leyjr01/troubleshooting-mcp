import asyncio
import socket

import pytest


@pytest.fixture(autouse=True)
def fixture_only_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Scenario harness must not access a network")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(asyncio, "open_connection", forbidden)
