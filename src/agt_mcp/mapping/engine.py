"""Declarative row-to-Incident mapping without expressions, evaluation or SQL."""

from pydantic import ValidationError

from agt_mcp.core.errors import SchemaMappingError
from agt_mcp.core.models import Incident, Provenance
from agt_mcp.knowledge.security import KnowledgeRedactor
from agt_mcp.mapping.schema import MappingSpec


class IncidentMappingEngine:
    def __init__(self, redactor: KnowledgeRedactor | None = None) -> None:
        self.redactor = redactor or KnowledgeRedactor()

    def map_record(
        self, record: dict[str, object], spec: MappingSpec, source: Provenance
    ) -> Incident:
        if spec.entity != "Incident" or "source" in spec.fields:
            raise SchemaMappingError()
        values: dict[str, object] = {}
        for field, mapping in spec.fields.items():
            if mapping.column not in record:
                raise SchemaMappingError()
            value = record[mapping.column]
            if isinstance(value, str):
                value = self.redactor.redact(value)
            elif isinstance(value, (tuple, list)):
                value = tuple(self.redactor.redact(str(v)) for v in value)
            values[field] = value
        if values.get("environment_id", source.environment_id) != source.environment_id:
            raise SchemaMappingError()
        values.update(environment_id=source.environment_id, source=source)
        try:
            return Incident.model_validate(values)
        except (ValueError, TypeError, ValidationError):
            raise SchemaMappingError() from None
