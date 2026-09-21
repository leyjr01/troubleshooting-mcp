# Cenário futuro 1: backend_down

Status: especificação para sprint futura, sem execução de diagnóstico nesta Sprint 0.

Symptom: Backend indisponível.

Topology: nodes/edges canônicos do caminho afetado com ambiente e provenance.

Input evidence: Runtime/rota apontam ao backend e observações de falha na mesma janela.

Expected findings: interpretações limitadas ao suporte fornecido, com evidence_ids.

Root cause: candidato a validar, não conclusão predefinida sem evidência.

Expected rejected hypotheses: hipóteses alternativas contraditas pelas entradas devem ser registradas.

Expected recommendation: Não atribuir a DNS se resolução válida; recomendação de verificar disponibilidade, sem restart.
