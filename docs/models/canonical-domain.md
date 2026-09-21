# Canonical Domain Model

Pydantic Model rejeita extras, limita textos/IDs e congela atribuições.
Datas usam timezone; timestamps ingênuos são inválidos. Dicionários são
extensões descritivas, não lugar para segredos. IDs são opacos no contexto do
ambiente; tipos não referenciam 3scale, OpenShift ou fornecedor obrigatório.

| Modelo | Responsabilidade |
|---|---|
| Environment | id/name/type/cluster/namespace/metadata; define escopo |
| Resource | id/environment/kind/name/provider/namespace/status/labels/annotations |
| API | Resource API com versão e gateway_id |
| Gateway | Resource gateway com versão e referência do endpoint |
| Dependency | relação dirigida com fonte da informação e confiança |
| Evidence | observação factual, timestamp, recurso, origem e raw_reference |
| Finding | interpretação com severidade e evidence_ids obrigatórios |
| Hypothesis | candidate/supported/rejected/inconclusive; referências pró/contra |
| Incident | sintoma, erro, recursos, origem, evidências e causa/remediação por referência |
| Recommendation | proposta baseada em findings/evidências, nunca executável |
| Provenance | source_id, ambiente, retrieved_at, referência e hash do conteúdo |
| Confidence | LOW/MEDIUM/HIGH e racional explícito para seis dimensões |
| IncidentBundle | agrega e valida referências e isolamento de ambiente |

root_cause_finding_id é opcional, não string de causa confirmada sem evidência.
Registros históricos com alegação textual não devem virar root cause validada
por simples mapping de coluna. Importador futuro deve guardar alegação como
histórica e construir evidências/linhagem.

Modelos geram JSON Schema com model_json_schema(); round-trip usa
model_dump_json/model_validate_json. Validação de forma não comprova verdade
nem redige conteúdo; tratamento de segurança ocorre antes da exposição.
