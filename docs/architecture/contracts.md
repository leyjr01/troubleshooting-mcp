# Gateway Adapter e Data Source Contract

Async foi escolhido porque as operações futuras serão I/O-bound e canceláveis.
Métodos exigem OperationContext (ambiente, principal, request/correlation IDs,
timeout, limites de itens e bytes). Dados canônicos na saída, sem objetos de
driver. IDs de vendor entram como referências/provenance, não novas dependências core.

## Lifecycle e execução

Uma instância pertence ao serviço/composição: connect(context), uso e close()
em finally. connect repetido pode ser idempotente, close deve ser idempotente.
Nenhuma operação de leitura antes de connect; falhar com ConnectionError.
Pooling pertence ao adapter por configuração/ambiente, nunca singleton global.
Não há pooling ou retries implementados. Futuro retry só em leitura idempotente,
limite/backoff explícitos dentro do deadline total, sem repetir autorização.
run_read verifica identidade, ambiente, allowlist e capabilities antes de iniciar
a ação e aplica asyncio.timeout. CancelledError propaga; adapter deve cooperar
com cancelamento, liberar recursos em finally e nunca capturar BaseException.
Python não pode interromper I/O bloqueante de um driver mal implementado:
contratos futuros exigem drivers async ou isolamento apropriado.

## DataSourceAdapter

capabilities; connect; health; query(Query, context); discover_schema; close.
Query contém coleção lógica, filtros escalares e limite/cursor: não aceita SQL
livre. Cada adapter futuro traduz campos autorizados e parâmetros vinculados.
discover_schema retorna schemas/tables/columns/types/relationships/indexes,
sem valores de linhas; limites de metadados e autorização também se aplicam.
UnsupportedCapabilityError para operação anunciada como não suportada.
Resultado Evidence exige observação/provenance, não string genérica de driver.

## GatewayAdapter

capabilities; connect; discover_gateway; get_products; get_backends; get_routes;
get_policies; get_dependencies; get_gateway_logs; get_health; trace_request; close.
Resource representa produto/backend/rota sem semântica 3scale no core.
trace_request lê um request já existente; não dispara tráfego, replay ou probe.
Policies/logs também são evidências não confiáveis. Ausência de suporte retorna
UnsupportedCapabilityError, não lista vazia fingindo sucesso.
ThreeScaleAdapter, Kong, Apigee, WSO2, Gravitee, Azure APIM, IBM API Manager e
Connectivity Link são extensões planejadas, não implementações desta sprint.

## Erros

ConfigurationError, AuthenticationError, AuthorizationError, ConnectionError,
TimeoutError, DataSourceUnavailable, GatewayUnavailable, SchemaMappingError,
EvidenceCollectionError, UnsupportedCapabilityError, SanitizationError.
São AGTError com código estável e mensagem segura sem payload. Exceções de driver
serão traduzidas preservando detalhes apenas em canal operacional sanitizado;
não retornar stacktraces ou valores brutos ao cliente.
