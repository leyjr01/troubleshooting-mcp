"""Hard bounds for temporal/topological expansion and the ephemeral result cache."""

from typing import Self

from pydantic import Field, model_validator

from agt_mcp.core.models import Model


class CorrelationConfig(Model):
    default_lookback_seconds: int = Field(default=900, ge=1, le=86400)
    max_lookback_seconds: int = Field(default=86400, ge=1, le=604800)
    future_skew_seconds: int = Field(default=30, ge=0, le=300)
    temporal_proximity_seconds: int = Field(default=90, ge=1, le=3600)
    max_events: int = Field(default=10, ge=1, le=200)
    max_resources: int = Field(default=12, ge=1, le=200)
    max_candidates: int = Field(default=12, ge=1, le=200)
    max_topology_depth: int = Field(default=2, ge=0, le=3)
    max_knowledge_results: int = Field(default=2, ge=1, le=10)
    enrichment_timeout_seconds: float = Field(default=3, gt=0, le=30)
    cache_entries: int = Field(default=16, ge=1, le=100)
    cache_ttl_seconds: int = Field(default=300, ge=1, le=3600)

    @model_validator(mode="after")
    def lookback(self) -> Self:
        if self.default_lookback_seconds > self.max_lookback_seconds:
            raise ValueError("default lookback exceeds maximum")
        return self
