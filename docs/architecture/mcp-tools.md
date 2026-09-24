# Future MCP tool catalog

Sprint 5 implements opt-in correlate_evidence, get_correlation_timeline and
explain_correlation. Their executable contracts, permissions and bounded cache are
specified in [evidence correlation](evidence-correlation.md).

Sprint 4 implements five opt-in knowledge tools. Their typed inputs, permissions
and index-only behavior are specified in [knowledge contracts](knowledge-rag.md).

Sprint 3 implements semantic discover_gateway and the opt-in get_gateway_topology,
inspect_gateway_component and get_gateway_dependencies. See the executable
[3scale contracts](threescale-discovery.md); historical entries below remain conceptual
where their arguments or scopes differ from that contract.

Catálogo conceitual criado na Sprint 0. A Sprint 1 implementou sete tools locais,
incluindo discover_gateway em memória: veja [runtime MCP](mcp-runtime.md).
A Sprint 2 implementa discover_environment, inspect_resource, inspect_events,
find_related_resources e get_resource_topology: os contratos executáveis,
permissions e limites estão em [runtime discovery](runtime-discovery.md).
As demais entradas continuam planejadas; scopes com dois-pontos abaixo são
conceituais, não substituem as permissions internas do contrato executável.
Inputs comuns: identidade autenticada pela futura sessão, environment_id, request_id,
correlation_id e deadline/limites. O cliente não escolhe suas próprias permissões.
Outputs são canônicos e passam sanitização/ACL; erros usam taxonomia segura.
Permissões abaixo são scopes propostos do transporte, a mapear à allowlist interna;
não são roles Kubernetes já criadas. FastMCP é restrito à interface MCP (ADR-0011).

## discover_environment

Purpose: Inventariar ambiente autorizado.

Inputs: environment_id.

Outputs: Environment e Resources.

Permissions: inventory:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Restringir cluster/namespace.

## discover_gateway

Purpose: Identificar gateway e versão.

Inputs: environment_id, gateway_id.

Outputs: Gateway e provenance.

Permissions: gateway:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Não expor endpoint administrativo com userinfo.

## inspect_resource

Purpose: Observar recurso.

Inputs: environment_id, resource_id.

Outputs: Evidence.

Permissions: resource:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Remover conteúdo de secrets.

## inspect_logs

Purpose: Ler janela limitada de logs.

Inputs: environment_id, resource_id, start, end, limit.

Outputs: Evidence paginada.

Permissions: logs:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Sanitizar tokens e limitar bytes.

## inspect_events

Purpose: Ler eventos de runtime.

Inputs: environment_id, resource_id, window.

Outputs: Evidence.

Permissions: events:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Restringir janela e namespace.

## inspect_configuration

Purpose: Inspecionar configuração sanitizada.

Inputs: environment_id, resource_id.

Outputs: Evidence.

Permissions: configuration:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Não devolver credenciais ou connection strings.

## inspect_certificate

Purpose: Verificar metadados de certificado.

Inputs: environment_id, resource_id.

Outputs: Evidence de validade/emissor.

Permissions: certificate:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Nunca private key.

## inspect_dns

Purpose: Inspecionar registros/estado conhecido.

Inputs: environment_id, dns_resource_id.

Outputs: Evidence.

Permissions: dns:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Sem probes ou destinos arbitrários nesta fase.

## inspect_network

Purpose: Inspecionar políticas e dados observados.

Inputs: environment_id, resource_id.

Outputs: Evidence e Dependency.

Permissions: network:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Sem scan/replay ou alteração de policy.

## inspect_service

Purpose: Inspecionar serviço e seleção.

Inputs: environment_id, service_id.

Outputs: Resource e Dependency.

Permissions: service:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Isolamento por namespace.

## get_gateway_topology

Purpose: Obter grafo do gateway.

Inputs: environment_id, gateway_id, depth.

Outputs: Topology.

Permissions: topology:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Limitar profundidade e filtrar ACL.

## get_api_topology

Purpose: Obter caminho da API.

Inputs: environment_id, api_id, depth.

Outputs: Topology.

Permissions: topology:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Não vazar dependências de outro ambiente.

## trace_api

Purpose: Correlacionar caminho já observado.

Inputs: environment_id, api_id, window.

Outputs: Evidence e Dependency.

Permissions: trace:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Sem gerar chamadas à API.

## trace_request

Purpose: Consultar trace de requisição existente.

Inputs: environment_id, request_id.

Outputs: Evidence.

Permissions: trace:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Request ID não autoriza acesso por si só.

## diagnose_api

Purpose: Orquestrar diagnóstico evidence-first.

Inputs: environment_id, api_id, symptom, window.

Outputs: Hypothesis, Finding, Recommendation.

Permissions: diagnosis:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Nenhuma conclusão sem provenance.

## diagnose_gateway

Purpose: Orquestrar diagnóstico do gateway.

Inputs: environment_id, gateway_id, symptom.

Outputs: Findings e referências.

Permissions: diagnosis:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Sem remediação automática.

## diagnose_component

Purpose: Orquestrar diagnóstico de componente.

Inputs: environment_id, resource_id, symptom.

Outputs: Findings e referências.

Permissions: diagnosis:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Sem executar comandos sugeridos por logs.

## find_related_resources

Purpose: Buscar relações explícitas.

Inputs: environment_id, resource_id, depth.

Outputs: Resources e Dependencies.

Permissions: topology:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Não inferir edges factuais por similaridade.

## search_internal_knowledge

Purpose: Pesquisar conhecimento autorizado.

Inputs: environment_id, query, repository_ids, limit.

Outputs: KnowledgeChunks com citações.

Permissions: knowledge:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: ACL antes de retrieval, prompt injection como dado.

## search_official_documentation

Purpose: Pesquisar fontes oficiais permitidas.

Inputs: environment_id, query, provider, version.

Outputs: KnowledgeChunks com citações.

Permissions: knowledge:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Allowlist de fonte/versão e proteção SSRF.

## find_known_issue

Purpose: Consultar incidente semelhante.

Inputs: environment_id, symptom, window, limit.

Outputs: Incidents com provenance.

Permissions: incident:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Sem apresentar histórico como causa atual.

## find_runbook

Purpose: Buscar procedimento aplicável.

Inputs: environment_id, query, version.

Outputs: KnowledgeChunks.

Permissions: knowledge:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Runbook recomenda, não executa.

## inspect_datasource_schema

Purpose: Inspecionar metadados permitidos.

Inputs: environment_id, datasource_id, scope, limit.

Outputs: SchemaDescription.

Permissions: schema:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Sem amostra de linhas; tabelas/colunas sensíveis filtradas.

## generate_incident_report

Purpose: Renderizar bundle autorizado.

Inputs: environment_id, bundle_id.

Outputs: Relatório sanitizado e citações.

Permissions: report:read, ambiente autorizado e limites do contexto.

Side effects: nenhuma escrita externa; leitura e auditoria local controlada apenas.

Security considerations: Sem escrever em sistemas externos ou publicar automaticamente.
