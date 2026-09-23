import asyncio

import pytest

from agt_mcp.configuration.knowledge import KnowledgeLimits
from agt_mcp.core.errors import ConfigurationError
from agt_mcp.knowledge.models import SourceType
from agt_mcp.rag.contracts import RetrievalQuery
from agt_mcp.rag.local import DeterministicFakeEmbeddingProvider, InMemoryVectorStore
from tests.knowledge_support import ready


@pytest.mark.parametrize(
    "filters",
    [
        {"system": "payments"},
        {"application": "missing"},
        {"gateway_type": "missing"},
        {"product_version": "2.16"},
        {"document_type": "RUNBOOK"},
        {"tags": ["tls"]},
        {"environment": "demo"},
        {"product": "3scale"},
    ],
)
def test_retrieval_filters(tmp_path, filters):
    runtime, context, _ = ready(tmp_path)

    async def run():
        result = await runtime.knowledge.search(
            RetrievalQuery(text="APIcast Redis payments", filters=filters), context
        )
        for match in result.results:
            for key, value in filters.items():
                observed = getattr(match.chunk.metadata, key)
                assert set(value) <= set(observed) if key == "tags" else observed == value

    asyncio.run(run())


def test_source_category_dedup_and_history_not_cause(tmp_path):
    runtime, context, _ = ready(tmp_path)

    async def run():
        query = RetrievalQuery(text="APIcast 503", source_types=(SourceType.HISTORICAL_INCIDENT,))
        results = await runtime.knowledge.search(query, context)
        assert len(results.results) == 2
        assert all(r.match_kind == "similar prior incident" for r in results.results)
        assert "Missing endpoint" in results.model_dump_json()
        assert "Backend TLS mismatch" in results.model_dump_json()
        assert "diagnostic_confidence" not in results.model_dump_json()
        official = await runtime.knowledge.search(
            RetrievalQuery(text="Redis", repository_ids=("official",)), context
        )
        assert official.results
        assert all(
            r.chunk.source_type == SourceType.OFFICIAL_DOCUMENTATION for r in official.results
        )
        assert len({r.chunk.document_id for r in results.results}) == len(results.results)

    asyncio.run(run())


def test_retrieval_byte_cap_and_no_sources(tmp_path):
    runtime, context, _ = ready(tmp_path)

    async def run():
        runtime.knowledge.limits = KnowledgeLimits(max_result_bytes=256)
        result = await runtime.knowledge.search(RetrievalQuery(text="APIcast"), context)
        assert result.truncated and not result.results
        runtime.knowledge.sources.clear()
        assert not (await runtime.knowledge.search(RetrievalQuery(text="APIcast"), context)).results

    asyncio.run(run())


def test_vectors_deterministic_and_invalid_storage(tmp_path):
    runtime, context, _ = ready(tmp_path)
    provider = DeterministicFakeEmbeddingProvider()
    vectors = asyncio.run(provider.embed(("Redis storage", "Redis storage", ""), context))
    assert vectors[0] == vectors[1]
    assert all(v == 0 for v in vectors[2])
    store = InMemoryVectorStore()
    chunk, vector = next(iter(runtime.knowledge.store.source_records("internal").values()))
    with pytest.raises(ConfigurationError):
        store.replace_source("wrong", {chunk.id: (chunk, vector)})
    with pytest.raises(ConfigurationError):
        store.replace_source("internal", {chunk.id: (chunk, (float("nan"),))})
    store.replace_source("internal", {chunk.id: (chunk, vector)})
    with pytest.raises(ConfigurationError):
        store.ranked((1.0,), RetrievalQuery(text="Redis"), context)
    assert not store.ranked(tuple(0.0 for _ in vector), RetrievalQuery(text="Redis"), context)
