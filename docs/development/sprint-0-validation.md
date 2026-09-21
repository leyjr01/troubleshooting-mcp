# Sprint 0 — validação de entrega

Executada em 2026-09-21, Windows, Python 3.12.10.

| Check | Resultado |
|---|---|
| pytest --cov=agt_mcp --cov-report=term-missing | 99 aprovados, 0 falhas; cobertura com branches 97,40% |
| ruff check . | PASS |
| ruff format --check . | PASS |
| mypy | PASS, 39 arquivos de produção |
| bandit -r src -q | PASS, supressões pontuais justificadas em testing.md |
| pip check | PASS |
| CLI validate-config com os cinco exemplos | PASS, sem resolver segredos |
| Mappings | Três exemplos validados pela suíte; CLI de incidente PASS |
| Documentação | Links locais, 10 ADRs, 24 ferramentas e 12 cenários verificados |

Revisão de segurança: exemplos e fixtures sintéticos, nenhum segredo real,
nenhuma conexão externa ou operação de escrita de infraestrutura. Contratos
de adapters usam fakes; testes de segurança cobrem autorização, ambiente,
timeouts, cancelamento, parsing e projeção conservadora de saída.

As métricas descrevem a fundação local. Não comprovam compatibilidade com
3scale/OpenShift ou proteção de um servidor produtivo: essas integrações,
o transporte MCP e a sanitização contextual não foram implementados.

Não há pendência bloqueante dentro da Sprint 0. Consulte o roadmap do README
para os próximos entregáveis. O commit e o estado Git finais são informados
no relatório de execução, evitando uma referência circular neste arquivo.
