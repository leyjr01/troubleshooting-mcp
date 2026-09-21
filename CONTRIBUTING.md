# Contributing

Use Python 3.12+, .venv e instalação editável com extra dev.
Execute pytest --cov=agt_mcp, Ruff lint/format, mypy, Bandit e pip check antes
de propor mudança. Preserve fronteiras: core não importa vendor ou transporte.
Nova porta precisa de contrato e fake testável offline; integração exige sprint
própria, permissões mínimas e testes adversariais. Não adicionar dependência sem
justificativa documentada. Fixture artificial, sem credenciais ou ambientes reais.

Decisão estrutural exige ADR com contexto, decisão, consequências e alternativas.
Não renomear observação em conclusão nem aumentar confiança para satisfazer teste.
Mudanças de schema exigem compatibilidade/versionamento explícitos.
Revisar git diff e status; datasets, bundles reais, .env e .venv ficam ignorados.
