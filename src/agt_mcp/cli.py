"""Explicit server entrypoint plus compatible offline validation commands."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from agt_mcp.configuration.loader import load_configuration
from agt_mcp.core.errors import AGTError
from agt_mcp.mapping.schema import load_mapping


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AGT MCP — read-only local server and validation")
    commands = parser.add_subparsers(dest="command")
    config = commands.add_parser(
        "validate-config", help="Validate configuration without connecting"
    )
    config.add_argument("--file", type=Path, action="append", default=[])
    config.add_argument("--environment-file", type=Path)
    mapping = commands.add_parser("validate-mapping", help="Validate a canonical mapping blueprint")
    mapping.add_argument("path", type=Path)
    server = commands.add_parser("serve", help="Run the local MCP server")
    server.add_argument("--file", type=Path, action="append", default=[])
    server.add_argument("--environment-file", type=Path)
    server.add_argument("--transport", choices=("stdio", "http"))
    server.add_argument("--port", type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            from pydantic import ValidationError

            from agt_mcp.configuration.models import Configuration
            from agt_mcp.core.errors import ConfigurationError
            from agt_mcp.mcp.runner import serve

            configuration = load_configuration(args.file, args.environment_file)
            data = configuration.model_dump()
            for key in ("transport", "port"):
                if getattr(args, key) is not None:
                    data["mcp"]["server"][key] = getattr(args, key)
            try:
                configuration = Configuration.model_validate(data)
            except ValidationError:
                raise ConfigurationError() from None
            serve(configuration)
        elif args.command == "validate-config":
            load_configuration(args.file, args.environment_file)
            print("PASS: configuration (offline; credentials not resolved)")
        elif args.command == "validate-mapping":
            load_mapping(args.path)
            print("PASS: mapping blueprint (no database access)")
        else:
            parser.print_help()
        return 0
    except AGTError as exc:
        print(
            f"FAIL: {exc.code.value}; verify local schema and required environment variables",
            file=sys.stderr if args.command == "serve" else sys.stdout,
        )
        return 1
    except Exception:
        if args.command != "serve":
            raise
        # Startup is another public boundary; never print framework exceptions.
        print("FAIL: internal_error; server startup or transport failure", file=sys.stderr)
        return 1
