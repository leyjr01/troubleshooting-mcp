import asyncio
import json
from datetime import timedelta

import pytest
from pydantic import ValidationError

from agt_mcp.configuration.observability import ObservabilityLimits
from agt_mcp.core.errors import AuthorizationError
from agt_mcp.datasources.prometheus import PrometheusObservabilityAdapter
from agt_mcp.observability.models import SignalType
from tests.correlation_support import NOW
from tests.observability_support import query, source
from tests.probe_support import config as probe_config


def prometheus(**changes):
    base = dict(
        type="prometheus",
        url="https://backend.example:443/prometheus",
        usage=(SignalType.METRIC,),
        network_policy=probe_config().policy.environments[0],
    )
    return source(**(base | changes))


def payload(mode="instant", values=None, labels=None, **changes):
    item = {"metric": labels or {"namespace": "example", "service": "service"}}
    item["value" if mode == "instant" else "values"] = values or (
        [NOW.timestamp(), "0.95"] if mode == "instant" else [[NOW.timestamp(), "0.95"]]
    )
    return {
        "status": "success",
        "data": {"resultType": "vector" if mode == "instant" else "matrix", "result": [item]},
        **changes,
    }


class HTTP:
    def __init__(self, data=None, status=200):
        self.data = data if data is not None else payload()
        self.status, self.calls = status, []

    async def get(self, path, parameters):
        self.calls.append((path, parameters))
        return self.status, self.data if isinstance(self.data, bytes) else json.dumps(
            self.data
        ).encode()


def adapter(http=None, cfg=None, **limits):
    return PrometheusObservabilityAdapter(
        cfg or prometheus(), ObservabilityLimits(**limits), http or HTTP()
    )


def metric_query(**changes):
    return query(
        **(
            dict(
                resource_refs=("service",), signal_types=(SignalType.METRIC,), metric_mode="instant"
            )
            | changes
        )
    )


@pytest.mark.parametrize("mode", ["instant", "range"])
@pytest.mark.parametrize(
    "intent", ["availability", "restarts", "latency", "resource_usage", "error_rate"]
)
def test_internal_templates_and_bounded_protocol(mode, intent):
    http = HTTP(payload(mode))
    subject = adapter(http)
    result = asyncio.run(
        subject.query(metric_query(metric_mode=mode, metric_intent=intent, limit=3))
    )
    assert len(result.observations) == 1 and result.observations[0].value == 0.95
    path, params = http.calls[0]
    assert path == ("/api/v1/query" if mode == "instant" else "/api/v1/query_range")
    assert 'namespace="example"' in params["query"] and 'service="service"' in params["query"]
    assert params["limit"] == "3" and params["timeout"] == "3s"
    if mode == "range":
        assert float(params["end"]) - float(params["start"]) == 300
        assert int(params["step"]) >= 150
    else:
        assert float(params["time"]) == NOW.timestamp()
    if intent == "error_rate":
        assert params["query"].startswith("rate(") and 'code=~"5.."' in params["query"]
    assert subject.capabilities() == frozenset({SignalType.METRIC})


def test_provider_mapping_is_configurable_and_unavailable_intent_explicit():
    http = HTTP()
    subject = adapter(http, prometheus(metric_names={"availability": "custom_gateway_up"}))
    asyncio.run(subject.query(metric_query()))
    assert http.calls[0][1]["query"].startswith("custom_gateway_up{")
    batch = asyncio.run(subject.query(metric_query(metric_intent="latency")))
    assert batch.warnings == ("metric_intent_unavailable",) and len(http.calls) == 1


@pytest.mark.parametrize("status", [200, 503, 302, 401, 403])
def test_health_is_live_and_auth_is_distinct(status):
    subject = adapter(HTTP(status=status))
    if status in {401, 403}:
        with pytest.raises(AuthorizationError):
            asyncio.run(subject.health())
    else:
        assert asyncio.run(subject.health()) == ("AVAILABLE" if status == 200 else "UNAVAILABLE")
    assert subject.transport.calls == [("/-/ready", {})]


def test_health_network_exception_is_unavailable():
    class Down:
        async def get(self, *_):
            raise OSError("token=fake-network-error")

    assert asyncio.run(adapter(Down()).health()) == "UNAVAILABLE"


