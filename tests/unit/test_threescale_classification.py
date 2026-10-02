import copy

import pytest

from agt_mcp.gateways.threescale.classifier import ThreeScaleComponentClassifier
from agt_mcp.gateways.threescale.models import ComponentType as C
from agt_mcp.gateways.threescale.models import Presence
from tests.threescale_support import ROLES, config, healthy_resources, snapshot


def classify(resources=None, configuration=None, **kwargs):
    snap, _ = snapshot(resources, configuration, **kwargs)
    return ThreeScaleComponentClassifier(snap).classify()


@pytest.mark.parametrize("role", ROLES)
def test_owned_component_has_evidence_and_high_confidence(role):
    installation = classify()[0]
    component = next(
        c for c in installation.components if c.type.value == role.upper().replace("-", "_")
    )
    assert component.status == Presence.PRESENT
    assert component.confidence.level.value == "high"
    assert component.evidence and component.runtime_resources
    assert all(e.provenance.environment_id == "dev" for e in component.evidence)
    assert installation.version == "2.16"
    assert installation.operator_managed


@pytest.mark.parametrize(
    "name", ["backend-payments", "backend-listener", "system-app", "apicast-production"]
)
def test_name_alone_never_classifies(name):
    resources = healthy_resources()
    for r in resources:
        if r["kind"] == "Deployment":
            r["metadata"].pop("labels", None)
            r["metadata"].pop("ownerReferences", None)
    resources[-1]["metadata"]["name"] = name
    installation = classify(resources)[0]
    assert all(not c.runtime_resources for c in installation.components if c.type != C.APIMANAGER)


def test_label_spoof_cannot_produce_high_confidence():
    resources = [r for r in healthy_resources() if r["kind"] != "APIManager"]
    installation = classify(resources)[0]
    assert not installation.operator_managed and installation.apimanager is None
    assert all(c.confidence.level.value != "high" for c in installation.components)
    assert any(w.code == "ambiguous_classification" for w in installation.warnings)


@pytest.mark.parametrize(
    "version,warning",
    [
        (None, "version_unknown"),
        ("2.15", "unsupported_version_profile"),
        ("2.14", "unsupported_version_profile"),
        ("3.0", "unsupported_version_profile"),
        ("2.16.1", None),
    ],
)
def test_version_profiles_are_not_assumed(version, warning):
    resources = healthy_resources()
    resources[0]["metadata"]["labels"] = (
        {} if version is None else {"app.kubernetes.io/version": version}
    )
    installation = classify(resources)[0]
    assert installation.version == (version or "UNKNOWN")
    if warning:
        assert any(w.code == warning for w in installation.warnings)
        assert installation.version_profile == "UNKNOWN"
    else:
        assert installation.version_profile == "2.16"


@pytest.mark.parametrize(
    "kind", [C.SYSTEM_DATABASE, C.BACKEND_REDIS_STORAGE, C.BACKEND_REDIS_QUEUES, C.SYSTEM_REDIS]
)
def test_external_dependencies_do_not_require_deployments(kind):
    installation = classify()[0]
    component = next(c for c in installation.components if c.type == kind)
    assert component.status == Presence.EXTERNAL
    dependency = next(d for d in installation.dependencies if d.type == kind)
    assert dependency.endpoint_status == "unresolved" and dependency.secret_references
    assert not any(
        w.code == "expected_component_not_observed" and w.resource_id == component.id
        for w in installation.warnings
    )


def test_zync_disabled_and_absent_is_not_a_failure():
    resources = [r for r in healthy_resources() if not r["metadata"]["name"].startswith("zync")]
    resources[0]["spec"]["zync"]["enabled"] = False
    installation = classify(resources)[0]
    assert all(
        c.status == Presence.DISABLED and c.expected is False
        for c in installation.components
        if c.type in {C.ZYNC, C.ZYNC_QUE, C.ZYNC_DATABASE}
    )


def test_multiple_installations_cannot_mix_namespaces():
    resources = healthy_resources("one") + healthy_resources("two")
    installations = classify(resources, config(("one", "two")))
    assert len(installations) == 2
    assert set(installations[0].runtime_resources).isdisjoint(installations[1].runtime_resources)
    assert set(c.id for c in installations[0].components).isdisjoint(
        c.id for c in installations[1].components
    )


def test_external_apicast_is_associated_with_the_apimanager_installation():
    resources = [
        resource
        for resource in healthy_resources("apim")
        if not resource["metadata"]["name"].startswith("apicast-")
    ]
    resources.extend(
        resource
        for resource in healthy_resources("apicast")
        if resource["metadata"]["name"].startswith("apicast-")
    )
    snap, _ = snapshot(resources, config(("apim", "apicast")))

    installations = ThreeScaleComponentClassifier(snap, primary_namespace="apim").classify()

    assert len(installations) == 1
    installation = installations[0]
    assert installation.namespace == "apim"
    runtime = {node.id: node for node in snap.topology.nodes}
    apicast_components = [
        component
        for component in installation.components
        if component.type in {C.APICAST_STAGING, C.APICAST_PRODUCTION}
    ]
    assert len(apicast_components) == 2
    assert all(component.status == Presence.PRESENT for component in apicast_components)
    assert all(
        runtime[resource_id].namespace == "apicast"
        for component in apicast_components
        for resource_id in component.runtime_resources
    )


