import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from agt_mcp.configuration.knowledge import KnowledgeLimits, KnowledgeSourceConfig
from agt_mcp.core.errors import ConfigurationError
from agt_mcp.knowledge.models import SourceDocument
from agt_mcp.knowledge.pipeline import SafeDocumentNormalizer, StructureAwareChunker
from agt_mcp.knowledge.security import KnowledgeRedactor
from agt_mcp.rag.contracts import RetrievalQuery
from tests.knowledge_support import commit, ready


def normalize(text, path="runbooks/test.md", limits=None, config=None):
    limits = limits or KnowledgeLimits()
    raw = SourceDocument(
        path=path, content=text.encode(), revision="a" * 40, retrieved_at=datetime.now(UTC)
    )
    return SafeDocumentNormalizer(limits, KnowledgeRedactor()).normalize(
        raw,
        config or KnowledgeSourceConfig(id="source", type="git", local_path="unused"),
    )


@pytest.mark.parametrize("extension", ["md", "txt", "yaml", "yml", "json"])
def test_supported_formats(extension):
    text = '{"system":"payments"}' if extension == "json" else "system: payments"
    document = normalize(text, f"architecture/test.{extension}")
    assert document.source.content_sha256
    assert document.source.source_type == "ARCHITECTURE"
    assert document.trust == "untrusted_data"


def test_structure_and_identity():
    document = normalize("# Main\nIntroduction\n## Nested\n" + "operational detail " * 30)
    limits = KnowledgeLimits(max_chunk_size=100, overlap=10, minimum_size=20)
    chunks = StructureAwareChunker(limits).chunk(document, "a" * 40)
    assert len(chunks) > 2
    assert any(c.source.section == "Main / Nested" for c in chunks)
    assert all(len(c.text) <= 100 for c in chunks)
    again = StructureAwareChunker(limits).chunk(document, "b" * 40)
    assert [c.id for c in chunks] == [c.id for c in again]
    assert all(c.revision == "b" * 40 for c in again)


def test_small_sections_and_fenced_headings():
    doc = normalize("# Main\n```\n# code\n```\n## Next\nshort")
    chunks = StructureAwareChunker(KnowledgeLimits()).chunk(doc, "revision")
    assert len(chunks) == 2
    assert "# code" in chunks[0].text
    assert StructureAwareChunker(KnowledgeLimits()).chunk(normalize("  "), "revision") == ()


@pytest.mark.parametrize(
    "text,path",
    [
        ("!!python/object/apply:os.system [echo unsafe]", "x.yaml"),
        ("a: &value [one]\nb: *value", "x.yml"),
        ("a: 1\na: 2", "x.yaml"),
        ("[invalid", "x.json"),
        ("---\na: 1", "x.md"),
        ("---\n[one, two]\n---\nbody", "x.md"),
        ("\x00body", "x.txt"),
    ],
)
def test_unsafe_or_malformed_document_rejected(text, path):
    with pytest.raises(ConfigurationError):
        normalize(text, path)


def test_frontmatter_scope_and_metadata():
    doc = normalize(
        "---\nenvironment: prod\nsystem: payments\ntags: [tls]\nignored: secret\n---\n# title\nbody"
    )
    assert doc.source.environment_id == "prod"
    assert doc.source.metadata.tags == ("tls",)
    assert "ignored" not in doc.model_dump_json()
    cfg = KnowledgeSourceConfig(
        id="scoped", type="git", local_path="unused", metadata={"environment": "demo"}
    )
    with pytest.raises(ConfigurationError):
        normalize("---\nenvironment: prod\n---\nbody", config=cfg)


def test_document_and_chunk_limits():
    with pytest.raises(ConfigurationError):
        normalize("x" * 129, limits=KnowledgeLimits(max_document_bytes=128))
    document = normalize("detail " * 100)
    with pytest.raises(ConfigurationError):
        StructureAwareChunker(
            KnowledgeLimits(max_chunk_size=64, overlap=0, max_chunks_per_document=1)
        ).chunk(document, "revision")


def test_incremental_git_and_rebuild(tmp_path):
    runtime, context, root = ready(tmp_path)
    service = runtime.knowledge

    async def run():
        original = service.manifests["internal"]
        assert original.branch == "main"
        service.embedding.embed = AsyncMock(wraps=service.embedding.embed)
        assert (await service.refresh("internal", context)).unchanged == 9
        service.embedding.embed.assert_not_awaited()
        old_ids = set(service.store.source_records("internal"))
        (root / "systems/notes.txt").write_text("changed APIcast notes", encoding="utf-8")
        (root / "systems/new.txt").write_text("new APIcast document", encoding="utf-8")
        (root / "architecture/payments.md").unlink()
        commit(root, "change add delete")
        assert (await service.health("internal", context)).status == "STALE"
        result = await service.refresh("internal", context)
        assert (result.new, result.changed, result.deleted, result.unchanged) == (1, 1, 1, 7)
        assert service.manifests["internal"].source_revision != original.source_revision
        assert old_ids - set(service.store.source_records("internal"))
        assert (await service.health("internal", context)).status == "HEALTHY"
        expected = set(service.store.source_records("internal"))
        await service.refresh("internal", context, rebuild=True)
        assert expected == set(service.store.source_records("internal"))
        assert (await service.refresh("incidents", context)).unchanged == 2
        results = await service.search(RetrievalQuery(text="APIcast"), context)
        assert results.results
        assert all(
            r.chunk.source.document_id and r.chunk.source.content_sha256 for r in results.results
        )

    asyncio.run(run())
