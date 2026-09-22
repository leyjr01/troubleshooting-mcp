# Arquitetura e limites

Evolução na Sprint 1: transporte FastMCP e application services locais implementados;
veja [runtime MCP](mcp-runtime.md) e ADR-0011. Engines de diagnóstico permanecem futuros.

Arquitetura hexagonal modular: core contém conceitos e portas usam modelos
canônicos. Application engines futuros orquestram portas, sem conhecer driver,
URL, SQL, kubectl ou particularidades de 3scale. O transporte MCP traduz entradas/
saídas, autenticação e erros, não regras de diagnóstico.

## Fluxo de diagnóstico futuro

Symptom -> Topology discovery -> Hypothesis generation -> Evidence collection ->
Evidence correlation -> Hypothesis validation -> Root cause candidates ->
Confidence -> Recommendation. Hipótese pode existir sem evidência, mas não
pode virar suportada/rejeitada sem referências apropriadas. Finding exige
evidência; bundle valida referências e ambiente. Não há engine nem LLM executando
essa sequência nesta sprint.

## Responsabilidades

Runtime State é observação temporal de recursos, logs e métricas; Knowledge é
documentação versionada; Historical Data são registros de incidentes/mudanças,
não prova do estado atual. Topology descreve relações e origem. Evidence guarda
observação; Inference interpreta; Recommendation propõe ação não executável.
Query/Diagnosis/Knowledge engines serão serviços distintos; correlação pode
usar topologia e conhecimento, mas não confunde grafo com índice vetorial.

Multi-cluster e multi-environment usam IDs explícitos em contextos, configuração,
provenance e bundles; instâncias recebem dependências. Não há conexão global.
Config permite inventário de ambientes distintos; cada request é restrito ao
ambiente autorizado. Cross-environment joins não são permitidos implicitamente.

## Dependências e escolhas

Python 3.12, Pydantic 2 para validação/JSON Schema, PyYAML com SafeLoader próprio
para configuração, biblioteca padrão para async/logging. Pytest/coverage, Ruff,
mypy/types-PyYAML e Bandit são ferramentas de desenvolvimento.
Não adicionar pandas, ORM, SDK Kubernetes, clientes HTTP ou bancos nesta sprint.
Na Sprint 0, MCP Python SDK foi avaliado e adiado. Na Sprint 1, FastMCP 4.0.5
foi escolhido e fixado, com seus imports restritos ao pacote mcp (ADR-0011).
Referências consultadas em 2026-09-21:
[Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) e
[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk).
Modelos com extra=forbid rejeitam campos desconhecidos; frozen não significa
imutabilidade profunda dos dicionários. Tratar instâncias como snapshots e
revalidar fronteiras; nunca usar model_construct para dados externos.
