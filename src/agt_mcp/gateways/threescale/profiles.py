"""Auditable product rules. These are expectations, never runtime observations."""

from dataclasses import dataclass

from agt_mcp.gateways.threescale.models import ComponentType as C

INSTALL_GUIDE = "https://docs.redhat.com/en/documentation/red_hat_3scale_api_management/2.16/html-single/installing_red_hat_3scale_api_management/installing_red_hat_3scale_api_management"
API_REFERENCE = "https://github.com/3scale/3scale-operator/blob/master/doc/apimanager-reference.md"
MIGRATION_GUIDE = "https://docs.redhat.com/en/documentation/red_hat_3scale_api_management/2.16/html/migrating_red_hat_3scale_api_management/externalizing-databases"

PATTERNS = {
    c.value.lower().replace("_", "-"): c
    for c in C
    if c
    not in {
        C.APIMANAGER,
        C.UNKNOWN,
        C.BACKEND_REDIS_STORAGE,
        C.BACKEND_REDIS_QUEUES,
    }
}
CORE_COMPONENTS = (
    C.APICAST_STAGING,
    C.APICAST_PRODUCTION,
    C.SYSTEM_APP,
    C.SYSTEM_SIDEKIQ,
    C.BACKEND_LISTENER,
    C.BACKEND_WORKER,
    C.BACKEND_CRON,
)
ZYNC_COMPONENTS = (C.ZYNC, C.ZYNC_QUE, C.ZYNC_DATABASE)
EXTERNAL_COMPONENTS = (
    C.SYSTEM_DATABASE,
    C.BACKEND_REDIS_STORAGE,
    C.BACKEND_REDIS_QUEUES,
    C.SYSTEM_REDIS,
)
SECRET_BINDINGS = {
    C.SYSTEM_DATABASE: ("system", "database", "system-database"),
    C.BACKEND_REDIS_STORAGE: ("backend", "redis", "backend-redis"),
    C.BACKEND_REDIS_QUEUES: ("backend", "redis", "backend-redis"),
    C.SYSTEM_REDIS: ("system", "redis", "system-redis"),
    C.ZYNC_DATABASE: ("zync", "database", "zync"),
}


@dataclass(frozen=True)
class ThreeScaleVersionProfile:
    version: str
    expected_components: tuple[C, ...]
    optional_components: tuple[C, ...]
    externally_managed_components: tuple[C, ...]
    supported_features: tuple[str, ...]
    sources: tuple[str, ...]
    product: str = "Red Hat 3scale API Management"
    document_sections: tuple[str, ...] = (
        "External databases",
        "ExternalComponentsSpec",
        "ZyncSpec",
    )
    last_verified: str = "2026-09-22"
    known_resource_patterns: tuple[str, ...] = tuple(sorted(PATTERNS))


PROFILES = {
    "2.16": ThreeScaleVersionProfile(
        "2.16",
        CORE_COMPONENTS,
        (C.SYSTEM_MEMCACHE, *ZYNC_COMPONENTS),
        EXTERNAL_COMPONENTS,
        ("external-databases", "zync-toggle", "runtime-classification"),
        (INSTALL_GUIDE, API_REFERENCE, MIGRATION_GUIDE),
    )
}


def profile_for(version: str) -> ThreeScaleVersionProfile | None:
    return PROFILES.get(".".join(version.split(".")[:2]))
