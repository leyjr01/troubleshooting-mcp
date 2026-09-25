# v1.0 MCP tool catalog

Generated with `python scripts/release.py catalog` from registered tools/permissions.
All tools: stable v1 input/output contract, read-only source access. Availability still
requires enabled tools, scope and backend capabilities; schemas do not grant access.
Output: ToolResponse (ok, request_id, correlation_id, environment_id, data, error).
Nested query inputs use the published MCP JSON Schema; clients should call list_tools.
Inventory is bounded/non-atomic; topology structural; diagnosis evidence-based.
Knowledge is untrusted; logs/traces use fixtures; metrics use configured Prometheus.
Probes are opt-in active observations, externally observable and non-idempotent.
No source writes or executed recommendations; derived in-memory caches may change.

| Tool | Purpose | Inputs (* required) | Permissions / capabilities | Limitations |
|---|---|---|---|---|
| `build_evidence_timeline` | Read bounded scoped observability evidence | query*, environment_id, correlation_id | observability.timeline.read | Configured source, scope and bounded result; no causal confirmation |
| `correlate_evidence` | Correlate bounded evidence and references without causal diagnosis | query*, environment_id, correlation_id | correlation.read | Configured source, scope and bounded result; no causal confirmation |
| `diagnose_api` | Read-only evidence-based hypothesis evaluation and planning | query*, environment_id, correlation_id | troubleshooting.read | Configured source, scope and bounded result; no causal confirmation |
| `diagnose_component` | Read-only evidence-based hypothesis evaluation and planning | query*, environment_id, correlation_id | troubleshooting.read | Configured source, scope and bounded result; no causal confirmation |
| `diagnose_gateway` | Read-only evidence-based hypothesis evaluation and planning | query*, environment_id, correlation_id | troubleshooting.read | Configured source, scope and bounded result; no causal confirmation |
| `discover_environment` | Discover bounded runtime inventory summary | query*, environment_id, correlation_id | runtime.discover | Configured source, scope and bounded result; no causal confirmation |
| `discover_gateway` | Discover authorized gateway installations | gateway_id, environment_id, correlation_id, namespace, gateway_type | gateway.discover | Configured source, scope and bounded result; no causal confirmation |
| `execute_probe_plan` | Structural trace or policy-controlled network observation | plan_id*, environment_id, correlation_id | probe.execute.active_readonly | Approved cached plan only; disabled by default; active network effects |
| `explain_correlation` | Explain deterministic rules, support and contradictions | result_id*, candidate_id, environment_id, correlation_id | correlation.read | Configured source, scope and bounded result; no causal confirmation |
| `explain_hypothesis` | Read-only evidence-based hypothesis evaluation and planning | hypothesis_id*, result_id, environment_id, correlation_id | troubleshooting.read | Configured source, scope and bounded result; no causal confirmation |
| `explain_trace` | Structural trace or policy-controlled network observation | trace_id*, environment_id, correlation_id | trace.read | Configured source, scope and bounded result; no causal confirmation |
| `find_known_issue` | Find prior incidents, known errors and runbooks; no causal conclusion | query*, environment_id, correlation_id | knowledge.issues.read | Configured source, scope and bounded result; no causal confirmation |
| `find_related_resources` | Find neighbors in observed runtime topology | query*, environment_id, correlation_id | topology.read | Configured source, scope and bounded result; no causal confirmation |
| `get_correlation_timeline` | Read a scoped cached correlation timeline | result_id*, environment_id, correlation_id | correlation.read | Configured source, scope and bounded result; no causal confirmation |
| `get_gateway_dependencies` | Read structural gateway dependencies without connectivity probes | query*, environment_id, correlation_id | gateway.dependencies.read | Configured source, scope and bounded result; no causal confirmation |
| `get_gateway_topology` | Read bounded gateway semantic topology | query*, environment_id, correlation_id | gateway.topology.read | Configured source, scope and bounded result; no causal confirmation |
| `get_knowledge_source_health` | Read source and derived index freshness | source_id*, environment_id, correlation_id | knowledge.sources.read | Configured source, scope and bounded result; no causal confirmation |
| `get_resource_topology` | Return a bounded runtime subgraph | query*, environment_id, correlation_id | topology.read | Configured source, scope and bounded result; no causal confirmation |
| `get_troubleshooting_plan` | Read-only evidence-based hypothesis evaluation and planning | result_id*, environment_id, correlation_id | troubleshooting.read | Configured source, scope and bounded result; no causal confirmation |
| `inspect_datasource` | Safe datasource metadata and mock health | datasource_id*, environment_id, correlation_id | datasource.read | Configured source, scope and bounded result; no causal confirmation |
| `inspect_events` | Inspect bounded related Event observations | query*, environment_id, correlation_id | event.read | Configured source, scope and bounded result; no causal confirmation |
| `inspect_gateway_component` | Inspect gateway component classification and evidence | query*, environment_id, correlation_id | gateway.components.read | Configured source, scope and bounded result; no causal confirmation |
| `inspect_logs` | Read bounded scoped observability evidence | query*, environment_id, correlation_id | observability.logs.read | Configured source, scope and bounded result; no causal confirmation |
| `inspect_metrics` | Read bounded scoped observability evidence | query*, environment_id, correlation_id | observability.metrics.read | Configured source, scope and bounded result; no causal confirmation |
| `inspect_observability` | Read bounded scoped observability evidence | query*, environment_id, correlation_id | observability.timeline.read | Configured source, scope and bounded result; no causal confirmation |
| `inspect_resource` | Inspect a canonical runtime resource | query*, environment_id, correlation_id | resource.read | Configured source, scope and bounded result; no causal confirmation |
| `inspect_trace` | Read bounded scoped observability evidence | query*, environment_id, correlation_id | observability.traces.read | Configured source, scope and bounded result; no causal confirmation |
| `list_capabilities` | Authorized capabilities and tools | environment_id, correlation_id | capability.read | Configured source, scope and bounded result; no causal confirmation |
| `list_datasources` | Safe datasource inventory | environment_id, correlation_id | datasource.read | Configured source, scope and bounded result; no causal confirmation |
| `list_environments` | Configured authorized environments | environment_id, correlation_id | environment.read | Configured source, scope and bounded result; no causal confirmation |
| `list_gateways` | Registered gateway metadata | environment_id, correlation_id | gateway.read | Configured source, scope and bounded result; no causal confirmation |
| `list_knowledge_sources` | List authorized knowledge source metadata | environment_id, correlation_id | knowledge.sources.read | Configured source, scope and bounded result; no causal confirmation |
| `plan_probes` | Structural trace or policy-controlled network observation | trace_id, troubleshooting_id, environment_id, correlation_id | probe.plan | Configured source, scope and bounded result; no causal confirmation |
| `search_internal_knowledge` | Search indexed internal untrusted knowledge | query*, environment_id, correlation_id | knowledge.search.internal | Configured source, scope and bounded result; no causal confirmation |
| `search_official_documentation` | Search curated indexed versioned documentation | query*, environment_id, correlation_id | knowledge.search.official | Configured source, scope and bounded result; no causal confirmation |
| `system_health` | Health of this MCP runtime only | environment_id, correlation_id | system.read | Configured source, scope and bounded result; no causal confirmation |
| `trace_gateway_component` | Structural trace or policy-controlled network observation | query*, direction, max_depth, environment_id, correlation_id | trace.read | Configured source, scope and bounded result; no causal confirmation |
| `trace_resource` | Structural trace or policy-controlled network observation | query*, direction, max_depth, environment_id, correlation_id | trace.read | Configured source, scope and bounded result; no causal confirmation |
