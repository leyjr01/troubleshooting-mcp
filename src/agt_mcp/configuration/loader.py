"""Safe YAML and deterministic overlays. No network or secret resolution on load."""

import copy
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.errors import ConfigurationError

MAX_CONFIG_BYTES = 262144


class UniqueSafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        result: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ConfigurationError()
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ConfigurationError()
        text = raw.decode("utf-8")
        if any(
            isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken))
            for token in yaml.scan(text)
        ):
            raise ConfigurationError()
        # SafeLoader subclass only rejects extra input; no object constructors are added.
        value = yaml.load(text, Loader=UniqueSafeLoader)  # nosec B506
        if not isinstance(value, dict):
            raise ConfigurationError()
        return value
    except (OSError, UnicodeError, yaml.YAMLError, RecursionError):
        raise ConfigurationError() from None


def merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Maps merge recursively; lists replace atomically to avoid mixed identities."""
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_configuration(
    files: Sequence[Path] = (),
    environment_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Configuration:
    env = os.environ if environ is None else environ
    values: dict[str, Any] = {}
    for path in files:
        values = merge(values, read_yaml(path))
    if environment_file is not None:
        values = merge(values, read_yaml(environment_file))
    application = values.setdefault("application", {})
    if not isinstance(application, dict):
        raise ConfigurationError()
    overrides = {
        "AGT_ENVIRONMENT": ("environment", str),
        "AGT_TIMEOUT_SECONDS": ("timeout_seconds", float),
        "AGT_MAX_PAYLOAD_BYTES": ("max_payload_bytes", int),
    }
    try:
        for name, (field, converter) in overrides.items():
            if name in env:
                application[field] = converter(env[name])

        def interpolate(value: Any, depth: int = 0) -> Any:
            if depth > 30:
                raise ConfigurationError()
            if isinstance(value, dict):
                return {k: interpolate(v, depth + 1) for k, v in value.items()}
            if isinstance(value, list):
                return [interpolate(v, depth + 1) for v in value]
            if isinstance(value, str) and "${" in value:
                match = re.fullmatch(r"\$\{([A-Z][A-Z0-9_]*)\}", value)
                if match is None or match[1] not in env:
                    raise ConfigurationError()
                return env[match[1]]
            return value

        return Configuration.model_validate(interpolate(values))
    except (ValueError, TypeError, ValidationError, RecursionError):
        raise ConfigurationError() from None
