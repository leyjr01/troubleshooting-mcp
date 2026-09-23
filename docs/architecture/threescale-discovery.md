# 3scale semantic discovery

Sprint 3 performs product discovery, classification and structural topology.
It does not identify root causes. `Backend` here means runtime listener/worker/cron
components, not the Backend entities managed by the 3scale Admin API.

## Composition and scope

FastMCP → GatewayDiscoveryService → ThreeScaleGatewayAdapter → RuntimeAdapter →
Kubernetes/OpenShift adapter. The gateway adapter makes one discovery call per
configured binding per operation and reuses its observed_at, graph and Evidence.
Raw API objects and the SDK stay in the runtime adapter. No runtime web access
or new third-party dependency is introduced.

The [example configuration](../../config/server/threescale.example.yaml) enables
APIManager in the custom-resource allowlist. `threescale-auto` is a configured
discovery binding, not a known installation ID. Calling discover_gateway without
an ID finds APIManagers only inside the configured authorized namespace scope.
Returned installation IDs can be used for subsequent queries. Namespace includes,
excludes, resource/page limits and deadlines retain Sprint 2 behavior.

Multiple namespaces are supported only when explicitly authorized. UID ownership
separates roots. Multiple APIManagers in one namespace produce ambiguity warnings
and do not claim each other's owned resources; the operator documentation normally
expects one APIManager per namespace. Legacy disabled datasource-based examples
still validate, but activating 3scale requires the runtime-backed configuration.

## Classification and version

The runtime projection retains only recognized role values from deployment and
app.kubernetes.io/component labels, fixed product/manager markers, strictly numeric
app.kubernetes.io/version, and APIManager externalComponents/zync.enabled booleans.
Unknown labels, annotations, images, arbitrary CR fields and literal env values
are omitted. A custom app label does not prevent ownership-based discovery.

APIManager establishes a root. Owned workloads with component labels can receive
HIGH confidence; owned exact-name matches receive MEDIUM. Names without membership
evidence never classify. Product/component labels without ownership remain
unverified MEDIUM candidates with ambiguity warnings. Conflicting labels preserve
UNKNOWN_THREESCALE_COMPONENT. Pod identities are never component identities.

Observed version comes from a valid recommended version label on APIManager or
consistent labels on owned resources. Image tags alone are not used. Missing
version becomes UNKNOWN and discovery continues. Explicit version_profile: 2.16
selects expectations without falsifying the observed version. 2.14, 2.15 and future
versions currently use conservative generic discovery with unsupported-profile
warnings; additional profiles can be registered without altering generic models.

## Profile 2.16 and auditable sources

Rules reside in gateways/threescale/profiles.py, including product/version,
source URLs, document sections, known patterns and last_verified: 2026-09-22.
Sources were reviewed during development; they are not fetched by the application.

| Rule | Source and section |
| --- | --- |
| External System DB and Redis; distinct Backend Redis storage/queues | [2.16 installation guide](https://docs.redhat.com/en/documentation/red_hat_3scale_api_management/2.16/html-single/installing_red_hat_3scale_api_management/installing_red_hat_3scale_api_management), external databases/Redis configuration |
| 2.16 externalization expectations and workload names | [2.16 migration guide](https://docs.redhat.com/en/documentation/red_hat_3scale_api_management/2.16/html/migrating_red_hat_3scale_api_management/externalizing-databases), externalizing databases |
| Explicit external flags, Zync enablement, optional external Zync DB and Secret reference names | [operator APIManager reference](https://github.com/3scale/3scale-operator/blob/master/doc/apimanager-reference.md), ExternalComponentsSpec/ZyncSpec/APIManager Secrets |

The System DB, Backend Redis storage, Backend Redis queues and System Redis
profile expectations are EXTERNAL, not missing Deployments. Explicit external
flags are authoritative configuration observations; profile-derived expectations
are distinguished by version-profile-rule evidence. Explicit conflicts emit a
warning. Endpoint identity remains unresolved even when a Secret name is known.
Zync disabled means expected=false; absent unspecified Zync is treated conservatively
as optional. Explicitly enabled Zync can be expected, with its DB internal or external.
No absent component is assigned ABSENT_EXPECTED on an incomplete runtime listing.

## MCP contracts

| Tool | Arguments | Permission |
| --- | --- | --- |
| discover_gateway | Optional gateway_id, namespace, gateway_type=threescale, environment_id | gateway.discover |
| get_gateway_topology | query: gateway_id, optional depth/limit; environment_id | gateway.topology.read |
| inspect_gateway_component | query: gateway_id, component_id, optional limit; environment_id | gateway.components.read |
| get_gateway_dependencies | query: gateway_id, optional limit; environment_id | gateway.dependencies.read |

All accept optional correlation_id. Discovery returns installations, versions,
component expectations, capabilities, evidence counts and warnings. Inspection
includes detection evidence and associated safe runtime observations. Topology
contains a root, components, bounded runtime nodes, provenance-bearing edges and
unresolved runtime references. Dependencies include structural runtime references
and external identities, never connectivity results.

Defaults and hard bounds: limit 50 (max 200), depth 2 (max 3), at most 200 semantic
components per installation, and runtime-configured node/edge limits. The final
MCP envelope also has a byte cap and fails safely if exceeded. include_runtime_resources
controls expanded resource payloads; include_dependencies controls external
dependency payloads and access to the dependencies tool. Component expectation
metadata remains available. No cache is shared between operations or environments.
