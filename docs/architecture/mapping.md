# Mapping Contract

MappingSpec é blueprint validado: schema_version, entity (Incident/Resource/
Dependency), source datasource/table/schema_name, fields target -> column.
Colunas/tabelas usam identificadores simples, nunca expressões SQL. Campos
canônicos desconhecidos, id ausente e extras são rejeitados. Parser safe YAML;
não há execução nem conexão. Exemplos em mappings/incidents, assets e topology.

Blueprint pode ser parcial: ambiente, provenance e defaults serão injetados
pela composição futura e objeto final deve passar validação do modelo canônico.
A validação do blueprint não afirma que a tabela/coluna existe. discover_schema
permitirá conferência controlada posterior, nunca leitura de dados para adivinhar
schema. MappingEngine é porta map_record(record, spec, provenance); sem implementador.

Coluna ROOT_CAUSE textual histórica não deve ser mapeada diretamente para
root_cause_finding_id: IDs e evidências devem ser construídos por etapa explícita.
Sem eval, templates executáveis, shell ou SQL livre. Não inventar transforms.
