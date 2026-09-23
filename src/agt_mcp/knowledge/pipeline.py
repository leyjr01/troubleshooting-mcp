"""Replaceable normalization and structure-aware deterministic chunking stages."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Literal, Protocol, cast
from urllib.parse import unquote, urlsplit

import yaml
from pydantic import ValidationError

from agt_mcp.configuration.knowledge import KnowledgeLimits, KnowledgeSourceConfig
from agt_mcp.configuration.loader import UniqueSafeLoader
from agt_mcp.core.errors import ConfigurationError, SanitizationError
from agt_mcp.knowledge.models import (
    KnowledgeDocument,
    KnowledgeMetadata,
    KnowledgeProvenance,
    SourceDocument,
    SourceType,
)
from agt_mcp.knowledge.security import KnowledgeRedactor
from agt_mcp.rag.contracts import KnowledgeChunk


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_yaml(text: str) -> object:
    try:
        if any(
            isinstance(t, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken))
            for t in yaml.scan(text)
        ):
            raise ConfigurationError()
        # Restrictive SafeLoader subclass: rejects duplicate keys and has no custom tags.
        return yaml.load(text, Loader=UniqueSafeLoader)  # nosec B506
    except (yaml.YAMLError, RecursionError):
        raise ConfigurationError() from None


class DocumentNormalizer(Protocol):
    def normalize(
        self, raw: SourceDocument, config: KnowledgeSourceConfig
    ) -> KnowledgeDocument: ...


class SafeDocumentNormalizer:
    def __init__(self, limits: KnowledgeLimits, redactor: KnowledgeRedactor) -> None:
        self.limits, self.redactor = limits, redactor

    def normalize(self, raw: SourceDocument, config: KnowledgeSourceConfig) -> KnowledgeDocument:
        if len(raw.content) > self.limits.max_document_bytes:
            raise ConfigurationError()
        path = raw.path
        if self.redactor.redact(path) != path or any(ord(c) < 32 for c in path):
            raise SanitizationError()
        for reference in (config.repository_url, config.source_url):
            if reference:
                parsed = urlsplit(reference)
                parts = [parsed.hostname or "", *unquote(parsed.path).split("/")]
                if any(self.redactor.redact(part) != part for part in parts):
                    raise SanitizationError()
        try:
            text = raw.content.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
            if "\x00" in text:
                raise ConfigurationError()
            metadata = config.metadata
            suffix = PurePosixPath(path).suffix.lower()
            if suffix == ".md" and text.startswith("---\n"):
                front, separator, text = text[4:].partition("\n---\n")
                if not separator or len(front) > 8192:
                    raise ConfigurationError()
                fields = safe_yaml(front)
                if not isinstance(fields, dict):
                    raise ConfigurationError()
                allowed = {k: v for k, v in fields.items() if k in KnowledgeMetadata.model_fields}
                metadata = KnowledgeMetadata.model_validate({**metadata.model_dump(), **allowed})
                if (
                    config.metadata.environment != "global"
                    and metadata.environment != config.metadata.environment
                ):
                    raise ConfigurationError()
            if suffix in {".yaml", ".yml", ".json"}:
                value = json.loads(text) if suffix == ".json" else safe_yaml(text)
                text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            clean = self.redactor.redact(text).strip()
            fields = metadata.model_dump()
            # Metadata can carry credentials too; reject rather than emitting altered ACLs.
            if self.redactor.redact(json.dumps(fields)) != json.dumps(fields):
                raise SanitizationError()
            category = config.source_type
            if category == SourceType.INTERNAL_KNOWLEDGE:
                for part, kind in {
                    "runbooks": SourceType.RUNBOOK,
                    "architecture": SourceType.ARCHITECTURE,
                    "known-errors": SourceType.KNOWN_ERROR,
                }.items():
                    if part in PurePosixPath(path).parts:
                        category = kind
                        break
            if metadata.document_type is None:
                metadata = metadata.model_copy(update={"document_type": category.value})
            identifier = "doc-" + checksum(config.id + "\0" + path)
            title = next(
                (line.lstrip("# ") for line in clean.splitlines() if line.startswith("# ")), path
            )
            source = KnowledgeProvenance(
                source_id=config.id,
                environment_id=metadata.environment,
                retrieved_at=raw.retrieved_at,
                source_reference=config.source_url or f"{config.id}/{path}",
                content_sha256=checksum(clean + "\0" + metadata.model_dump_json()),
                source_type=category,
                repository=config.repository_url,
                path=path,
                document_id=identifier,
                version=metadata.product_version,
                commit=raw.revision if config.type == "git" else None,
                branch=config.branch if config.type == "git" else None,
                ingested_at=datetime.now(UTC),
                metadata=metadata,
            )
            return KnowledgeDocument(
                id=identifier,
                title=title[:1024],
                text=clean,
                format=cast(Literal[".md", ".txt", ".yaml", ".yml", ".json"], suffix),
                source=source,
                incident=raw.incident,
            )
        except (UnicodeError, ValueError, TypeError, RecursionError, ValidationError):
            raise ConfigurationError() from None


class Chunker(Protocol):
    def chunk(self, document: KnowledgeDocument, revision: str) -> tuple[KnowledgeChunk, ...]: ...


class StructureAwareChunker:
    def __init__(self, limits: KnowledgeLimits) -> None:
        self.limits = limits

    def chunk(self, document: KnowledgeDocument, revision: str) -> tuple[KnowledgeChunk, ...]:
        sections: list[tuple[str, str]] = []
        headings: list[tuple[int, str]] = []
        lines: list[str] = []
        section = "document"
        fenced = False
        for line in document.text.splitlines():
            if line.startswith(("```", "~~~")):
                fenced = not fenced
            match = (
                re.match(r"^(#{1,6})\s+(.+)$", line)
                if document.format == ".md" and not fenced
                else None
            )
            if match:
                if lines:
                    sections.append((section, "\n".join(lines).strip()))
                level = len(match[1])
                headings = [(n, title) for n, title in headings if n < level]
                headings.append((level, match[2]))
                section = " / ".join(title for _, title in headings)
                lines = []
            lines.append(line)
        if lines:
            sections.append((section, "\n".join(lines).strip()))
        chunks: dict[str, KnowledgeChunk] = {}
        size, overlap = self.limits.max_chunk_size, self.limits.overlap
        for section, text in sections:
            start = 0
            while start < len(text):
                end = min(start + size, len(text))
                if 0 < len(text) - end < self.limits.minimum_size and len(text) > size:
                    end = max(
                        start + self.limits.minimum_size, len(text) - self.limits.minimum_size
                    )
                excerpt = text[start:end].strip()
                identifier = "chunk-" + checksum(document.id + "\0" + section + "\0" + excerpt)
                if excerpt:
                    chunks[identifier] = KnowledgeChunk(
                        id=identifier,
                        environment_id=document.source.environment_id,
                        text=excerpt,
                        source=document.source.model_copy(update={"section": section}),
                        access_labels=(document.source.environment_id,),
                        revision=revision,
                        title=document.title,
                        source_type=document.source.source_type,
                        metadata=document.source.metadata,
                        document_id=document.id,
                    )
                if len(chunks) > self.limits.max_chunks_per_document:
                    raise ConfigurationError()
                if end == len(text):
                    break
                start = max(start + 1, end - overlap)
        return tuple(chunks.values())
