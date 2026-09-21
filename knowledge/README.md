# Knowledge repository convention

Estrutura futura: environments/, architecture/, systems/, applications/, apis/,
runbooks/, known-errors/, incidents/, topology/. Nenhuma informação real incluída.
Cada documento deverá declarar id, environment_ids, owner, revision, source,
classification/access_labels, valid_from, reviewed_at e relação com recursos.
Git revision é parte da provenance. Expiração/revisão são explícitas; runbook
não prova estado runtime. Proibir secrets, dumps e credenciais em commits.
Incidentes publicados devem ser sanitizados e ligados ao bundle autorizado.
Diretórios serão criados com conteúdo na sprint de ingestão, sem pastas vazias.
