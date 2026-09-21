"""Mapping blueprint parser, not a database or transformation engine."""

from pathlib import Path
from typing import Annotated, Literal, Protocol, Self

from pydantic import Field, StringConstraints, ValidationError, model_validator

from agt_mcp.configuration.loader import read_yaml
from agt_mcp.core.errors import ConfigurationError, SchemaMappingError
from agt_mcp.core.models import Incident, Model, Provenance, Resource
from agt_mcp.topology.models import Dependency

Name = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")]


class MappingSource(Model):
    datasource: str = Field(min_length=1, max_length=128)
    table: Name
    schema_name: Name | None = None


class ColumnMapping(Model):
    column: Name


class MappingSpec(Model):
    schema_version: Literal["1.0.0"] = "1.0.0"
    entity: Literal["Incident", "Resource", "Dependency"]
    source: MappingSource
    fields: dict[str, ColumnMapping]

    @model_validator(mode="after")
    def known_fields(self) -> Self:
        targets: dict[str, type[Model]] = {
            "Incident": Incident,
            "Resource": Resource,
            "Dependency": Dependency,
        }
        target = targets[self.entity]
        if "id" not in self.fields or not set(self.fields) <= target.model_fields.keys():
            raise ValueError("invalid canonical field")
        return self


def load_mapping(path: Path) -> MappingSpec:
    try:
        return MappingSpec.model_validate(read_yaml(path))
    except (ConfigurationError, ValidationError):
        raise SchemaMappingError() from None


class MappingEngine(Protocol):
    def map_record(
        self, record: dict[str, object], spec: MappingSpec, source: Provenance
    ) -> Model: ...
