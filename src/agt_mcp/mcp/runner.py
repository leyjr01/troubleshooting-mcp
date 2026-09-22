"""CLI transport launch with protocol-only stdout and safe stderr logging."""

import logging
import sys

from agt_mcp.configuration.models import Configuration
from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.server import create_server


class FrameworkLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "agt_mcp.audit":
            record.msg = "framework_event"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True


def serve(configuration: Configuration) -> None:
    settings = configuration.mcp.server
    server = create_server(build_runtime(configuration))
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(FrameworkLogFilter())
    logging.basicConfig(level=settings.log_level, handlers=[handler], force=True)
    # SDK loggers must use the same sanitizing handler as application events.
    for name in ("fastmcp", "mcp", "uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    if settings.transport == "stdio":
        server.run(transport="stdio", show_banner=False, log_level=settings.log_level)
    else:
        server.run(
            transport="http",
            host=settings.host,
            port=settings.port,
            path="/mcp",
            show_banner=False,
            log_level=settings.log_level,
            host_origin_protection=True,
            allowed_hosts=["127.0.0.1"],
            allowed_origins=[],
            uvicorn_config={"log_config": None, "access_log": False},
        )
