# Incident Evidence Bundle v1.0.0

Contrato executável: agt_mcp.evidence.bundle.IncidentBundle, com JSON Schema
derivável. Não há writer/exporter de arquivos nesta sprint.

Layout futuro:
```text
incident/
  metadata.json
  topology.json
  timeline.json
  hypotheses.json
  findings.json
  recommendations.json
  evidence/<id>.json
  report.md
```

metadata contém schema_version, incident, environment e inventário de artefatos
com checksum. Os demais arquivos correspondem aos campos do modelo; evidências
mantêm hash/referência da origem, que não é substituído pelo hash do bundle.
timeline aponta a evidence_ids. report é uma apresentação, não nova fonte.
O formato lógico é JSON do IncidentBundle; múltiplos arquivos são apenas projeção
futura com escrita atômica, ACL e retenção definida antes de implementação.
Nenhum caminho fornecido por fonte pode virar filename sem normalização/validação.
Escopos e IDs devem resolver; root cause referencia finding, remediation referencia
recommendation e evidência referencia node. Nenhuma mistura entre ambientes.
