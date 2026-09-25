"""A configured HTTP reader identity; application ACLs remain authoritative."""

from hmac import compare_digest

from fastmcp.server.auth import AccessToken, TokenVerifier
from pydantic import SecretStr

from agt_mcp.core.errors import AuthenticationError
from agt_mcp.credentials.providers import (
    CredentialReference,
    EnvironmentVariableCredentialProvider,
    MountedFileCredentialProvider,
)


class ConfiguredTokenVerifier(TokenVerifier):
    def __init__(self, reference: CredentialReference) -> None:
        super().__init__()
        self.reference = reference
        self.secret: SecretStr | None = None

    async def initialize(self) -> None:
        provider = (
            EnvironmentVariableCredentialProvider(
                self.reference.environment_id, frozenset({self.reference.reference})
            )
            if self.reference.provider == "environment"
            else MountedFileCredentialProvider(
                self.reference.environment_id, frozenset({self.reference.reference})
            )
        )
        secret = await provider.resolve(self.reference)
        value = secret.get_secret_value()
        if not 32 <= len(value) <= 4096 or not value.isascii() or any(c.isspace() for c in value):
            raise AuthenticationError()
        self.secret = secret

    async def verify_token(self, token: str) -> AccessToken | None:
        if self.secret is None or not compare_digest(
            token.encode(), self.secret.get_secret_value().encode()
        ):
            return None
        return AccessToken(token=token, client_id="local-client", scopes=[])
