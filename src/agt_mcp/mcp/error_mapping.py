"""Framework boundary never serializes exception text, arguments or tracebacks."""

from agt_mcp.core.errors import AGTError


def error_code(error: Exception) -> str:
    return error.code.value if isinstance(error, AGTError) else "internal_error"
