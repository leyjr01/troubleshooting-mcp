import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from agt_mcp.configuration.knowledge import KnowledgeLimits, KnowledgeSourceConfig
from agt_mcp.configuration.models import Configuration
from agt_mcp.core.errors import ConfigurationError, SchemaMappingError
from agt_mcp.core.models import Provenance
from agt_mcp.mapping.engine import IncidentMappingEngine
from agt_mcp.mapping.schema import MappingSpec
from agt_mcp.mcp.bootstrap import build_runtime
from tests.knowledge_support import setup


def spec(**fields):
    return MappingSpec(
        entity="Incident",
        source={"datasource": "incidents", "table": "HISTORY"},
        fields={"id": {"column": "ID"}, **{k: {"column": v} for k, v in fields.items()}},
    )


def provenance():
    return Provenance(
        source_id="incidents",
        environment_id="demo",
        retrieved_at=datetime.now(UTC),
        source_reference="incidents/HISTORY",
        content_sha256="a" * 64,
    )


def test_incident_mapping_retains_structured_history_and_redacts():
    mapping = spec(
        timestamp="AT",
        symptom="DESCRIPTION",
        historical_root_cause="CAUSE",
        historical_remediation="ACTION",
        tags="TAGS",
    )
    incident = IncidentMappingEngine().map_record(
        {
            "ID": "INC-001",
            "AT": "2026-09-23T12:00:00Z",
            "DESCRIPTION": "APIcast 503",
            "CAUSE": "Past outage",
            "ACTION": "password: HIDDEN",
            "TAGS": ["tls"],
            "PERSON": "PRIVATE NAME",
            "EMAIL": "private@example.invalid",
        },
        mapping,
        provenance(),
    )
    assert incident.historical_root_cause == "Past outage"
    assert incident.root_cause_finding_id is None
    assert incident.tags == ("tls",)
    assert "HIDDEN" not in incident.model_dump_json()
    assert "PRIVATE NAME" not in incident.model_dump_json()


@pytest.mark.parametrize("case", ["entity", "source", "missing", "environment", "invalid"])
def test_mapping_rejects_invalid_rows(case):
    mapping = spec(timestamp="AT", symptom="DESCRIPTION")
    row = {"ID": "INC-001", "AT": "2026-09-23T12:00:00Z", "DESCRIPTION": "symptom"}
    if case == "entity":
        mapping = mapping.model_copy(update={"entity": "Resource"})
    elif case == "source":
        mapping = spec(source="SOURCE")
    elif case == "missing":
        del row["AT"]
    elif case == "environment":
        mapping = spec(environment_id="ENV")
        row["ENV"] = "prod"
    else:
        row["AT"] = "not a timestamp"
    with pytest.raises(SchemaMappingError):
        IncidentMappingEngine().map_record(row, mapping, provenance())


@pytest.mark.parametrize("table", ["HISTORY;DROP TABLE secrets", "(SELECT secret)", "a b"])
def test_mapping_does_not_accept_sql(table):
    with pytest.raises(ValidationError):
        MappingSpec(
            entity="Incident",
            source={"datasource": "incidents", "table": table},
            fields={"id": {"column": "ID"}},
        )


@pytest.mark.parametrize(
    "change",
    [
        {"overlap": 1200},
        {"minimum_size": 1000, "max_chunk_size": 100},
    ],
)
def test_invalid_chunk_configuration(change):
    with pytest.raises(ValidationError):
        KnowledgeLimits(**change)


@pytest.mark.parametrize(
    "change",
    [
        {"source_type": "INTERNAL_KNOWLEDGE"},
        {"source_url": "https://evil.invalid/docs"},
        {"metadata": {}},
        {"source_url": None},
    ],
)
def test_official_allowlist_and_provenance_required(change):
    data = dict(
        id="official",
        type="official-local",
        local_path="unused",
        source_type="OFFICIAL_DOCUMENTATION",
        source_url="https://docs.redhat.com/docs",
        metadata={"product": "3scale", "product_version": "2.16"},
    )
    data.update(change)
    with pytest.raises(ValidationError):
        KnowledgeSourceConfig.model_validate(data)


@pytest.mark.parametrize(
    "case", ["duplicate", "environment", "credential", "mapping", "mapping_source"]
)
def test_knowledge_composition_fail_closed(tmp_path, case):
    runtime, _, _ = setup(tmp_path)
    data = runtime.configuration.model_dump(mode="json")
    if case == "duplicate":
        data["knowledge_sources"].append(data["knowledge_sources"][0])
    elif case == "environment":
        data["knowledge_sources"][0]["metadata"]["environment"] = "missing"
    elif case == "credential":
        data["knowledge_sources"][0]["metadata"]["environment"] = "demo"
        data["knowledge_sources"][0]["credentials"] = {
            "provider": "env",
            "reference": "GIT_CREDENTIAL",
            "environment_id": "demo",
        }
    elif case == "mapping":
        data["knowledge_sources"][2]["mapping_path"] = None
    else:
        data["knowledge_sources"][2]["id"] = "other-incidents"
    with pytest.raises((ValidationError, ConfigurationError)):
        build_runtime(Configuration.model_validate(data))


@pytest.mark.parametrize("content", ["broken json", "{}", "[1]", '[{"ID":"missing required"}]'])
def test_incident_local_invalid_rows(tmp_path, content):
    runtime, context, _ = setup(tmp_path)
    source = runtime.knowledge.sources["incidents"]
    (Path(source.config.local_path) / "rows.json").write_text(content)
    with pytest.raises((ConfigurationError, SchemaMappingError)):
        asyncio.run(source.snapshot(context))
