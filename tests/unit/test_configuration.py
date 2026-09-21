from pathlib import Path

import pytest
from pydantic import ValidationError

from agt_mcp.configuration.loader import MAX_CONFIG_BYTES, load_configuration, merge
from agt_mcp.configuration.models import Configuration
from agt_mcp.core.errors import ConfigurationError, SchemaMappingError
from agt_mcp.mapping.schema import load_mapping

ROOT = Path(__file__).resolve().parents[2]


def test_example_composition():
    config = load_configuration(sorted((ROOT / "config").glob("*.example.yaml")), environ={})
    assert len(config.datasources) == 2
    assert config.gateways[0].adapter == "threescale"
    assert not config.gateways[0].enabled
    assert config.application.read_only


def test_precedence_and_replacement(tmp_path):
    base = tmp_path / "base.yaml"
    overlay = tmp_path / "env.yaml"
    base.write_text("application:\n  timeout_seconds: 20\n", encoding="utf-8")
    overlay.write_text("application:\n  timeout_seconds: 30\n", encoding="utf-8")
    assert load_configuration().application.timeout_seconds == 10
    assert load_configuration([base], environ={}).application.timeout_seconds == 20
    assert load_configuration([base], overlay, environ={}).application.timeout_seconds == 30
    assert (
        load_configuration(
            [base], overlay, {"AGT_TIMEOUT_SECONDS": "40"}
        ).application.timeout_seconds
        == 40
    )
    assert merge({"x": [1]}, {"x": [2]}) == {"x": [2]}


def test_placeholders(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("application:\n  environment: ${ENV_ID}\n", encoding="utf-8")
    assert load_configuration([path], environ={"ENV_ID": "demo"}).application.environment == "demo"
    with pytest.raises(ConfigurationError):
        load_configuration([path], environ={})


@pytest.mark.parametrize(
    "text",
    [
        "[]",
        "application: []",
        "read_only: false",
        "application: {read_only: false}",
        "application: {timeout_seconds: 0}",
        "application: {timeout_seconds: .nan}",
        "application: {max_payload_bytes: 999999999}",
        "application: {password: secret}",
        "application: {environment: '${UNKNOWN}/suffix'}",
        "x: &shared {value: 1}\ny: *shared",
        "x: 1\nx: 2",
        "1: value",
        "[broken",
        "x: !!python/object/apply:os.system ['echo unsafe']",
    ],
)
def test_unsafe_configuration_rejected(tmp_path, text):
    path = tmp_path / "invalid.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_configuration([path], environ={})


@pytest.mark.parametrize("kind", ["oversized", "encoding", "missing", "deep"])
def test_invalid_file(tmp_path, kind):
    path = tmp_path / "bad.yaml"
    if kind == "oversized":
        path.write_bytes(b"x" * (MAX_CONFIG_BYTES + 1))
    elif kind == "encoding":
        path.write_bytes(b"\xff")
    elif kind == "deep":
        path.write_text("x: " + "[" * 40 + "0" + "]" * 40, encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_configuration([path], environ={})


@pytest.mark.parametrize("env", [{"AGT_TIMEOUT_SECONDS": "bad"}, {"AGT_MAX_PAYLOAD_BYTES": "-1"}])
def test_bad_environment_values(env):
    with pytest.raises(ConfigurationError):
        load_configuration(environ=env)


@pytest.mark.parametrize(
    "kind",
    [
        "duplicate_source",
        "duplicate_gateway",
        "gateway_scope",
        "credential_scope",
        "gateway_missing",
        "enabled_gateway",
        "tls_disabled",
        "verify_disabled",
        "unsafe_host",
    ],
)
def test_config_identity_and_security(kind):
    data = load_configuration(
        sorted((ROOT / "config").glob("*.example.yaml")), environ={}
    ).model_dump()
    if kind == "duplicate_source":
        data["datasources"] = (*data["datasources"], data["datasources"][0])
    elif kind == "duplicate_gateway":
        data["gateways"] = (*data["gateways"], data["gateways"][0])
    elif kind == "gateway_scope":
        data["gateways"][0]["environment_id"] = "other"
    elif kind == "credential_scope":
        data["datasources"][0]["credentials"]["environment_id"] = "other"
    elif kind == "gateway_missing":
        data["gateways"][0]["datasource_id"] = "absent"
    elif kind == "enabled_gateway":
        data["gateways"][0]["enabled"] = True
    elif kind == "tls_disabled":
        data["datasources"][0]["tls"]["enabled"] = False
    elif kind == "verify_disabled":
        data["datasources"][0]["tls"]["verify"] = False
    else:
        data["datasources"][0]["connection"]["host"] = "user:secret@host"
    with pytest.raises(ValidationError):
        Configuration.model_validate(data)


@pytest.mark.parametrize("path", list((ROOT / "mappings").rglob("*.yaml")), ids=lambda p: p.name)
def test_mapping_examples(path):
    assert "id" in load_mapping(path).fields


@pytest.mark.parametrize(
    "text",
    [
        "entity: Unknown",
        "entity: Incident\nsource: {datasource: db, table: 'X;DROP'}\nfields: {}",
        "entity: Incident\nsource: {datasource: db, table: T}\nfields: {unknown: {column: A}}",
        "entity: Incident\nsource: {datasource: db, table: T}\n"
        "fields: {id: {column: ID}, password: {column: P}}",
    ],
)
def test_mapping_invalid(tmp_path, text):
    path = tmp_path / "mapping.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(SchemaMappingError):
        load_mapping(path)


def test_mapping_missing_file(tmp_path):
    with pytest.raises(SchemaMappingError):
        load_mapping(tmp_path / "missing.yaml")
