import asyncio
from unittest.mock import AsyncMock

import pytest

from agt_mcp.configuration.knowledge import KnowledgeLimits
from agt_mcp.core.errors import AuthorizationError, ConfigurationError, ResourceNotFound
from tests.knowledge_support import commit, ready, setup


def test_git_snapshot_changes_and_scope(tmp_path):
    runtime, context, root = setup(tmp_path)
    source = runtime.knowledge.sources["internal"]

    async def run():
        before = await source.snapshot(context)
        assert len(await source.list_documents(context)) == 9
        assert (await source.get_document("systems/notes.txt", context)).revision == before.revision
        with pytest.raises(ResourceNotFound):
            await source.get_document("../missing", context)
        (root / "systems/notes.txt").write_text("changed", encoding="utf-8")
        # Uncommitted work cannot change an authoritative Git snapshot.
        assert (await source.get_document("systems/notes.txt", context)).content != b"changed"
        (root / "systems/new.txt").write_text("new", encoding="utf-8")
        (root / "systems/details.json").unlink()
        commit(root, "incremental")
        changes = await source.get_changes(before, context)
        assert changes.new == ("systems/new.txt",)
        assert changes.changed == ("systems/notes.txt",)
        assert changes.deleted == ("systems/details.json",)
        assert len(changes.unchanged) == 7
        assert await source.health(context) == "HEALTHY"
        source.config = source.config.model_copy(
            update={"subpath": "systems", "include": ("notes.txt",)}
        )
        assert await source.list_documents(context) == ("systems/notes.txt",)
        scoped = runtime.knowledge.sources["incidents"]
        with pytest.raises(AuthorizationError):
            await scoped.snapshot(context.model_copy(update={"environment_id": "prod"}))

    asyncio.run(run())


@pytest.mark.parametrize("case", ["missing", "branch", "oversized", "count"])
def test_git_source_failures(tmp_path, case):
    runtime, context, root = setup(tmp_path)
    source = runtime.knowledge.sources["internal"]
    if case == "missing":
        source.config = source.config.model_copy(update={"local_path": str(root / "missing")})
    elif case == "branch":
        source.config = source.config.model_copy(update={"branch": "missing"})
    elif case == "oversized":
        source.limits = KnowledgeLimits(max_document_bytes=128)
    else:
        source.limits = KnowledgeLimits(max_documents=1)
    with pytest.raises(ConfigurationError):
        asyncio.run(source.snapshot(context))


def test_git_missing_executable_and_malformed_revision(tmp_path, monkeypatch):
    runtime, context, _ = setup(tmp_path)
    source = runtime.knowledge.sources["internal"]
    monkeypatch.setattr("agt_mcp.knowledge.sources.shutil.which", lambda _: None)
    with pytest.raises(ConfigurationError):
        asyncio.run(source.revision(context))
    source._git = AsyncMock(return_value=b"invalid")
    with pytest.raises(ConfigurationError):
        asyncio.run(source.revision(context))


@pytest.mark.parametrize("case", ["missing", "oversized", "count", "enumeration"])
def test_curated_source_limits(tmp_path, case):
    runtime, context, _ = setup(tmp_path)
    source = runtime.knowledge.sources["official"]
    from pathlib import Path

    root = Path(source.config.local_path)
    if case == "missing":
        source.config = source.config.model_copy(update={"local_path": str(root / "missing")})
    elif case == "oversized":
        (root / "big.md").write_text("x" * 300)
        source.limits = KnowledgeLimits(max_document_bytes=128)
    elif case == "count":
        (root / "other.md").write_text("other")
        source.limits = KnowledgeLimits(max_documents=1)
    else:
        for index in range(12):
            (root / f"{index}.bin").write_text("ignored")
        source.limits = KnowledgeLimits(max_documents=1)
    with pytest.raises(ConfigurationError):
        asyncio.run(source.snapshot(context))


def test_health_atomic_failure_and_metadata(tmp_path):
    runtime, context, _ = ready(tmp_path)
    service = runtime.knowledge

    async def run():
        metadata = service.document_metadata("internal", "runbooks/apicast-503.md", context)
        assert metadata.text == ""
        with pytest.raises(ResourceNotFound):
            service.document_metadata("internal", "missing", context)
        with pytest.raises(ResourceNotFound):
            await service.health("missing", context)
        previous = service.manifests["internal"]
        records = service.store.source_records("internal")
        old_limits = service.limits
        service.limits = KnowledgeLimits(max_total_chunks_per_ingestion=1)
        with pytest.raises(ConfigurationError):
            await service.refresh("internal", context)
        assert service.manifests["internal"] == previous
        assert service.store.source_records("internal") == records
        assert (await service.health("internal", context)).status == "DEGRADED"
        service.limits = old_limits
        await service.refresh("internal", context)
        assert (await service.health("internal", context)).status == "HEALTHY"
        service.sources["internal"].revision = AsyncMock(side_effect=ConfigurationError())
        assert (await service.health("internal", context)).status == "UNAVAILABLE"

    asyncio.run(run())


def test_not_indexed_and_schema(tmp_path):
    runtime, context, _ = setup(tmp_path)

    async def run():
        assert (await runtime.knowledge.health("internal", context)).status == "NOT_INDEXED"
        schema = await runtime.knowledge.sources["incidents"].inspect_datasource_schema(context)
        assert schema.tables[0].name == "INCIDENT_HISTORY"
        assert "INCIDENT_ID" in {c.name for c in schema.tables[0].columns}
        assert "INC-001" not in schema.model_dump_json()

    asyncio.run(run())
