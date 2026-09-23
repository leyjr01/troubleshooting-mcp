"""Read-only local snapshots; Git blobs are read at a pinned commit, never checked out."""

import asyncio
import hashlib
import os
import shutil
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from agt_mcp.configuration.knowledge import KnowledgeLimits, KnowledgeSourceConfig
from agt_mcp.core.errors import AuthorizationError, ConfigurationError, ResourceNotFound
from agt_mcp.core.operations import OperationContext
from agt_mcp.knowledge.models import (
    KnowledgeSource,
    SourceChanges,
    SourceDocument,
    SourceSnapshot,
)

FORMATS = frozenset({".md", ".txt", ".yaml", ".yml", ".json"})


class KnowledgeSourceAdapter(ABC):
    def __init__(self, config: KnowledgeSourceConfig, limits: KnowledgeLimits) -> None:
        self.config, self.limits = config, limits

    def check_scope(self, context: OperationContext) -> None:
        if self.config.metadata.environment not in {"global", context.environment_id}:
            raise AuthorizationError()

    def source_metadata(self) -> KnowledgeSource:
        return KnowledgeSource(
            id=self.config.id,
            source_type=self.config.source_type,
            environment=self.config.metadata.environment,
            capabilities=("document.list", "document.read", "incremental.read"),
            usage=self.config.usage,
        )

    def included(self, path: str) -> bool:
        candidate = PurePosixPath(path)
        if candidate.suffix.lower() not in FORMATS:
            return False
        root = PurePosixPath(self.config.subpath)
        if not candidate.is_relative_to(root):
            return False
        relative = candidate.relative_to(root)
        return any(relative.is_relative_to(PurePosixPath(p)) for p in self.config.include)

    @abstractmethod
    async def revision(self, context: OperationContext) -> str: ...

    @abstractmethod
    async def snapshot(self, context: OperationContext) -> SourceSnapshot: ...

    async def list_documents(self, context: OperationContext) -> tuple[str, ...]:
        return tuple(d.path for d in (await self.snapshot(context)).documents)

    async def get_document(self, path: str, context: OperationContext) -> SourceDocument:
        for document in (await self.snapshot(context)).documents:
            if document.path == path:
                return document
        raise ResourceNotFound()

    async def get_changes(
        self, previous: SourceSnapshot, context: OperationContext
    ) -> SourceChanges:
        current = await self.snapshot(context)
        before = {d.path: d.content for d in previous.documents}
        after = {d.path: d.content for d in current.documents}
        return SourceChanges(
            new=tuple(sorted(after.keys() - before.keys())),
            changed=tuple(sorted(k for k in after.keys() & before.keys() if after[k] != before[k])),
            unchanged=tuple(
                sorted(k for k in after.keys() & before.keys() if after[k] == before[k])
            ),
            deleted=tuple(sorted(before.keys() - after.keys())),
        )

    async def health(self, context: OperationContext) -> str:
        await self.revision(context)
        return "HEALTHY"


