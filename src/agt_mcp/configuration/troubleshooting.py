"""Bounded hypothesis evaluation and ephemeral result storage."""

from pydantic import Field

from agt_mcp.core.models import Model


class TroubleshootingConfig(Model):
    max_hypotheses: int = Field(default=16, ge=1, le=100)
    max_candidates: int = Field(default=8, ge=1, le=50)
    max_plan_steps: int = Field(default=12, ge=1, le=100)
    max_evidence_per_hypothesis: int = Field(default=10, ge=1, le=100)
    max_components: int = Field(default=12, ge=1, le=50)
    cache_entries: int = Field(default=16, ge=1, le=100)
    cache_ttl_seconds: int = Field(default=300, ge=1, le=3600)
