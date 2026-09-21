# Configuração e credenciais

Precedência: defaults -> arquivos --file em ordem -> --environment-file ->
variáveis de ambiente permitidas -> resolução explícita do secret provider.
Mapas mesclam; listas substituem integralmente, evitando combinar identidades.
Os cinco exemplos possuem namespaces distintos e compõem uma Configuration.
Variáveis diretas: AGT_ENVIRONMENT, AGT_TIMEOUT_SECONDS, AGT_MAX_PAYLOAD_BYTES.
Valores de arquivo podem usar placeholder integral ${NAME}; indefinidos falham,
sem executar expressões ou substituir parcialmente URLs. Nunca interpolar um
segredo para um campo comum: somente CredentialReference para credenciais.
Não há auto-discovery de arquivos de ambiente nem carregamento de .env.

Secret provider tem precedência final apenas para o valor da credencial
referenciada, não pode alterar read_only, TLS ou permissão. Load não resolve
segredos e não cria conexão. EnvironmentVariableCredentialProvider é a única
implementação, exigindo ambiente e allowlist de nomes. Retorna SecretStr;
nunca registrar get_secret_value(). KubernetesSecret, Vault, File e ExternalSecret
seguirão CredentialProvider, com escopo, autenticação, cache/expiração e rotação
definidos na sprint de cada provider; não estão implementados.

Configuração rejeita campos extras, duplicatas YAML, anchors/aliases, tags
executáveis, UTF-8 inválido e documentos acima de 256 KiB. Timeout deve ser
positivo <=300s; payload <=1 MiB; TLS/verificação e read_only não podem ser
desativados. Nenhum threshold aqui classifica a qualidade de um gateway.
Enabled é intenção futura: não instancia integração nesta sprint.
Connection só aceita host/porta/database, sem DSN/senha ou userinfo na URL.
IDs duplicados, gateway apontando a datasource de outro ambiente ou ausente,
e credencial cross-environment falham. Provedores futuros não cadastrados podem
ser declarados, mas não executados; adapter resolver futuro deve falhar explicitamente.