class GitKnowledgeSource(KnowledgeSourceAdapter):
    async def _git(self, arguments: tuple[str, ...], max_bytes: int, timeout: float) -> bytes:
        executable = shutil.which("git")
        if executable is None:
            raise ConfigurationError()
        environment = {
            k: v
            for k, v in os.environ.items()
            if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}
        }
        environment.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_OPTIONAL_LOCKS": "0",
            }
        )
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                "--no-pager",
                "-C",
                self.config.local_path,
                *arguments,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=environment,
            )
            try:
                async with asyncio.timeout(timeout):
                    if process.stdout is None:
                        raise ConfigurationError()
                    output = await process.stdout.read(max_bytes + 1)
                    # StreamReader.read may return a short block before EOF.
                    while len(output) <= max_bytes:
                        block = await process.stdout.read(max_bytes + 1 - len(output))
                        if not block:
                            break
                        output += block
                    if len(output) > max_bytes:
                        raise ConfigurationError()
                    if await process.wait() != 0:
                        raise ConfigurationError()
                    return output
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.communicate()
        except (OSError, TimeoutError):
            raise ConfigurationError() from None

    async def revision(self, context: OperationContext) -> str:
        self.check_scope(context)
        output = await self._git(
            ("rev-parse", "--verify", f"refs/heads/{self.config.branch}^{{commit}}"),
            100,
            context.timeout_seconds,
        )
        revision = output.decode("ascii").strip()
        if len(revision) not in {40, 64} or any(c not in "0123456789abcdef" for c in revision):
            raise ConfigurationError()
        return revision

    async def snapshot(self, context: OperationContext) -> SourceSnapshot:
        revision = await self.revision(context)
        listing = await self._git(
            ("ls-tree", "-r", "-z", revision),
            self.limits.max_documents * 4096,
            context.timeout_seconds,
        )
        documents: list[SourceDocument] = []
        now = datetime.now(UTC)
        try:
            for entry in listing.split(b"\0"):
                if not entry:
                    continue
                header, raw_path = entry.split(b"\t", 1)
                mode, kind, oid = header.split()
                path = raw_path.decode("utf-8")
                if not self.included(path):
                    continue
                if mode not in {b"100644", b"100755"} or kind != b"blob":
                    raise ConfigurationError()
                if len(documents) >= self.limits.max_documents:
                    raise ConfigurationError()
                content = await self._git(
                    ("cat-file", "blob", oid.decode("ascii")),
                    self.limits.max_document_bytes,
                    context.timeout_seconds,
                )
                documents.append(
                    SourceDocument(
                        path=path,
                        content=content,
                        revision=revision,
                        retrieved_at=now,
                    )
                )
        except (UnicodeError, ValueError):
            raise ConfigurationError() from None
        return SourceSnapshot(
            revision=revision, documents=tuple(sorted(documents, key=lambda d: d.path))
        )


class CuratedLocalSource(KnowledgeSourceAdapter):
    """No URL fetch. The configured URL is attribution metadata only."""

    async def revision(self, context: OperationContext) -> str:
        return (await self.snapshot(context)).revision

    async def snapshot(self, context: OperationContext) -> SourceSnapshot:
        self.check_scope(context)
        return await asyncio.to_thread(self._read)

    def _read(self) -> SourceSnapshot:
        root = Path(self.config.local_path).resolve()
        if not root.is_dir():
            raise ConfigurationError()
        documents: list[SourceDocument] = []
        now = datetime.now(UTC)
        digest = hashlib.sha256()
        try:
            # Bound enumeration as well as selected documents. Symlink directories are rejected.
            count = 0
            for directory, dirs, files in os.walk(root, followlinks=False):
                for name in sorted([*dirs, *files]):
                    count += 1
                    path = Path(directory) / name
                    if count > self.limits.max_documents * 10 or path.is_symlink():
                        raise ConfigurationError()
                for name in sorted(files):
                    path = Path(directory) / name
                    if not path.resolve().is_relative_to(root):
                        raise ConfigurationError()
                    relative = path.relative_to(root).as_posix()
                    if not self.included(relative):
                        continue
                    if len(documents) >= self.limits.max_documents:
                        raise ConfigurationError()
                    with path.open("rb") as stream:
                        content = stream.read(self.limits.max_document_bytes + 1)
                    if len(content) > self.limits.max_document_bytes:
                        raise ConfigurationError()
                    documents.append(
                        SourceDocument(
                            path=relative,
                            content=content,
                            revision="pending",
                            retrieved_at=now,
                        )
                    )
            documents.sort(key=lambda d: d.path)
            for document in documents:
                digest.update(document.path.encode() + b"\0" + document.content + b"\0")
            revision = digest.hexdigest()
            return SourceSnapshot(
                revision=revision,
                documents=tuple(d.model_copy(update={"revision": revision}) for d in documents),
            )
        except OSError:
            raise ConfigurationError() from None
