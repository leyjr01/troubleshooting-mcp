"""Local composition reads declared mapping files, never repositories or networks."""

from pathlib import Path

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.errors import ConfigurationError
from agt_mcp.knowledge.incidents import LocalIncidentSource
from agt_mcp.knowledge.pipeline import SafeDocumentNormalizer, StructureAwareChunker
from agt_mcp.knowledge.security import KnowledgeRedactor
from agt_mcp.knowledge.sources import CuratedLocalSource, GitKnowledgeSource, KnowledgeSourceAdapter
from agt_mcp.mapping.schema import load_mapping
from agt_mcp.rag.local import DeterministicFakeEmbeddingProvider, InMemoryVectorStore
from agt_mcp.services.knowledge import KnowledgeService


def build_knowledge(configuration: Configuration) -> KnowledgeService:
    sources: dict[str, KnowledgeSourceAdapter] = {}
    limits = configuration.knowledge_limits
    for config in configuration.knowledge_sources:
        if not config.enabled:
            continue
        # Remote credentials are reserved references; no second credential resolver.
        if config.credentials:
            raise ConfigurationError()
        if config.type == "git":
            sources[config.id] = GitKnowledgeSource(config, limits)
        elif config.type == "incident-local":
            if not config.mapping_path:
                raise ConfigurationError()
            source = LocalIncidentSource(config, limits)
            source.mapping = load_mapping(Path(config.mapping_path))
            if source.mapping.source.datasource != config.id:
                raise ConfigurationError()
            sources[config.id] = source
        else:
            sources[config.id] = CuratedLocalSource(config, limits)
    return KnowledgeService(
        sources,
        limits,
        SafeDocumentNormalizer(limits, KnowledgeRedactor()),
        StructureAwareChunker(limits),
        DeterministicFakeEmbeddingProvider(),
        InMemoryVectorStore(),
    )
