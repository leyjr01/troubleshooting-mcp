import asyncio

import pytest

from agt_mcp.core.errors import AuthorizationError, SanitizationError
from agt_mcp.correlation.models import CorrelatedKnowledge, RelationType
from agt_mcp.rag.contracts import RetrievalQuery
from agt_mcp.services.correlation_providers import HistoryBridge, KnowledgeBridge
from tests.correlation_support import References, engine, query, snapshot
from tests.knowledge_support import ready


def setup(tmp_path, version="2.16"):
    runtime, execution, _ = ready(tmp_path)
    snap = snapshot().model_copy(update={"gateway_type": "threescale", "version": version})
    subject = engine(snap, max_candidates=30)
    subject.knowledge = KnowledgeBridge(runtime.knowledge, 2)
    subject.history = HistoryBridge(runtime.knowledge, 2)
    return subject, runtime, execution


def test_two_historical_503_causes_never_become_runtime_evidence(tmp_path):
    subject, _, execution = setup(tmp_path)
    result = asyncio.run(
        subject.correlate(
            query(symptom="APIcast 503", include_knowledge=True, include_history=True), execution
        )
    )
    assert len(result.historical_matches) == 2
    assert {h.incident.id for h in result.historical_matches} == {"INC-001", "INC-002"}
    assert {h.incident.historical_root_cause for h in result.historical_matches} == {
        "Missing endpoint",
        "Backend TLS mismatch",
    }
    assert all(
        h.incident.historical_remediation and not h.runtime_support
        for h in result.historical_matches
    )
    historical_ids = {h.id for h in result.historical_matches}
    assert historical_ids.isdisjoint(e.id for s in result.evidence_sets for e in s.evidence)
    assert all(
        not c.supporting_evidence and c.confidence.level == "low"
        for c in result.candidates
        if c.relation_type == RelationType.HISTORICAL_SIMILARITY
    )
    assert "FAKE-DB-CREDENTIAL" not in result.model_dump_json()


@pytest.mark.parametrize("version", ["2.16", "2.16.1", None, "UNKNOWN"])
def test_version_aware_official_reference_and_unknown_warning(tmp_path, version):
    subject, runtime, execution = setup(tmp_path, version)
    # The provider search sees both indexed versions; compatible filtering must select 2.16.
    store = runtime.knowledge.store
    old = next(iter(store.source_records("official").values()))
    chunk, vector = old
    old_chunk = chunk.model_copy(
        update={
            "id": "old-version",
            "metadata": chunk.metadata.model_copy(update={"product_version": "2.15"}),
        }
    )
    records = dict(store.source_records("official"))
    records[old_chunk.id] = old_chunk, vector
    store.replace_source("official", records)
    result = asyncio.run(
        subject.correlate(query(symptom="3scale Redis", include_knowledge=True), execution)
    )
    official = [
        k
        for k in result.knowledge
        if k.reference.chunk.source_type.value == "OFFICIAL_DOCUMENTATION"
    ]
    assert official
    if version in {"2.16", "2.16.1"}:
        assert all(
            k.reference.chunk.metadata.product_version == "2.16" and k.version_compatible
            for k in official
        )
    else:
        assert "version_compatibility_unconfirmed" in {w.code for w in result.warnings}
        assert all(k.version_compatible is None for k in official)


def test_malicious_runbook_is_only_untrusted_reference(tmp_path):
    subject, runtime, execution = setup(tmp_path)
    matches = asyncio.run(
        runtime.knowledge.search(
            RetrievalQuery(text="APIcast untrusted instructions", limit=10), execution
        )
    )
    malicious = next(r for r in matches.results if "kubectl delete" in r.chunk.text)
    subject.knowledge = References(
        (CorrelatedKnowledge(id=malicious.chunk.id, reference=malicious),)
    )
    result = asyncio.run(subject.correlate(query(include_knowledge=True), execution))
    assert result.knowledge[0].reference.chunk.trust == "untrusted_data"
    assert "ghp_FAKE" not in result.model_dump_json()
    assert all("kubectl" not in reason for c in result.candidates for reason in c.reasons)
    assert subject.provider.calls == 1


def test_unavailable_history_index_degrades_only_enrichment(tmp_path):
    subject, runtime, execution = setup(tmp_path)
    runtime.knowledge.failures.add("incidents")
    result = asyncio.run(subject.correlate(query(include_history=True), execution))
    assert result.candidates and result.evidence_sets[0].evidence
    assert "history_unavailable" in {w.code for w in result.warnings}


@pytest.mark.parametrize(
    "case", ["environment", "source", "text", "incident_environment", "incident_secret"]
)
def test_untrusted_reference_scope_or_credentials_rejected(tmp_path, case):
    subject, runtime, execution = setup(tmp_path)
    matches = asyncio.run(
        subject.history.retrieve(
            subject.context(query(), execution), subject.provider.value, execution
        )
    )
    item = matches[0]
    chunk = item.reference.chunk
    if case == "environment":
        chunk = chunk.model_copy(update={"environment_id": "prod"})
    elif case == "source":
        chunk = chunk.model_copy(
            update={"source": chunk.source.model_copy(update={"environment_id": "prod"})}
        )
    elif case == "text":
        chunk = chunk.model_copy(update={"text": "password: EXPOSE-ME"})
    elif case == "incident_environment":
        item = item.model_copy(
            update={"incident": item.incident.model_copy(update={"environment_id": "prod"})}
        )
    else:
        item = item.model_copy(
            update={
                "incident": item.incident.model_copy(
                    update={"historical_root_cause": "password: EXPOSE-ME"}
                )
            }
        )
    item = item.model_copy(update={"reference": item.reference.model_copy(update={"chunk": chunk})})
    subject.history = References((item,))
    with pytest.raises(
        SanitizationError if case in {"text", "incident_secret"} else AuthorizationError
    ):
        asyncio.run(subject.correlate(query(include_history=True), execution))


def test_history_without_structured_incident_stays_reference(tmp_path):
    subject, runtime, execution = setup(tmp_path)
    runtime.knowledge.documents.clear()
    matches = asyncio.run(
        subject.history.retrieve(
            subject.context(query(), execution), subject.provider.value, execution
        )
    )
    assert matches and all(m.incident is None and not m.runtime_support for m in matches)
