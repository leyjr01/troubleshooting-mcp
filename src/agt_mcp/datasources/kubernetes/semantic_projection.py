"""Fixed safe product hints, not classification. No free-form CR/label passthrough."""

import re
from typing import Any

from pydantic import JsonValue

ROLES = frozenset(
    {
        "apicast-staging",
        "apicast-production",
        "system-app",
        "system-sidekiq",
        "backend-listener",
        "backend-worker",
        "backend-cron",
        "zync",
        "zync-que",
        "zync-database",
        "system-memcache",
        "system-database",
        "system-redis",
    }
)


def safe_hints(raw: dict[str, Any]) -> dict[str, JsonValue]:
    metadata = raw.get("metadata", {})
    labels = metadata.get("labels", {})
    result: dict[str, JsonValue] = {}
    roles = sorted(
        {
            v
            for k in ("deployment", "app.kubernetes.io/component")
            if isinstance(v := labels.get(k), str) and v in ROLES
        }
    )
    if roles:
        result["component_labels"] = [role for role in roles]
    if (
        labels.get("app") == "3scale-api-management"
        or labels.get("app.kubernetes.io/part-of") == "3scale"
    ):
        result["product_label"] = True
    if labels.get("app.kubernetes.io/managed-by") in {"3scale-operator", "3scale"}:
        result["operator_label"] = True
    version = labels.get("app.kubernetes.io/version")
    if isinstance(version, str) and re.fullmatch(r"\d{1,2}\.\d{1,2}(?:\.\d{1,3})?", version):
        result["version_label"] = version
    if raw.get("kind") == "APIManager" and raw.get("apiVersion") == "apps.3scale.net/v1alpha1":
        spec = raw.get("spec", {})
        external = spec.get("externalComponents", {})
        result["external_components"] = {
            component: {
                field: value
                for field in fields
                if type(value := external.get(component, {}).get(field)) is bool
            }
            for component, fields in (
                ("system", ("database", "redis")),
                ("backend", ("redis",)),
                ("zync", ("database",)),
            )
        }
        enabled = spec.get("zync", {}).get("enabled")
        if type(enabled) is bool:
            result["zync_enabled"] = enabled
    return result
