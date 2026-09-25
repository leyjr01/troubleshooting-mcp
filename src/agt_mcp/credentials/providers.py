"""Only a scoped environment-variable provider is concrete in Sprint 0."""

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import SecretStr

from agt_mcp.core.errors import AuthenticationError, AuthorizationError
from agt_mcp.core.models import Identifier, Model


class CredentialReference(Model):
    provider: Identifier
    reference: Identifier
    environment_id: Identifier


@runtime_checkable
class CredentialProvider(Protocol):
    async def resolve(self, reference: CredentialReference) -> SecretStr: ...


class EnvironmentVariableCredentialProvider:
    def __init__(
        self,
        environment_id: str,
        allowed_names: frozenset[str],
        values: Mapping[str, str] | None = None,
    ) -> None:
        self.environment_id = environment_id
        self.allowed_names = allowed_names
        self.values = os.environ if values is None else values

    async def resolve(self, reference: CredentialReference) -> SecretStr:
        if reference.provider != "environment":
            raise AuthenticationError()
        if reference.environment_id != self.environment_id:
            raise AuthorizationError()
        if reference.reference not in self.allowed_names:
            raise AuthorizationError()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", reference.reference):
            raise AuthenticationError()
        value = self.values.get(reference.reference)
        if not value:
            raise AuthenticationError()
        return SecretStr(value)


class MountedFileCredentialProvider:
    """Operator-configured credential files; paths never come from tool arguments."""

    def __init__(self, environment_id: str, allowed_paths: frozenset[str]) -> None:
        self.environment_id = environment_id
        self.allowed_paths = allowed_paths

    async def resolve(self, reference: CredentialReference) -> SecretStr:
        if (
            reference.environment_id != self.environment_id
            or reference.reference not in self.allowed_paths
        ):
            raise AuthorizationError()
        path = Path(reference.reference.removeprefix("file:"))
        if (
            reference.provider != "mounted-file"
            or not reference.reference.startswith("file:")
            or not path.is_absolute()
        ):
            raise AuthenticationError()
        try:
            with path.open("rb") as stream:
                raw = stream.read(4097)
            value = raw.decode("utf-8").strip()
            if len(raw) > 4096 or not value:
                raise AuthenticationError()
        except (OSError, UnicodeError):
            raise AuthenticationError() from None
        return SecretStr(value)