@pytest.mark.parametrize(
    "case", ["environment", "resource", "empty", "disabled", "signal", "window"]
)
def test_adapter_revalidates_scope(case):
    subject, q = adapter(), metric_query()
    if case == "environment":
        q = metric_query(environment_id="other")
    elif case == "resource":
        q = metric_query(resource_refs=("unknown",))
    elif case == "empty":
        q = metric_query(resource_refs=(), trace_id="t")
    elif case == "disabled":
        subject = adapter(cfg=prometheus(enabled=False))
    elif case == "signal":
        q = metric_query(signal_types=(SignalType.LOG,))
    else:
        q = metric_query(time_window={"start": NOW - timedelta(hours=2), "end": NOW})
    with pytest.raises(ValueError if case == "window" else AuthorizationError):
        asyncio.run(subject.query(q))
    assert not subject.transport.calls


@pytest.mark.parametrize("status", [401, 403, 404, 500, 302])
def test_no_error_body_forwarding(status):
    with pytest.raises(AuthorizationError if status in {401, 403} else ConnectionError):
        asyncio.run(adapter(HTTP({"error": "password=fake-error"}, status)).query(metric_query()))


@pytest.mark.parametrize(
    "data",
    [
        b"not json",
        {"status": "error"},
        {"status": "success", "data": {"resultType": "scalar"}},
        {"status": "success", "data": {"resultType": "vector", "result": {}}},
        payload(values=[NOW.timestamp(), "NaN"]),
        payload(values=[NOW.timestamp(), "+Inf"]),
        payload(values=["not-a-timestamp", "1"]),
    ],
)
def test_invalid_provider_data_rejected(data):
    with pytest.raises((ValueError, KeyError)):
        asyncio.run(adapter(HTTP(data)).query(metric_query()))


def test_response_byte_limit_wrong_resource_and_filter_scope():
    with pytest.raises(ValueError, match="response limit"):
        asyncio.run(adapter(HTTP(b" " * 1025), max_response_bytes=1024).query(metric_query()))
    with pytest.raises(AuthorizationError):
        asyncio.run(adapter(HTTP(payload(labels={"namespace": "other"}))).query(metric_query()))
    subject = adapter()
    result = asyncio.run(
        subject.query(metric_query(trace_id="unmapped", correlation_id="unmapped"))
    )
    assert not result.observations and not subject.transport.calls


def test_range_order_volume_duplicates_and_untrusted_warnings():
    values = [[(NOW - timedelta(seconds=i % 200)).timestamp(), str(i % 200)] for i in range(2000)]
    http = HTTP(payload("range", values=values, warnings=["password=fake-warning"]))
    subject = adapter(http)
    q = metric_query(metric_mode="range", limit=5)
    a = asyncio.run(subject.query(q))
    http.data = payload("range", values=list(reversed(values)), warnings=["password=fake-warning"])
    b = asyncio.run(subject.query(q))
    assert a == b and len(a.observations) == 5
    assert set(a.warnings) == {"source_limit_reached", "provider_warning"}
    assert "fake-warning" not in a.model_dump_json()
    http.data = payload("range", values=[[NOW.timestamp(), "1"]] * 4)
    assert len(asyncio.run(subject.query(q)).observations) == 1
    http.data = payload(values=[(NOW + timedelta(seconds=1)).timestamp(), "1"])
    result = asyncio.run(subject.query(metric_query()))
    assert not result.observations and result.warnings == ("out_of_window_signal",)


@pytest.mark.parametrize(
    "change",
    [
        {"url": "http://user:pass@backend.example"},
        {"url": "ftp://backend.example"},
        {"url": "https://backend.example/?token=x"},
        {"url": "https://backend.example/#x"},
        {"url": None},
        {"network_policy": None},
        {"usage": ["LOG"]},
        {"metric_names": {"availability": "up} or secret{"}},
        {"error_status_label": 'code=~".*"'},
        {
            "url": "http://backend.example",
            "credentials": {
                "provider": "environment",
                "reference": "TEST_TOKEN",
                "environment_id": "demo",
            },
        },
    ],
)
def test_source_configuration_rejects_unsafe_protocols_and_queries(change):
    with pytest.raises(ValidationError):
        prometheus(**change)
