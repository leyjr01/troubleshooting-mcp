"""Only a scoped environment-variable provider is concrete in Sprint 0."""

import os
import re
from collections.abc import Mapping
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
