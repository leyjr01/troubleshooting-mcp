"""Create internal identity; caller input never defines principal or permissions."""

from datetime import UTC, datetime
from time import monotonic
from uuid import UUID, uuid4

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.execution import ExecutionContext, ToolName


def create_context(
    configuration: Configuration,
    operation: ToolName,
    environment_id: str | None,
    correlation_id: str | None,
) -> ExecutionContext:
    # Only UUIDs are accepted for logs; arbitrary external identifiers are not logged.
    try:
        correlation = (
            str(UUID(correlation_id))
            if correlation_id and len(correlation_id) <= 36
            else str(uuid4())
        )
    except ValueError:
        correlation = str(uuid4())
    timeout = min(
        configuration.application.timeout_seconds, configuration.mcp.server.request_timeout_seconds
    )
    return ExecutionContext(
        environment_id=environment_id or configuration.application.environment,
        principal_id=configuration.mcp.server.authorization.principal,
        operation=operation,
        request_id=str(uuid4()),
        correlation_id=correlation,
        start_time=datetime.now(UTC),
        deadline=monotonic() + timeout,
        timeout_seconds=timeout,
        max_payload_bytes=configuration.application.max_payload_bytes,
    )
