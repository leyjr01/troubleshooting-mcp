# Cenário futuro 3: expired_certificate

Status: especificação para sprint futura, sem execução de diagnóstico nesta Sprint 0.

Symptom: Certificado expirado.

Topology: nodes/edges canônicos do caminho afetado com ambiente e provenance.

Input evidence: Certificado referenciado e instante posterior ao vencimento.

Expected findings: interpretações limitadas ao suporte fornecido, com evidence_ids.

Root cause: candidato a validar, não conclusão predefinida sem evidência.

Expected rejected hypotheses: hipóteses alternativas contraditas pelas entradas devem ser registradas.

Expected recommendation: Rejeitar falha de autenticação de aplicação sem prova; recomendar renovação humana.
