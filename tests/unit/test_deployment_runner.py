import logging
from unittest.mock import Mock

import pytest

from agt_mcp.configuration.models import Configuration
from agt_mcp.mcp import runner
from tests.integration.test_mcp_server import config
from tests.unit.test_deployment_readiness import remote


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_runner_preserves_explicit_host_auth_and_shutdown_settings(monkeypatch, transport):
    data = config().model_dump()
    if transport == "http":
        data["mcp"]["server"].update(remote(authorization=data["mcp"]["server"]["authorization"]))
    settings = Configuration.model_validate(data)
    server = Mock()
    monkeypatch.setattr(runner, "create_server", lambda runtime: server)
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: None)
    runner.serve(settings)
    actual = server.run.call_args.kwargs
    assert actual["transport"] == transport and not actual["show_banner"]
    if transport == "http":
        assert actual["host"] == "0.0.0.0" and actual["host_origin_protection"]
        assert actual["allowed_origins"] == [] and actual["path"] == "/mcp"
        assert actual["uvicorn_config"]["timeout_graceful_shutdown"] == 30
        assert not actual["uvicorn_config"]["proxy_headers"]
        assert not actual["uvicorn_config"]["access_log"]


def test_framework_log_filter_drops_headers_exception_and_stack():
    record = logging.LogRecord(
        "uvicorn.error",
        logging.ERROR,
        "",
        1,
        "Authorization: Bearer %s",
        ("secret",),
        (ValueError, ValueError("secret"), None),
    )
    record.stack_info = "secret"
    assert runner.FrameworkLogFilter().filter(record)
    assert record.getMessage() == "framework_event"
    assert record.exc_info is None and record.stack_info is None
    audit = logging.LogRecord(
        "agt_mcp.audit", logging.INFO, "", 1, '{"event":"tool_finished"}', (), None
    )
    assert runner.FrameworkLogFilter().filter(audit)
    assert audit.getMessage() == '{"event":"tool_finished"}'
