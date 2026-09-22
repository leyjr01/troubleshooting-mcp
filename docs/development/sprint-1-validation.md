# Sprint 1 — resultado de validação

Status: PASS. Executado em 2026-09-21, Windows, Python 3.12.10.
Base: 20d66cf426ecd2ecea59f28243baed25e4d149b8.

## Dependências

FastMCP 4.0.5 foi a versão estável mais recente oferecida pelo índice consultado;
Requires-Python >=3.10. Foi instalado com constraints das versões previamente
instaladas. Todas as dependências da Sprint 0 mantiveram suas versões, verificadas
contra requirements.lock. Os 99 testes originais passaram após a instalação.
O lockfile é um snapshot pip de desenvolvimento para Windows/Python 3.12.10.
Instalação editável com esse lockfile como constraints e pip check: PASS.

## Checks finais

| Check | Resultado |
|---|---|
| pytest --cov=agt_mcp --cov-report=term-missing | 127 aprovados, 0 falhas |
| Cobertura com branches | 92,93%, mínimo 80% |
| Ruff lint | PASS |
| Ruff formatting | PASS |
| Mypy strict | PASS, 55 arquivos de produção |
| Bandit | PASS, sem novas supressões |
| Dependências | pip check PASS |
| Documentação | Links e estrutura de 11 ADRs validados |
| Arquitetura | Imports FastMCP/SDK isolados em mcp/ |
| STDIO | Subprocesso real, list_tools e discover_gateway PASS |
| HTTP local | Processo real, list_tools e system_health PASS |
| Host/Origin | Origem de navegador não autorizada rejeitada com HTTP 403 |

As execuções dos subprocessos não são incorporadas ao percentual de cobertura;
por isso runner.py aparece sem cobertura no processo principal, apesar dos testes
reais de transporte. Não foram adicionados testes artificiais para elevar esse número.

## Entrega e limites

Sete tools, schemas estruturados, ExecutionContext próprio, governança de tools,
registry de adapters, serviços, autorização por ambiente/permissão, timeout,
cancelamento, cleanup de startup parcial, projeções seguras e auditoria stderr.
Testes cobrem falhas simuladas, ausência de credenciais e isolamento entre ambientes.
Os contratos-base GatewayAdapter/DataSourceAdapter e ADRs 0001–0010 não mudaram.

Sem OpenShift/3scale reais, banco, RAG/LLM, remediação, OAuth corporativo, ingress,
TLS corporativo ou exportadores externos. Local-read-only confia no usuário do
sistema operacional e o HTTP só aceita loopback; não é uma configuração produtiva.
Resources/prompts foram avaliados e omitidos por ausência de caso de uso atual.

Veja [runtime e comandos](../architecture/mcp-runtime.md) e
[ADR-0011](../adr/0011-fastmcp-as-mcp-server-framework.md).
