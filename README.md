# API Gateway Troubleshooting MCP — v1.0.0

Evidence-first, read-only troubleshooting for API gateways and Kubernetes/OpenShift.
The release provides 38 MCP tools for inventory/topology, 3scale semantic discovery,
evidence correlation, hypotheses, safe inspection plans, Virtual Trace, opt-in probes
and knowledge/observability enrichment. READ, DIAGNOSE, RECOMMEND; no remediation.

FastMCP → application services → canonical diagnosis/correlation → injected runtime,
gateway, observability, probe and knowledge ports. Core has no vendor implementations.
See [architecture and limits](docs/release/contracts.md) and [tool catalog](docs/release/tool-catalog.md).

## Quickstart

Use Python 3.12 and a virtual environment. From a prepared source checkout:

```sh
python -m pip install -e '.[dev]'
python -m agt_mcp validate-config --file config/server/local.example.yaml
python -m agt_mcp serve --file config/server/local.example.yaml
```

The local example uses synthetic data. The [installation guide](docs/installation/README.md)
includes a client calling system_health/list_environments/discover_gateway and explains
explicit live discover_environment configuration. HTTP is loopback by default.

## Security and qualification

Deny-all defaults, environment ACLs, bounded requests, safe errors, evidence provenance,
read-only RBAC and no Secret API access. Remote HTTP needs explicit bearer configuration,
exact allowed Hosts and operator-managed TLS/network restrictions. Probes are disabled
by default, and active observation requires separate authorization and target policy.
External content is untrusted. See [SECURITY](SECURITY.md).

Technical release positioning: READY WITH LIMITATIONS, subject to the recorded gates.
Windows Python 3.12, FastMCP 4.0.5 and SDK contracts are tested. Real Kubernetes,
OpenShift, 3scale and Linux container execution remain NOT QUALIFIED. Prometheus is
protocol-tested, not live-qualified. No production SSO, HA, durable incident database,
Redis/database protocol diagnosis or confirmed automatic root-cause determination.
See the [compatibility matrix](docs/release/compatibility.md).

## Documentation and release

- [Release notes and post-1.0 backlog](docs/release/v1.0.0.md)
- [Changelog](CHANGELOG.md)
- [Kubernetes](docs/deployment/kubernetes.md) and [OpenShift](docs/deployment/openshift.md)
- [Operations runbook](docs/operations/runbook.md)
- [Build, verification and release commands](docs/release/commands.md)
- [Security review and license inventory](docs/release/security-review.md)
- [Release validation](docs/release/sprint-11-validation.md)
- [Current checkpoint](PROJECT_STATE.md)

One-command offline checkpoint: `python scripts/release.py checkpoint`.
Real-lab tests are [explicit opt-in](docs/development/real-lab.md); no platform
software or cluster resources are installed automatically. Package version comes
from pyproject metadata without Git lookup. Optional local Git knowledge sources still
require Git. No external release was published.
