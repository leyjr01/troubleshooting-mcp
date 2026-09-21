# API Gateway Troubleshooting MCP

Fundação modular para diagnóstico de gateways. Primeiro alvo futuro: Red Hat
3scale/APIcast em OpenShift. Sprint 0 entrega contratos, modelos, configuração
validada, segurança local e governança. Não há servidor MCP ou integração ativa.

## Goals e non-goals

Permitir múltiplos ambientes, clusters, gateways e fontes com conclusões
rastreáveis. Nesta sprint não acessar clusters, bancos, Git remoto, APIs, LLMs
ou executar remediação. Diagnóstico, RAG e correlação reais ficam para sprints futuras.

## Architecture

```text
MCP client -> future MCP transport -> application engines
  query / diagnosis / knowledge -> evidence correlation
  topology / mapping / retrieval -> read-only data access boundary
  DataSourceAdapter | GatewayAdapter | CredentialProvider
  future Git / DB / REST / Kubernetes | gateways
```

Core não importa adapters nem bibliotecas de fornecedores. Portas assíncronas,
modelos Pydantic e injeção de dependências, sem singletons de ambiente.
Veja [arquitetura](docs/architecture/overview.md) e [ADRs](docs/adr/README.md).

## Repository layout

- src/agt_mcp/core: modelos, erros e operações.
- gateways/base, datasources/base: contratos; demais subpacotes são reservas documentadas.
- configuration, credentials, security: configuração, resolução explícita de segredos e fronteiras locais.
- evidence, topology: modelos e validação de referências.
- mapping, rag: blueprints e portas; diagnostics/knowledge/mcp: extensões futuras.
- observability: eventos JSON sem payload bruto.
- config, mappings: exemplos artificiais; knowledge: convenções para repositórios futuros.
- tests/unit, contract, integration, scenarios, fixtures: validações offline.
- docs: arquitetura, modelos, segurança e desenvolvimento.

## Development setup

Python 3.12+ e Git. No PowerShell, na raiz do checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m agt_mcp --help
```

No Linux/macOS, use python3.12 e .venv/bin/python. Ativação é opcional;
nos comandos seguintes, python representa o executável da .venv.

```bash
python -m agt_mcp validate-config --file config/application.example.yaml --file config/datasources.example.yaml --file config/gateways.example.yaml --file config/rag.example.yaml --file config/diagnostics.example.yaml
python -m agt_mcp validate-mapping mappings/incidents/incident.example.yaml
python -m pytest --cov=agt_mcp
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m bandit -r src -q
python -m pip check
```

CLI retorna 0 no sucesso, 1 para configuração/mapping inválido, 2 para argumentos
inválidos. Não imprime valores de configuração nem resolve credenciais.
Todos os exemplos podem ser validados offline; fontes permanecem desabilitadas.
O comando sem arquivos valida defaults. Configuração de ambiente é fornecida
com --environment-file; veja [configuração](docs/architecture/configuration.md).

## Testing e current status

Fixtures são sintéticas, nenhum teste exige rede. Coverage mínimo configurado
em 80%, com branches e relatório de linhas; cobertura não prova segurança produtiva.
Testes de integração compõem componentes locais. Contratos usam fakes, nunca
drivers reais. A matriz de cenários descreve expectativas futuras, sem diagnóstico
simulado apresentado como funcionalidade pronta.
[Desenvolvimento](docs/development/testing.md) descreve os checks e suas limitações.
[Validação da Sprint 0](docs/development/sprint-0-validation.md) registra os resultados.

## Security principles

READ, DIAGNOSE, RECOMMEND; nenhuma operação de escrita externa.
Autorização e escopo precedem adapters; deadline obrigatório; recomendações
não executáveis. Sanitização inicial remove texto livre e campos desconhecidos.
Não resolve prompt injection por semântica: não há chamada ao modelo.
[SECURITY.md](SECURITY.md), [ameaças](docs/security/threat-model.md).

## Roadmap

1. Sprint 0: fundação, contratos, modelos e governança.
2. Sprint 1: primeiro adapter 3scale/runtime read-only com limites e RBAC verificados.
3. Sprints seguintes: descoberta, diagnóstico determinístico, evidências e cenários.
4. Conhecimento federado, mappings concretos e RAG com ACL/provenance.
5. Transporte MCP autenticado, observabilidade externa e hardening operacional.

Todos os textos do projeto são UTF-8. No Windows PowerShell use
Get-Content -Encoding UTF8 para leitura explícita.