def test_external_apicast_is_not_guessed_when_multiple_apimanagers_exist():
    resources = healthy_resources("one") + healthy_resources("two")
    resources.extend(
        resource
        for resource in healthy_resources("shared-apicast")
        if resource["metadata"]["name"].startswith("apicast-")
    )
    snap, _ = snapshot(resources, config(("one", "two", "shared-apicast")))

    installations = ThreeScaleComponentClassifier(snap).classify()
    roots = [installation for installation in installations if installation.apimanager]
    runtime = {node.id: node for node in snap.topology.nodes}

    assert len(roots) == 2
    assert all(
        runtime[resource_id].namespace != "shared-apicast"
        for installation in roots
        for resource_id in installation.runtime_resources
    )

    selected = ThreeScaleComponentClassifier(snap, primary_namespace="one").classify()
    assert len(selected) == 1
    assert selected[0].namespace == "one"
    assert all(
        runtime[resource_id].namespace != "shared-apicast"
        for resource_id in selected[0].runtime_resources
    )


def test_partial_rbac_does_not_assert_absence():
    from agt_mcp.core.errors import AuthorizationError

    installation = classify(
        forbidden={"Route": AuthorizationError, "Deployment": AuthorizationError}
    )[0]
    assert installation.partial
    assert any(w.code == "runtime_resource_forbidden" for w in installation.warnings)
    assert not any(c.status == Presence.ABSENT_EXPECTED for c in installation.components)


def test_inconsistent_labels_remain_unknown():
    resources = healthy_resources()
    workload = next(r for r in resources if r["kind"] == "Deployment")
    workload["metadata"]["labels"]["app.kubernetes.io/component"] = "backend-worker"
    installation = classify(resources)[0]
    assert any(c.type == C.UNKNOWN for c in installation.components)


def test_expected_component_absence_requires_complete_snapshot():
    resources = [
        r for r in healthy_resources() if not r["metadata"]["name"].startswith("backend-worker")
    ]
    installation = classify(resources)[0]
    assert (
        next(c for c in installation.components if c.type == C.BACKEND_WORKER).status
        == Presence.ABSENT_EXPECTED
    )


def test_profile_defaults_are_distinct_from_explicit_configuration():
    resources = healthy_resources()
    resources[0]["spec"].pop("externalComponents")
    installation = classify(resources)[0]
    component = next(c for c in installation.components if c.type == C.SYSTEM_DATABASE)
    assert component.status == Presence.EXTERNAL
    assert component.evidence[0].signal == "version-profile-rule"


def test_no_installation_for_unrelated_workload():
    resources = healthy_resources()
    assert classify([copy.deepcopy(resources[-1])]) == ()


def test_spoofed_member_cannot_inherit_high_confidence():
    resources = healthy_resources()
    resources[-1]["metadata"]["labels"] = {
        "app": "3scale-api-management",
        "deployment": "backend-listener",
    }
    component = next(c for c in classify(resources)[0].components if c.type == C.BACKEND_LISTENER)
    assert component.confidence.level.value == "medium"


def test_external_zync_database_and_configuration_provenance():
    resources = [
        r for r in healthy_resources() if not r["metadata"]["name"].startswith("zync-database")
    ]
    resources[0]["spec"]["externalComponents"]["zync"] = {"database": True}
    component = next(c for c in classify(resources)[0].components if c.type == C.ZYNC_DATABASE)
    assert component.status == Presence.EXTERNAL
    assert component.evidence[0].provenance.source_reference.endswith(
        "#spec.externalComponents.zync.database"
    )


def test_owned_version_label_preserves_actual_source():
    resources = healthy_resources()
    resources[0]["metadata"]["labels"] = {}
    workload = next(r for r in resources if r["kind"] == "Deployment")
    workload["metadata"]["labels"]["app.kubernetes.io/version"] = "2.16"
    installation = classify(resources)[0]
    assert installation.version == "2.16"
    evidence = next(e for e in installation.evidence if e.signal == "owned-resource-version-label")
    assert evidence.resource_id != installation.apimanager


def test_profile_source_is_auditable():
    resources = healthy_resources()
    resources[0]["spec"].pop("externalComponents")
    component = next(c for c in classify(resources)[0].components if c.type == C.SYSTEM_DATABASE)
    assert component.evidence[0].provenance.source_id == "threescale-version-profile"
    assert "2.16" in component.evidence[0].provenance.source_reference
