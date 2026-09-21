# Topology Model

Grafo dirigido: nodes Resource e edges Dependency com source, target,
relationship, source_of_information, confidence e metadata.
ResourceKind: Gateway, API, Product, Backend, Route, Service, Pod, Database,
Certificate, Secret, ExternalService, Queue, DNS, Network.
Relationship: calls, routes_to, depends_on, uses, contains, selects,
authenticates_with, secured_by, stores_in, reads_from, writes_to, managed_by.
writes_to descreve uma dependência observada, não permissão para o agente escrever.

IDs duplicados, endpoints inexistentes e ambiente divergente são rejeitados.
Ciclos são permitidos (dependências reais podem ser cíclicas); descoberta futura
deve limitar profundidade e visited-set. Secret node guarda referência, nunca valor.
Grafo é estado versionado com proveniência; similaridade vetorial não cria edge
factual sem evidência. API.gateway_id será resolvido em composição futura;
Bundle é a fronteira atual para IDs de evidência/recursos e escopo.
