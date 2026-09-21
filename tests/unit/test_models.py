import copy

import pytest
from pydantic import ValidationError

from agt_mcp.core.models import API, Evidence, Gateway, InformationType, Resource
from agt_mcp.evidence.bundle import IncidentBundle
from agt_mcp.topology.models import Topology


def test_bundle_round_trip(bundle_data):
    bundle = IncidentBundle.model_validate(bundle_data)
    assert IncidentBundle.model_validate_json(bundle.model_dump_json()) == bundle
    assert bundle.model_json_schema()["properties"]["schema_version"]
    assert {kind.value for kind in InformationType} == {
        "fact",
        "observation",
        "inference",
        "hypothesis",
        "finding",
        "recommendation",
    }


def test_gateway_and_api_are_vendor_neutral():
    gateway = Gateway(
        id="g",
        environment_id="demo",
        name="Generic",
        provider="fixture",
        version="1",
        endpoint_reference="endpoint-1",
    )
    api = API(
        id="a",
        environment_id="demo",
        name="API",
        provider="fixture",
        version="1",
        gateway_id=gateway.id,
    )
    assert api.kind == "api"
    assert gateway.kind == "gateway"


@pytest.mark.parametrize(
    "field,value",
    [
        ("conclusion", "unsupported cause"),
        ("type", "inference"),
        ("timestamp", "2026-09-21T10:00:00"),
        ("id", "bad id"),
    ],
)
def test_evidence_rejects_invalid_contract(bundle_data, field, value):
    data = bundle_data["evidence"][0]
    data[field] = value
    with pytest.raises(ValidationError):
        Evidence.model_validate(data)


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_nodes",
        "duplicate_edges",
        "missing_endpoint",
        "node_environment",
        "edge_environment",
    ],
)
def test_invalid_graph(bundle_data, mutation):
    data = bundle_data["topology"]
    if mutation == "duplicate_nodes":
        data["nodes"].append(copy.deepcopy(data["nodes"][0]))
    elif mutation == "duplicate_edges":
        data["edges"].append(copy.deepcopy(data["edges"][0]))
    elif mutation == "missing_endpoint":
        data["edges"][0]["target"] = "absent"
    elif mutation == "node_environment":
        data["nodes"][0]["environment_id"] = "other"
    else:
        data["edges"][0]["source_of_information"]["environment_id"] = "other"
    with pytest.raises(ValidationError):
        Topology.model_validate(data)


@pytest.mark.parametrize(
    "mutation",
    [
        "incident_environment",
        "topology_environment",
        "source_environment",
        "record_environment",
        "evidence_source",
        "evidence_resource",
        "duplicate_evidence",
        "missing_finding_evidence",
        "missing_recommendation_finding",
        "missing_root_cause",
        "supported_without_evidence",
        "rejected_without_evidence",
        "confidence_reference",
        "timeline_reference",
        "executable_recommendation",
    ],
)
def test_bundle_rejects_invalid_lineage(bundle_data, mutation):
    data = bundle_data
    if mutation == "incident_environment":
        data["incident"]["environment_id"] = "other"
    elif mutation == "topology_environment":
        data["topology"] = {"environment_id": "other", "nodes": []}
    elif mutation == "source_environment":
        data["incident"]["source"]["environment_id"] = "other"
    elif mutation == "record_environment":
        data["findings"][0]["environment_id"] = "other"
    elif mutation == "evidence_source":
        data["evidence"][0]["source"]["environment_id"] = "other"
    elif mutation == "evidence_resource":
        data["evidence"][0]["resource_id"] = "missing"
    elif mutation == "duplicate_evidence":
        data["evidence"].append(copy.deepcopy(data["evidence"][0]))
    elif mutation == "missing_finding_evidence":
        data["findings"][0]["evidence_ids"] = ["missing"]
    elif mutation == "missing_recommendation_finding":
        data["recommendations"][0]["finding_ids"] = ["missing"]
    elif mutation == "missing_root_cause":
        data["incident"]["root_cause_finding_id"] = "missing"
    elif mutation == "supported_without_evidence":
        data["hypotheses"][0]["supporting_evidence"] = []
    elif mutation == "rejected_without_evidence":
        data["hypotheses"][0]["status"] = "rejected"
    elif mutation == "confidence_reference":
        data["evidence"][0]["confidence"]["contradicting_evidence"] = ["missing"]
    elif mutation == "timeline_reference":
        data["timeline"][0]["evidence_ids"] = ["missing"]
    else:
        data["recommendations"][0]["executable"] = True
    with pytest.raises(ValidationError):
        IncidentBundle.model_validate(data)


def test_resource_extras_and_assignment_rejected():
    resource = Resource(id="r", environment_id="demo", kind="service", name="test", provider="fake")
    with pytest.raises(ValidationError):
        resource.name = "changed"
    with pytest.raises(ValidationError):
        Resource.model_validate({**resource.model_dump(), "vendor_specific": "value"})
