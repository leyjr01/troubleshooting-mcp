"""Offline configuration and mapping validation; no MCP server is launched."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from agt_mcp.configuration.loader import load_configuration
from agt_mcp.core.errors import AGTError
from agt_mcp.mapping.schema import load_mapping


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AGT MCP — Sprint 0 offline validation")
    commands = parser.add_subparsers(dest="command")
    config = commands.add_parser(
        "validate-config", help="Validate configuration without connecting"
    )
    config.add_argument("--file", type=Path, action="append", default=[])
    config.add_argument("--environment-file", type=Path)
    mapping = commands.add_parser("validate-mapping", help="Validate a canonical mapping blueprint")
    mapping.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-config":
            load_configuration(args.file, args.environment_file)
            print("PASS: configuration (offline; credentials not resolved)")
        elif args.command == "validate-mapping":
            load_mapping(args.path)
            print("PASS: mapping blueprint (no database access)")
        else:
            parser.print_help()
        return 0
    except AGTError as exc:
        print(f"FAIL: {exc.code.value}; verify local schema and required environment variables")
        return 1
