"""Redact before hashing, truncation, Evidence construction and timeline projection."""

import json
import re
from datetime import datetime
from hashlib import sha256

from agt_mcp.configuration.observability import ObservabilityLimits, ObservabilitySource
from agt_mcp.core.errors import AuthorizationError
from agt_mcp.core.models import Evidence, Provenance
from agt_mcp.correlation.models import EvidenceAtom
from agt_mcp.correlation.rules import identity
from agt_mcp.knowledge.security import KnowledgeRedactor
from agt_mcp.observability.models import LogObservation, ObservabilityQuery, SignalObservation
from agt_mcp.troubleshooting.generator import initial_confidence


class ObservabilityNormalizer:
    def __init__(self, limits: ObservabilityLimits) -> None:
        self.limits = limits
        self.redactor = KnowledgeRedactor()

    def text(self, text: str) -> str:
        text = re.sub(r"(?im)(\b(?:set-cookie|cookie)\s*[:=]\s*)[^\r\n]+", r"\1[REDACTED]", text)
        return self.redactor.redact(text)

    def canonicalize(
        self,
        item: SignalObservation,
        query: ObservabilityQuery,
        source: ObservabilitySource,
        retrieved_at: datetime,
    ) -> EvidenceAtom:
        if (
            item.environment_id != query.environment_id
            or source.environment_id != query.environment_id
            or item.source_id != source.id
            or item.resource_id not in query.resource_refs
        ):
            raise AuthorizationError()
        binding = next((b for b in source.bindings if b.resource_id == item.resource_id), None)
        if binding is None:
            raise AuthorizationError()
        # Resource bindings are trusted configuration. Signal text never supplies correlation keys.
        supplied = item.keys.model_dump(exclude_none=True)
        trusted = binding.keys.model_dump(exclude_none=True)
        for key, value in supplied.items():
            if key in trusted and trusted[key] != value:
                raise AuthorizationError()
        data = item.model_dump(mode="json")
        data["trust"] = "UNTRUSTED_DATA"
        data["labels"] = self.safe_mapping(item.labels)
        if "attributes" in data:
            data["attributes"] = self.safe_mapping(data["attributes"])
        for key in ("message", "operation", "service"):
            if key in data:
                clean = self.text(data[key])
                if isinstance(item, LogObservation):
                    clean = "\n".join(clean.splitlines()[: self.limits.max_log_lines])
                data[key] = clean[: self.limits.max_text_chars]
        # IDs in telemetry are untrusted too. Keep raw IDs only as hashes for stable deduplication.
        data["id"] = identity("observation", source.id, item.id)
        for key in ("trace_id", "span_id", "parent_span_id"):
            if data.get(key) and self.text(data[key]) != data[key]:
                data[key] = identity(key, data[key])
        data["keys"] = {
            k: v if self.text(v) == v else identity(k, v) for k, v in (trusted | supplied).items()
        }
        payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
        reference = json.dumps(
            {
                "adapter": source.type,
                "datasource": source.id,
                "query_id": identity("observability-query", query.model_dump_json()),
                "window": query.time_window.model_dump(mode="json"),
                "resource": item.resource_id,
            },
            sort_keys=True,
        )
        provenance = Provenance(
            source_id=source.id,
            environment_id=query.environment_id,
            retrieved_at=retrieved_at,
            source_reference=reference,
            content_sha256=sha256(payload.encode()).hexdigest(),
        )
        evidence = Evidence(
            id=identity("observability", source.id, payload),
            environment_id=query.environment_id,
            timestamp=item.timestamp,
            source=provenance,
            type="observation",
            resource_id=item.resource_id,
            observation=payload[:16384],
            raw_reference=reference,
            confidence=initial_confidence().model_copy(
                update={
                    "source_reliability": item.signal.value.lower(),
                    "rationale": "Untrusted descriptive telemetry; not proof of root cause",
                }
            ),
            metadata={"signal_type": item.signal.value, "trust": "UNTRUSTED_DATA"},
        )
        return EvidenceAtom(
            evidence=evidence,
            occurred_at=item.timestamp,
            kind=item.signal.value.lower(),
            origin=f"observability:{source.id}",
        )

    def safe_mapping(self, values: dict[str, str]) -> dict[str, str]:
        return {
            k: "[REDACTED]"
            if re.search(
                r"(?i)authorization|password|passwd|token|api.?key|client.?secret|cookie|private.?key|connection.?string",
                k,
            )
            else self.text(v)[:512]
            for k, v in sorted(values.items())
        }
