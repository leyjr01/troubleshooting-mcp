"""Explicit local-only knowledge sources and bounded pipeline settings."""

import re
from pathlib import PurePosixPath
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from agt_mcp.core.models import Identifier, Model
from agt_mcp.credentials.providers import CredentialReference
from agt_mcp.knowledge.models import KnowledgeMetadata, SourceType


class KnowledgeLimits(Model):
    max_document_bytes: int = Field(default=65536, ge=128, le=1048576)
    max_documents: int = Field(default=200, ge=1, le=2000)
    max_chunks_per_document: int = Field(default=100, ge=1, le=1000)
    max_total_chunks_per_ingestion: int = Field(default=2000, ge=1, le=10000)
    max_chunk_size: int = Field(default=1200, ge=64, le=8000)
    overlap: int = Field(default=100, ge=0, le=2000)
    minimum_size: int = Field(default=40, ge=1, le=1000)
    max_top_k: int = Field(default=10, ge=1, le=100)
    max_result_bytes: int = Field(default=32768, ge=256, le=1048576)

    @model_validator(mode="after")
    def sizes(self) -> Self:
        if self.overlap >= self.max_chunk_size or self.minimum_size > self.max_chunk_size:
            raise ValueError("invalid chunk sizes")
        return self


class KnowledgeSourceConfig(Model):
    id: Identifier
    type: Literal["git", "official-local", "incident-local"]
    enabled: bool = False
    local_path: str = Field(min_length=1, max_length=4096, repr=False)
    mapping_path: str | None = Field(default=None, max_length=4096, repr=False)
    repository_url: str | None = Field(default=None, max_length=2048, repr=False)
    branch: str = Field(default="main", pattern=r"^[A-Za-z0-9][A-Za-z0-9_./-]{0,127}$")
    subpath: str = ""
    include: tuple[str, ...] = ("",)
    source_type: SourceType = SourceType.INTERNAL_KNOWLEDGE
    metadata: KnowledgeMetadata = KnowledgeMetadata()
    source_url: str | None = None
    allowed_domains: tuple[str, ...] = ("docs.redhat.com", "access.redhat.com")
    credentials: CredentialReference | None = Field(default=None, repr=False)
    usage: tuple[Identifier, ...] = ("rag",)

    @model_validator(mode="after")
    def safe_configuration(self) -> Self:
        for path in (self.subpath, *self.include):
            if "\\" in path or ":" in path or PurePosixPath(path).is_absolute():
                raise ValueError("relative knowledge path required")
            if ".." in PurePosixPath(path).parts:
                raise ValueError("path traversal forbidden")
        if ".." in self.branch or self.branch.endswith(("/", ".", ".lock")):
            raise ValueError("invalid branch")
        for value in (self.repository_url, self.source_url):
            if value:
                parsed = urlsplit(value)
                if (
                    parsed.scheme != "https"
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                    or re.search(r"\s", value)
                ):
                    raise ValueError("credential-free HTTPS metadata URL required")
        if self.type == "official-local" and (
            self.source_type != SourceType.OFFICIAL_DOCUMENTATION
            or not self.source_url
            or urlsplit(self.source_url).hostname not in self.allowed_domains
            or not self.metadata.product
            or not self.metadata.product_version
        ):
            raise ValueError("official source requires allowlisted versioned provenance")
        if self.type == "incident-local" and self.source_type != SourceType.HISTORICAL_INCIDENT:
            raise ValueError("incident category required")
        if self.credentials and self.credentials.environment_id != self.metadata.environment:
            raise ValueError("credential scope mismatch")
        return self
