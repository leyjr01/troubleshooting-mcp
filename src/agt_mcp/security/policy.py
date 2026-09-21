"""Local authorization/deadline boundary; no authentication system is implemented."""

import asyncio
import builtins
from collections.abc import Awaitable, Callable

from agt_mcp.core.errors import AuthorizationError, TimeoutError, UnsupportedCapabilityError
from agt_mcp.core.operations import Operation, OperationContext


class ReadOnlyPolicy:
    def __init__(
        self, principal_id: str, environment_ids: frozenset[str], operations: frozenset[Operation]
    ) -> None:
        self.principal_id = principal_id
        self.environment_ids = environment_ids
        self.operations = operations

    def authorize(self, operation: Operation, context: OperationContext) -> None:
        if (
            context.principal_id != self.principal_id
            or context.environment_id not in self.environment_ids
            or operation not in self.operations
        ):
            raise AuthorizationError()


async def run_read[T](
    policy: ReadOnlyPolicy,
    operation: Operation,
    context: OperationContext,
    capabilities: frozenset[Operation],
    action: Callable[[], Awaitable[T]],
) -> T:
    policy.authorize(operation, context)
    if operation not in capabilities:
        raise UnsupportedCapabilityError()
    try:
        async with asyncio.timeout(context.timeout_seconds):
            return await action()
    except builtins.TimeoutError:
        raise TimeoutError() from None
