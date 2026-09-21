# Cenário futuro 8: wrong_secret

Status: especificação para sprint futura, sem execução de diagnóstico nesta Sprint 0.

Symptom: Referência de credencial inadequada.

Topology: nodes/edges canônicos do caminho afetado com ambiente e provenance.

Input evidence: Metadados e falha de autenticação, nunca valor secreto.

Expected findings: interpretações limitadas ao suporte fornecido, com evidence_ids.

Root cause: candidato a validar, não conclusão predefinida sem evidência.

Expected rejected hypotheses: hipóteses alternativas contraditas pelas entradas devem ser registradas.

Expected recommendation: Não inferir valor errado só por 401; recomendar conferência autorizada.
