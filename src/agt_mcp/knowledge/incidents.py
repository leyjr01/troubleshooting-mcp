"""Local incident rows and schema inspection; no database connections or SQL."""

import json
from typing import Protocol

from agt_mcp.core.errors import ConfigurationError
from agt_mcp.core.models import Provenance
from agt_mcp.core.operations import Column, OperationContext, SchemaDescription, SchemaTable
from agt_mcp.knowledge.models import KnowledgeSource, SourceDocument, SourceSnapshot
from agt_mcp.knowledge.pipeline import checksum
from agt_mcp.knowledge.sources import CuratedLocalSource
from agt_mcp.mapping.engine import IncidentMappingEngine
from agt_mcp.mapping.schema import MappingSpec


class IncidentKnowledgeSource(Protocol):
    async def snapshot(self, context: OperationContext) -> SourceSnapshot: ...

    async def inspect_datasource_schema(self, context: OperationContext) -> SchemaDescription: ...


class LocalIncidentSource(CuratedLocalSource):
    mapping: MappingSpec

    def source_metadata(self) -> KnowledgeSource:
        metadata = super().source_metadata()
        return metadata.model_copy(
            update={"capabilities": (*metadata.capabilities, "schema.inspect")}
        )

    async def inspect_datasource_schema(self, context: OperationContext) -> SchemaDescription:
        self.check_scope(context)
        return SchemaDescription(
            tables=(
                SchemaTable(
                    schema_name=self.mapping.source.schema_name or "local",
                    name=self.mapping.source.table,
                    columns=tuple(
                        Column(name=name, data_type="mapped scalar", nullable=True)
                        for name in sorted({m.column for m in self.mapping.fields.values()})
                    ),
                ),
            )
        )

    async def snapshot(self, context: OperationContext) -> SourceSnapshot:
        source = await super().snapshot(context)
        documents = []
        mapper = IncidentMappingEngine()
        for document in source.documents:
            try:
                rows = json.loads(document.content)
            except (ValueError, UnicodeError):
                raise ConfigurationError() from None
            if not isinstance(rows, list) or len(rows) > self.limits.max_documents:
                raise ConfigurationError()
            for row in rows:
                if not isinstance(row, dict):
                    raise ConfigurationError()
                safe = mapper.redactor.redact(json.dumps(row, sort_keys=True))
                provenance = Provenance(
                    source_id=self.config.id,
                    environment_id=self.config.metadata.environment,
                    retrieved_at=document.retrieved_at,
                    source_reference=f"{self.config.id}/{document.path}",
                    content_sha256=checksum(safe),
                )
                incident = mapper.map_record(row, self.mapping, provenance)
                documents.append(
                    SourceDocument(
                        path=f"{document.path}/{incident.id}.json",
                        content=incident.model_dump_json(exclude={"source"}).encode(),
                        revision=source.revision,
                        retrieved_at=document.retrieved_at,
                        incident=incident,
                    )
                )
                if len(documents) > self.limits.max_documents:
                    raise ConfigurationError()
        if len({d.path for d in documents}) != len(documents):
            raise ConfigurationError()
        return SourceSnapshot(revision=source.revision, documents=tuple(documents))
