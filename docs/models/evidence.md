# Evidências, taxonomia e confiança

FACT: afirmação verificável delimitada por fonte/tempo, não opinião do modelo.
OBSERVATION: leitura concreta produzida por fonte, ainda sujeita a erro.
INFERENCE: interpretação derivada, nunca dado original.
HYPOTHESIS: explicação candidata a testar, pode ser inconclusiva.
FINDING: interpretação sustentada e documentada com evidências.
RECOMMENDATION: ação proposta a humano com base em findings; não execução.
Evidence só aceita FACT ou OBSERVATION e não possui campo conclusion/root_cause.

Provenance identifica fonte, ambiente, referência, instante de coleta e SHA-256.
raw_reference aponta a artefato sob acesso controlado; não transportar secrets
embutidos em URLs. Bundle valida ambiente e referências, mas não baixa artefatos
nem verifica automaticamente hashes nesta sprint.

## Critérios de Confidence (ADR-0008)

LOW: fonte única ou fraca, temporalidade/topologia incerta, evidência faltante
ou contradição material não resolvida. MEDIUM: suporte direto e relevante,
fonte identificada, relação temporal/topológica demonstrada, limitações explícitas.
HIGH: múltiplas evidências independentes relevantes, proveniência confiável,
mesma janela e caminho afetado, contradições relevantes reconciliadas.
Similaridade histórica auxilia a busca; nunca substitui prova do estado runtime.
Registrar supporting evidence, contradicting evidence, source reliability,
temporal relevance, topological relevance, historical similarity e rationale.
Avaliação qualitativa por responsável, não porcentagem/probabilidade.
Nesta sprint o modelo exige campos, não calcula nem certifica o nível atribuído.
