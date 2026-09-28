# Instalação e uso — API Gateway Troubleshooting MCP v1.0.0

Guia operacional em português, baseado no código da release v1.0.0
(baseline `8f122eef16af3dbddbb4aa6edddd38e92813c709`). Inclui a instalação do
FastMCP Server, a execução deste projeto e as 38 ferramentas disponíveis.
Exemplos com domínios, IDs e namespaces ilustrativos exigem substituição pelos
valores autorizados do ambiente. Não contêm credenciais reais.

## Sumário

1. [Objetivo e arquitetura](#1-objetivo-e-arquitetura)
2. [Requisitos e escolha da instalação](#2-requisitos-e-escolha-da-instalação)
3. [Instalar Python, FastMCP e o projeto](#3-instalar-python-fastmcp-e-o-projeto)
4. [Configurar outro ambiente](#4-configurar-outro-ambiente)
5. [Executar e conectar clientes](#5-executar-e-conectar-clientes)
6. [Servidor existente e implantação em cluster](#6-servidor-existente-e-implantação-em-cluster)
7. [Referência das 38 ferramentas](#7-referência-das-38-ferramentas)
8. [Fluxos de utilização](#8-fluxos-de-utilização)
9. [Operação contínua e solução de problemas](#9-operação-contínua-e-solução-de-problemas)
10. [Segurança, software gratuito e licenças](#10-segurança-software-gratuito-e-licenças)
11. [Checklist para outro ambiente](#11-checklist-para-outro-ambiente)
12. [Ambiente utilizado e limites de homologação](#12-ambiente-utilizado-e-limites-de-homologação)

## 1. Objetivo e arquitetura

O MCP reúne inventário, topologia, evidências, hipóteses e recomendações para
investigar gateways e recursos Kubernetes/OpenShift. As fontes são consultadas
em modo de leitura. Não há ferramenta para reiniciar Pods, alterar configuração,
executar comandos arbitrários, escrever em bancos ou aplicar recomendações.

```text
Cliente MCP -- STDIO ou HTTP /mcp --> FastMCP + autenticação/autorização
                                     |
                              serviços do projeto
                                     |
                runtime / 3scale / conhecimento / observabilidade / probes
```

FastMCP é o framework Python que transporta e registra as ferramentas. Instalar
somente `fastmcp` não instala as funções deste projeto. O servidor correto é
iniciado por `python -m agt_mcp serve`. Não é necessário criar outro `server.py`.

O **servidor MCP** é o processo Python; o **servidor/cluster observado** é a fonte
de dados. Podem estar em máquinas diferentes. Uma instalação existente de outro
servidor FastMCP não recebe automaticamente estas ferramentas: execute este
projeto como serviço separado e cadastre sua conexão no cliente.

Virtual Trace é um percurso estrutural da topologia, não captura de pacotes.
Probes são observações ativas de rede, desativadas por padrão e controladas por
política. Podem gerar tráfego e registros no destino. Hipóteses apoiadas por
evidência não equivalem à confirmação automática de causa raiz.

## 2. Requisitos e escolha da instalação

| Item | Referência desta release |
|---|---|
| Python | 3.12; execução local validada com 3.12.10 no Windows |
| FastMCP | `4.0.5`, instalado como dependência do projeto |
| SDK Kubernetes | `36.0.3`; necessário ao pacote, sem exigir cluster para a demonstração |
| Outras dependências diretas | Pydantic `>=2.10,<3`, PyYAML `>=6,<7`; resolução restringida pelo lock |
| Git | Necessário para checkout e fontes de conhecimento Git locais |
| Rede | Repositório/índice de pacotes durante instalação; depois somente fontes configuradas |
| Credenciais | Identidade de leitura do cluster; bearer separado para MCP HTTP remoto |
| Cluster | Opcional para demonstração sintética; necessário para descoberta real |
| Contêiner | Opcional; imagem Linux e execução real ainda precisam de qualificação |

Escolha o caminho:

| Situação | Procedimento |
|---|---|
| Este MCP já está funcionando | Obter URL `/mcp`, CA, bearer e ambientes autorizados; usar seção 5.3 |
| Há máquina Windows/Linux disponível | Instalar Python/venv/projeto e iniciar STDIO ou HTTP |
| Há cluster Kubernetes/OpenShift disponível | Usar seção 6 com identidade dedicada e namespace autorizado |
| Não há infraestrutura | Começar pela demonstração local; provisionar cluster somente após verificar requisitos e licenças |

O perfil de Pod fornece requests de 100m CPU/256 MiB e limites de 1 CPU/512 MiB
como ponto inicial, não dimensionamento validado de produção. Reserve espaço
para venv, artefatos e fontes. A demanda do cluster observado é adicional.
Um cliente remoto precisa alcançar o proxy TLS; o servidor precisa alcançar a
API do cluster, fontes habilitadas e apenas os destinos de probes autorizados.

## 3. Instalar Python, FastMCP e o projeto

### 3.1 Obter o código e preparar o interpretador

Instale Python 3.12 de [python.org](https://www.python.org/downloads/) ou do
repositório oficial da distribuição. No Linux, instale também o componente
`venv` disponibilizado pela distribuição, se necessário. Instale Git de
[git-scm.com](https://git-scm.com/downloads) ou do repositório oficial.
Não é necessário administrador para instalar os pacotes dentro do venv.

Windows PowerShell, a partir de um diretório de trabalho escolhido:

```powershell
git clone https://github.com/leyjr01/troubleshooting-mcp.git
Set-Location troubleshooting-mcp
git checkout 8f122eef16af3dbddbb4aa6edddd38e92813c709
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe --version
& .\.venv\Scripts\python.exe -m pip install --constraint requirements.lock .
& .\.venv\Scripts\python.exe -m pip check
```

Linux, a partir de um diretório gravável:

```sh
git clone https://github.com/leyjr01/troubleshooting-mcp.git
cd troubleshooting-mcp
git checkout 8f122eef16af3dbddbb4aa6edddd38e92813c709
python3.12 -m venv .venv
.venv/bin/python --version
.venv/bin/python -m pip install --constraint requirements.lock --constraint deploy/runtime-linux.constraints .
.venv/bin/python -m pip check
```

O checkout fixa o código funcional examinado por este guia; fica em detached HEAD
para reprodução. Para outra release, selecione seu commit aprovado e respectivos
locks. Não suponha que exista tag ou pacote publicado no PyPI. Os comandos Linux
são procedimentos de implantação a qualificar no destino.

Não é necessário ativar o venv; usar seu executável explicitamente evita o alias
da Microsoft Store e instalação no Python errado. Nos exemplos seguintes,
`python` significa esse executável: `.\.venv\Scripts\python.exe` no Windows
ou `.venv/bin/python` no Linux, salvo dentro de um venv já ativado.

### 3.2 Instalação explícita do FastMCP Server

A instalação do projeto acima já instala FastMCP. Para instalar ou conferir o
framework separadamente **no mesmo venv**, use:

```powershell
& .\.venv\Scripts\python.exe -m pip install --constraint requirements.lock "fastmcp==4.0.5"
& .\.venv\Scripts\python.exe -c "from importlib.metadata import version; print(version('fastmcp'))"
& .\.venv\Scripts\fastmcp.exe version
```

```sh
.venv/bin/python -m pip install --constraint requirements.lock --constraint deploy/runtime-linux.constraints 'fastmcp==4.0.5'
.venv/bin/python -c "from importlib.metadata import version; print(version('fastmcp'))"
.venv/bin/fastmcp version
```

A versão esperada é `4.0.5`. Este projeto utiliza o pacote independente
`fastmcp`, não a API `mcp.server.fastmcp` do SDK antigo. Não atualizar o framework
isoladamente para resolver um erro de configuração. Consulte a
[instalação oficial do FastMCP](https://gofastmcp.com/getting-started/installation).

### 3.3 Alternativa: wheel aprovado

Receba de uma origem confiável o wheel, `SHA256SUMS`, locks e os arquivos de
configuração da mesma revisão. O wheel contém o runtime; o checkout/sdist
fornece exemplos, documentação e manifests. Confira o hash antes de instalar:

```powershell
Get-FileHash dist/api_gateway_troubleshooting_mcp-1.0.0-py3-none-any.whl -Algorithm SHA256
& .\.venv\Scripts\python.exe -m pip install --constraint requirements.lock dist/api_gateway_troubleshooting_mcp-1.0.0-py3-none-any.whl
```

Compare o hash com o manifesto confiável. No Linux, use `sha256sum -c SHA256SUMS`
no diretório que contém os artefatos e acrescente a constraint Linux à instalação.
Para produzir os artefatos, siga os comandos de build e clean-install em
[release/commands](docs/release/commands.md). Não se precisa de extras `[dev]`
para executar o MCP. Ambientes sem internet exigem wheelhouse aprovado com todas
as dependências da plataforma e instalação `--no-index --find-links`.

## 4. Configurar outro ambiente

### 4.1 Arquivos, precedência e habilitação

Os arquivos `--file` são combinados na ordem informada; o último prevalece.
Depois aplica-se `--environment-file`, seguido de overrides de ambiente e
interpolação. Mapas são mesclados; **listas são substituídas integralmente**.
Overrides de aplicação: `AGT_ENVIRONMENT`, `AGT_TIMEOUT_SECONDS` e
`AGT_MAX_PAYLOAD_BYTES`. `${NOME}` só é aceito como valor completo e a variável
deve existir. As opções CLI `--transport` e `--port` substituem esses campos.

```sh
python -m agt_mcp validate-config --file config/server/local.example.yaml --file config/site.local.yaml
python -m agt_mcp serve --file config/server/local.example.yaml --file config/site.local.yaml
```

Crie `config/site.local.yaml` localmente, sem segredos. Esse padrão está no
`.gitignore`. O validador verifica estrutura e referências, sem conectar ou
resolver credenciais. YAML com campos desconhecidos, IDs duplicados, aliases
ou chaves duplicadas é rejeitado. Limite de arquivo: 256 KiB.

Uma ferramenta requer, simultaneamente: presença em `mcp.server.enabled_tools`,
permissão em `mcp.server.authorization.permissions`, ambiente autorizado e
backend/capacidade disponíveis. O padrão de autorização é `deny-all`.
O exemplo local habilita sete ferramentas; não espere encontrar as 38 nele.
Ao ampliar uma lista, preserve explicitamente os itens que ainda serão usados.
Não conceda todas as permissões apenas para fazer uma chamada passar.

### 4.2 Configurações de referência

| Necessidade | Arquivo e alterações necessárias |
|---|---|
| Demonstração sem cluster | [local.example.yaml](config/server/local.example.yaml): ambiente `demo`, gateway `gateway-01`, datasource `memory-source` |
| Kubernetes existente | [kubernetes.example.yaml](config/server/kubernetes.example.yaml): contexto, cluster, arquivo kubeconfig, namespace, IDs e ACLs |
| OpenShift/3scale | [threescale.example.yaml](config/server/threescale.example.yaml): runtime, APIManager, gateway, escopo e permissões |
| Conhecimento interno | [local-git.example.yaml](config/knowledge/local-git.example.yaml): caminho local revisado, fontes habilitadas e ACLs |
| Documentação oficial curada | [official-docs.example.yaml](config/knowledge/official-docs.example.yaml): corpus autorizado e versão do produto |
| Histórico | [incident-source.example.yaml](config/knowledge/incident-source.example.yaml): fonte e mapeamento de incidentes |
| Observabilidade | [observability.example.yaml](config/server/observability.example.yaml): fontes, URL/TLS, bindings e escopo |
| Probes | [probes.example.yaml](config/server/probes.example.yaml): destinos confiáveis, política e autorização explícita |

### 4.3 Kubernetes fora e dentro do cluster

Fora do cluster, copie o exemplo Kubernetes para `config/runtime.local.yaml` e
configure `runtime.authentication.mode: kubeconfig`, caminho dedicado, contexto
explícito e cluster correspondente. Não reutilize identidade administrativa.
Plugins `exec` de kubeconfig são rejeitados; providencie credencial compatível
com a política do projeto. Preserve a verificação TLS e a CA correta.

```sh
python -m agt_mcp validate-config --file config/runtime.local.yaml
python -m agt_mcp serve --file config/runtime.local.yaml
```

Dentro do cluster, use `mode: in-cluster` e a ServiceAccount dedicada do
[perfil base](deploy/base/configmap.yaml). Autorize somente namespaces nomeados.
Para outros namespaces, crie Role/RoleBinding de leitura em cada destino,
mantendo o namespace de origem da ServiceAccount no binding. Não é preciso
conceder acesso à API de Secrets nem criar ClusterRoleBinding genérico.

### 4.4 Conhecimento e observabilidade

O CLI inicia com índice de conhecimento vazio. Configurar uma fonte não a
ingere. Um fluxo administrativo deve chamar `runtime.knowledge.refresh` e
servir **a mesma instância Runtime**; o índice é local ao processo. O roteiro e
exemplo de integração estão em [knowledge-ingestion](docs/development/knowledge-ingestion.md).
Não há comando CLI de ingestão, clone/fetch automático, worker permanente ou
base vetorial persistente prometidos nesta versão. Formatos: Markdown, texto,
YAML e JSON. Buscas de documentação oficial consultam o corpus local curado;
não pesquisam a internet ao vivo.

Prometheus possui adaptador de leitura com consultas predefinidas; não recebe
PromQL arbitrário do cliente. Configure fontes e associações a recursos reais.
Logs e traces usam adaptadores em memória/fixtures nesta release: instalar
Loki, Elasticsearch ou Jaeger não cria integração automaticamente. Fontes
ausentes devem permanecer desabilitadas, com limitação registrada.

## 5. Executar e conectar clientes

### 5.1 STDIO — reprodução local

```powershell
& .\.venv\Scripts\python.exe -m agt_mcp validate-config --file config/server/local.example.yaml
& .\.venv\Scripts\python.exe -m agt_mcp serve --file config/server/local.example.yaml
```

No Linux, use `.venv/bin/python` nos mesmos argumentos. STDIO aguarda mensagens
MCP; não apresenta interface web. Normalmente o cliente inicia o subprocesso,
portanto não mantenha outro servidor manual para esse mesmo cliente.

Salve o exemplo abaixo como `client_example.py` e execute com o Python do venv,
a partir da raiz do checkout:

```python
import asyncio
import sys

from fastmcp import Client


async def main():
    configuration = {
        "mcpServers": {
            "agt": {
                "command": sys.executable,
                "args": [
                    "-m", "agt_mcp", "serve", "--file",
                    "config/server/local.example.yaml",
                ],
            }
        }
    }
    async with Client(configuration) as client:
        print([tool.name for tool in await client.list_tools()])
        for name, arguments in [
            ("system_health", {}),
            ("list_environments", {}),
            ("discover_gateway", {"gateway_id": "gateway-01"}),
        ]:
            result = await client.call_tool(name, arguments)
            print(result.structured_content)


asyncio.run(main())
```

Para outro cliente compatível com configuração `mcpServers`, use o caminho
absoluto do Python do venv e caminhos absolutos dos YAMLs, ou defina o diretório
de trabalho conforme o cliente. No JSON Windows, escape barras (`C:\\...`).
Variáveis adicionais necessárias ao subprocesso devem ser encaminhadas
explicitamente via `env`, sem gravar credenciais no arquivo compartilhado.
STDIO usa stdout para o protocolo e stderr para logs.

### 5.2 HTTP local e HTTP autenticado

Demonstração restrita à própria máquina:

```sh
python -m agt_mcp serve --file config/server/local.example.yaml --transport http --port 8000
```

Endpoint: `http://127.0.0.1:8000/mcp`. Para bearer local ou publicação protegida,
crie `config/http.local.yaml` com o fragmento abaixo. O segredo deve ser injetado
na variável `AGT_HTTP_TOKEN` pelo mecanismo protegido do operador, sem aparecer
no YAML ou na linha de comando:

```yaml
mcp:
  server:
    transport: http
    host: 127.0.0.1
    port: 8000
    allowed_hosts: [127.0.0.1]
    http_token:
      provider: environment
      reference: AGT_HTTP_TOKEN
      environment_id: demo
```

```sh
python -m agt_mcp validate-config --file config/server/local.example.yaml --file config/http.local.yaml
python -m agt_mcp serve --file config/server/local.example.yaml --file config/http.local.yaml
```

O token precisa ter ao menos 32 caracteres ASCII não brancos e respeitar o limite
de 4096 bytes. A validação offline não confirma sua existência; a inicialização
HTTP o resolve e falha se inválido. Para publicação, configure `host: 0.0.0.0`,
hostnames exatos em `allowed_hosts`, bearer e proxy TLS confiável. A lista não
aceita URL, porta ou wildcard. O ID da credencial deve pertencer às ACLs do
servidor. Troca de token exige reinício. Não exponha HTTP sem TLS a rede não confiável.

### 5.3 Conectar a uma instância existente

Instale FastMCP no venv do cliente; não é necessário instalar o servidor do
projeto nessa máquina. Receba do operador a URL, CA e credencial. Configure
`AGT_MCP_URL` e `AGT_MCP_TOKEN` por mecanismo local protegido. Exemplo:

```python
import asyncio
import os

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def main():
    transport = StreamableHttpTransport(
        url=os.environ["AGT_MCP_URL"],
        headers={"Authorization": "Bearer " + os.environ["AGT_MCP_TOKEN"]},
    )
    async with Client(transport) as client:
        for tool in await client.list_tools():
            print(tool.name, tool.input_schema)
        result = await client.call_tool("system_health", {})
        print(result.structured_content)


asyncio.run(main())
```

Use HTTPS e confiança na CA do ambiente; não desative verificação TLS.
O inventário de `list_tools()` é o contrato efetivamente exposto, podendo ser
menor que 38. Ele é método do protocolo MCP, não uma 39ª ferramenta de negócio.
Veja os [transportes oficiais FastMCP](https://gofastmcp.com/clients/transports).

### 5.4 Health checks

```powershell
Invoke-RestMethod http://127.0.0.1:8000/livez
Invoke-RestMethod http://127.0.0.1:8000/readyz
```

```sh
curl --fail http://127.0.0.1:8000/livez
curl --fail http://127.0.0.1:8000/readyz
```

`/livez` indica vida do processo. `/readyz` retorna 200 após inicialização e 503
quando não pronto. São respostas mínimas; não verificam saúde de Kubernetes,
Prometheus ou bancos. `system_health` requer autenticação/autorização MCP e
expõe versão, uptime, ambiente e quantidades de registros.

## 6. Servidor existente e implantação em cluster

### 6.1 Processo persistente em Linux ou Windows

Em um host existente, use conta de serviço sem privilégios, diretório de
instalação legível, configuração protegida e Python absoluto do venv. Para
serviço de rede, use HTTP; STDIO pertence ao ciclo de vida de seu cliente.

Modelo Linux para `/etc/systemd/system/agt-mcp.service` (adapte caminhos e crie
previamente a conta `agt-mcp`; configuração HTTP já deve estar validada):

```ini
[Unit]
Description=API Gateway Troubleshooting MCP
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=agt-mcp
WorkingDirectory=/opt/agt-mcp
ExecStart=/opt/agt-mcp/.venv/bin/python -m agt_mcp serve --file /etc/agt-mcp/server.yaml
Restart=on-failure
TimeoutStopSec=45
NoNewPrivileges=true
PrivateTmp=true
UMask=0077

[Install]
WantedBy=multi-user.target
```

Para credencial de arquivo, configure `provider: mounted-file` e
`reference: file:/etc/agt-mcp/token`, com leitura exclusiva da conta de serviço.
O modelo não instala automaticamente proxy, certificados ou kubeconfig.

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now agt-mcp
sudo systemctl status agt-mcp
sudo journalctl -u agt-mcp -n 100
sudo systemctl stop agt-mcp
```

No Windows, uma opção sem wrapper comercial é uma tarefa do Agendador de
Tarefas: gatilho de inicialização, conta dedicada, programa absoluto
`C:\agt-mcp\.venv\Scripts\python.exe`, argumentos
`-m agt_mcp serve --file C:\agt-mcp\config\server.local.yaml` e diretório inicial
`C:\agt-mcp`. Configure reinício em falha e proteção do arquivo de credenciais;
não coloque token nos argumentos. Esse modo persistente precisa ser validado
no host, inclusive captura de stderr e parada graciosa. O repositório não
entrega um serviço Windows nativo ou garante drenagem pelo Agendador.

### 6.2 Construir e instalar em Kubernetes existente

Use engine de contêiner gratuito compatível e origem oficial. `docker` abaixo
é a CLI de referência, não exigência de Docker Desktop/licença comercial.
Escolha um digest real aprovado para a imagem base Python 3.12 slim Linux:

```sh
docker build --build-arg PYTHON_IMAGE="$APPROVED_PYTHON_IMAGE" --build-arg RELEASE_VERSION=1.0.0 --build-arg VCS_REF="$APPROVED_COMMIT" --build-arg SOURCE_URL=https://github.com/leyjr01/troubleshooting-mcp -t agt-mcp:1.0.0 .
```

`APPROVED_PYTHON_IMAGE` precisa conter `@sha256:` seguido do digest completo.
Use o commit do código como `APPROVED_COMMIT`. Publique a imagem no registry
autorizado e substitua a referência do Deployment pelo digest resultante.
A imagem base, resolução Linux, build e admissão precisam ser validados no destino.

Antes de aplicar [deploy/base](deploy/base), revise namespace, environment ID,
cluster, ferramentas, ACLs, Hosts e imagem. Crie o namespace e, pelo mecanismo
de gestão de segredos do ambiente, o Secret `agt-mcp-auth` com chave `token`.
Não versione esse Secret. Então aplique os manifests revisados:

```sh
kubectl apply -f deploy/base/namespace.yaml
kubectl apply -f deploy/base/
kubectl rollout status deployment/agt-mcp -n agt-mcp
kubectl get pods,services -n agt-mcp
```

O token é montado em `/var/run/agt-auth/token`; o runtime lê o arquivo local,
nunca a API Kubernetes de Secrets. Service é ClusterIP; publicação externa
requer proxy/Ingress TLS. O Pod não eleva privilégios, usa root filesystem
somente leitura, descarta capabilities e recebe `/tmp` efêmero de 128 MiB.
Não há banco ou PVC obrigatório para caches/índices.

O [NetworkPolicy de exemplo](deploy/examples/networkpolicy.yaml) contém CIDR
reservado ilustrativo: substitua antes de aplicar. Inclua somente DNS, API,
fontes e destinos autorizados. Siga [Kubernetes](docs/deployment/kubernetes.md)
para RBAC, recursos, volumes e health checks completos.

### 6.3 OpenShift e 3scale existentes

Use a base anterior e [guia OpenShift](docs/deployment/openshift.md). Configure
`provider: openshift` e a semântica 3scale preservando `in-cluster`, bearer e ACLs.
O exemplo local 3scale não deve substituir inadvertidamente essas configurações.
Revise e aplique os manifests opcionais somente onde necessários:

```sh
oc apply -f deploy/openshift/reader.yaml
oc apply -f deploy/openshift/route.yaml
oc rollout status deployment/agt-mcp -n agt-mcp
```

O reader adiciona leitura de Routes/APIManagers. Substitua o host da Route e
adicione-o a `allowed_hosts`. A Route usa TLS edge; o trecho até o Pod é HTTP.
A SCC restrita deve atribuir UID; não conceda `anyuid` ou `privileged` para
contornar falha de admissão. Confirme a execução com UID arbitrário no destino.
Estes manifests instalam o MCP, não instalam OpenShift ou 3scale.

### 6.4 Novo laboratório

Para reproduzir o servidor efetivamente usado neste projeto, basta a instalação
Windows/Python/venv da seção 3 com o perfil sintético. Um laboratório de cluster
é uma etapa adicional. Se necessário, selecione distribuição comunitária e
instalador oficiais, valide recursos, SO, virtualização, licenças de imagens e
compatibilidade; registre versões/digests e execute o checklist da seção 11.

O laboratório OpenShift local anterior ficou `BLOCKED`: o host tinha Windows
Home, não suportado pelo CRC, e a memória livre observada era insuficiente.
Não houve cluster instalado a ser replicado. Os
[requisitos oficiais CRC](https://crc.dev/docs/installing/) devem ser conferidos
no novo host. Uma alternativa candidata é host Fedora compatível com preset
OKD, sujeito à qualificação; isso não comprova compatibilidade com Red Hat
3scale 2.16 nem concede direitos de uso de imagens comerciais.

## 7. Referência das 38 ferramentas

### 7.1 Convenções, entradas e respostas

Todas aceitam opcionalmente `environment_id` e `correlation_id` no nível externo.
O ambiente omitido utiliza o configurado, sujeito às ACLs; recomenda-se torná-lo
explícito em ambientes múltiplos. `correlation_id` acompanha a operação e não é
ID de resultado. IDs canônicos de recursos, componentes e resultados devem
ser copiados das respostas. Nomes de Pod não substituem IDs canônicos.

Nas tabelas, `*` indica obrigatório. Cada JSON é o objeto `arguments` de:
`await client.call_tool("nome_da_ferramenta", arguments)`. Acrescente ambiente
externo quando necessário. Valores como `resource-id`, `result-id`, `trace-id`
e `component-id` são placeholders, não identificadores preexistentes.

Tipos compartilhados usados pelas ferramentas:

| Tipo | Campos de entrada |
|---|---|
| `RuntimeQuery` | `namespace`, `kind`, `name`, `api_version`, `relationship`, `since` opcionais; `depth=1` (1–3), `limit=50` (1–200), `direction="both"` (`both`, `dependencies`, `dependents`) |
| `GatewayQuery` | `gateway_id`, `namespace`, `component_id` opcionais; `gateway_type` ausente ou `threescale`; `depth=2` (1–3), `limit=50` (1–200) |
| `RetrievalQuery` | `text`*; `repository_ids=[]`, `source_types=[]`, `filters=null`, `limit=10` (1–100, ainda limitado pela política) |
| `CorrelationQuery` | Ao menos um de `resource_id`, `gateway_id`, `component_id`; opcionais `namespace`, `symptom`, `time_window`; `topology_depth=2` (0–3), `include_knowledge=true`, `include_history=true` |
| `ObservabilityQuery` | `environment_id`* interno, `time_window`*; ao menos um de `resource_refs`, `gateway_component_refs`, `virtual_trace_id`, `trace_id`; demais campos abaixo |

`TimeWindow` tem `start` e `end` em ISO 8601 com fuso, sendo `start < end`.
`RetrievalQuery.filters` usa `KnowledgeMetadata`: `environment` (padrão `global`),
`system`, `application`, `gateway_type`, `product`, `product_version`,
`document_type` e `tags`. Consulte os enums exatos no `inputSchema` publicado.

Observabilidade aceita até 12 referências por lista, `signal_types` com valores
distintos `LOG`, `METRIC`, `TRACE`, `EVENT`, `correlation_id` interno opcional e
`filters` com `resource_uid`, `namespace`, `pod`, `service`, `gateway_component`,
`hostname`, `trace_id`, `request_id`, `correlation_id`. `metric_intent` pode ser
`availability` (padrão), `error_rate`, `latency`, `restarts`, `resource_usage`;
`metric_mode` é `range` (padrão) ou `instant`; `step_seconds=60` (1–3600) e
`limit=50` (1–200). O ID de ambiente interno deve corresponder ao escopo externo.
Políticas podem restringir mais que o schema.

Envelope comum, ilustrado com erro seguro:

```json
{
  "ok": false,
  "request_id": "request-id",
  "correlation_id": "correlation-id",
  "environment_id": "demo",
  "data": null,
  "error": "resource_not_found"
}
```

Em sucesso, `ok=true`, `error=null` e `data` contém o objeto específico. Leia
`structured_content` e confira `ok`, avisos e completude antes de usar dados.
Erro de validação MCP pode ocorrer antes desse envelope. Resultados parciais
não devem ser interpretados como ausência comprovada de um recurso.

Permissões das tabelas são o gate da ferramenta, não autorização para todas as
fontes transitivas. As composições também verificam capacidades e escopos de
runtime, gateway, observabilidade e probes. Todas dependem da habilitação na
configuração e das ACLs explicadas na seção 4.

### 7.2 Sistema e inventário — 7 ferramentas

Pré-requisito: registros configurados e ambiente autorizado. O perfil local
oferece este grupo com dados sintéticos. Consultas não são snapshot atômico do
ambiente real; saúde de datasource depende do adaptador implementado.

| Ferramenta / permissão | Parâmetros e exemplo | Retorno e utilização |
|---|---|---|
| `system_health` / `system.read` | Apenas comuns; `{}` | `server`, `version`, `status`, `uptime_seconds`, `configured_environment`, contagens de gateways/datasources; verifica o MCP |
| `list_capabilities` / `capability.read` | Apenas comuns; `{}` | Capacidades e ferramentas autorizadas; usar antes de planejar consultas |
| `list_environments` / `environment.read` | Apenas comuns; `{}` | Ambientes autorizados e metadados; selecionar o ID correto |
| `list_gateways` / `gateway.read` | Apenas comuns; `{}` | Gateways registrados; obter IDs sem presumir descoberta real |
| `list_datasources` / `datasource.read` | Apenas comuns; `{}` | Inventário seguro de fontes; não retorna segredos |
| `inspect_datasource` / `datasource.read` | `datasource_id`*; `{"datasource_id":"memory-source"}` | Detalhes/estado da fonte; saúde requer capacidade correspondente, sem diagnóstico de protocolo de banco |
| `discover_gateway` / `gateway.discover` | `gateway_id`, `namespace`, `gateway_type` opcionais; `{"gateway_id":"gateway-01"}` | Descoberta do gateway autorizado; sem ID, usar seleção por namespace/tipo quando backend suportar |

Limites/erros: ID inexistente ou fora do escopo, backend indisponível e capacidade
não suportada. `system_health` saudável não certifica datasources saudáveis.

### 7.3 Runtime e topologia — 5 ferramentas

Pré-requisito: adaptador Kubernetes/OpenShift, namespaces explicitamente
autorizados e RBAC de leitura. Todas exigem `query: RuntimeQuery`.

| Ferramenta / permissão | Exemplo de argumentos | Retorno e utilização |
|---|---|---|
| `discover_environment` / `runtime.discover` | `{"query":{"namespace":"example"}}` | Resumo de inventário observado, categorias e avisos de descoberta |
| `inspect_resource` / `resource.read` | `{"query":{"namespace":"example","kind":"Service","name":"api"}}` | Recurso canônico e evidências sanitizadas; seletor precisa identificar o alvo |
| `inspect_events` / `event.read` | `{"query":{"namespace":"example","limit":20}}` | Evidências de eventos, limite e truncamento; usar janela `since` com fuso se necessário |
| `find_related_resources` / `topology.read` | `{"query":{"namespace":"example","kind":"Service","name":"api","depth":1}}` | Vizinhos e relações observadas; dependências estruturais |
| `get_resource_topology` / `topology.read` | `{"query":{"namespace":"example","kind":"Service","name":"api","depth":2}}` | Grafo limitado, referências e relações não resolvidas |

Categorias podem estar `forbidden`, `unsupported`, `truncated` ou `unavailable`.
Considere `warnings` e relações não resolvidas. Uma relação estrutural não prova
conectividade. O sistema não exporta valores secretos de ConfigMaps/Secrets.

### 7.4 Semântica 3scale/APIcast — 3 ferramentas adicionais

`discover_gateway` já consta no grupo de inventário. Este grupo exige runtime
e adaptador semântico 3scale configurados; todas usam `query: GatewayQuery`.
Obtenha `gateway_id` e `component_id` da descoberta, não de suposições de naming.

| Ferramenta / permissão | Exemplo de argumentos | Retorno e utilização |
|---|---|---|
| `get_gateway_topology` / `gateway.topology.read` | `{"query":{"gateway_id":"gateway-id","depth":2}}` | Componentes e arestas semânticas, evidências e confiança |
| `inspect_gateway_component` / `gateway.components.read` | `{"query":{"gateway_id":"gateway-id","component_id":"component-id"}}` | Papel, presença, recursos e evidências de APIcast/System/Backend ou outro componente |
| `get_gateway_dependencies` / `gateway.dependencies.read` | `{"query":{"gateway_id":"gateway-id","depth":2}}` | Dependências internas/externas, referências e lacunas; não conecta a Redis/SQL |

Presença distingue `PRESENT`, `ABSENT_EXPECTED`, `ABSENT_OPTIONAL`, `EXTERNAL`,
`DISABLED` e `UNKNOWN`. Ausência observada, restrição RBAC e dependência externa
não são situações equivalentes. APIs ausentes podem produzir resultado parcial.

### 7.5 Conhecimento — 5 ferramentas

Pré-requisito: fontes autorizadas, índice preparado no mesmo processo e ACLs de
conteúdo. Retornos são referências não confiáveis, com proveniência e versão;
similaridade de recuperação não é confiança em diagnóstico.

| Ferramenta / permissão | Parâmetros e exemplo | Retorno e utilização |
|---|---|---|
| `list_knowledge_sources` / `knowledge.sources.read` | Apenas comuns; `{}` | Fontes visíveis, metadados e tipos disponíveis |
| `get_knowledge_source_health` / `knowledge.sources.read` | `source_id`*; `{"source_id":"internal-git"}` | Estado da fonte e atualização do índice; localizar índice vazio/desatualizado |
| `search_internal_knowledge` / `knowledge.search.internal` | `query: RetrievalQuery`*; `{"query":{"text":"APIcast indisponível","limit":5}}` | Chunks internos autorizados, relevância e proveniência |
| `search_official_documentation` / `knowledge.search.official` | `query: RetrievalQuery`*; `{"query":{"text":"APIcast TLS","limit":5}}` | Referências oficiais curadas; conferir versão/documento original |
| `find_known_issue` / `knowledge.issues.read` | `query: RetrievalQuery`*; `{"query":{"text":"erro 503","limit":5}}` | Incidentes, erros conhecidos e runbooks semelhantes; não prova repetição de causa |

Busca vazia pode indicar índice não populado, filtros ou ACLs. Não execute
instruções embutidas em documentos retornados. O MCP não altera o repositório fonte.

### 7.6 Correlação — 3 ferramentas

Pré-requisito: evidência runtime acessível. Conhecimento/histórico são
complementos identificados separadamente. Resultados consultados por ID precisam
pertencer ao mesmo escopo e permanecer no cache do processo.

| Ferramenta / permissão | Parâmetros e exemplo | Retorno e utilização |
|---|---|---|
| `correlate_evidence` / `correlation.read` | `query: CorrelationQuery`*; `{"query":{"resource_id":"resource-id","symptom":"erro 503"}}` | Resultado com contexto, evidências, relações/candidatos, timeline e avisos; guardar ID retornado |
| `explain_correlation` / `correlation.read` | `result_id`*, `candidate_id` opcional; `{"result_id":"result-id"}` | Regras, suporte, contradições e explicação do resultado/candidato |
| `get_correlation_timeline` / `correlation.read` | `result_id`*; `{"result_id":"result-id"}` | Timeline do resultado já calculado; não faz nova coleta |

Correlação temporal/topológica não confirma causalidade. Cache expirado,
reinício ou ID de outro ambiente exige nova coleta autorizada.

### 7.7 Hipóteses e plano — 5 ferramentas

Pré-requisito: fontes de evidência e capacidades de composição acessíveis.
As três operações de diagnóstico recebem `query: CorrelationQuery`.

| Ferramenta / permissão | Parâmetros e exemplo | Retorno e utilização |
|---|---|---|
| `diagnose_api` / `troubleshooting.read` | `query`*; `{"query":{"resource_id":"resource-id","symptom":"API retorna 503"}}` | Avaliações e recomendações no contexto da API/recurso; não recebe URL arbitrária |
| `diagnose_gateway` / `troubleshooting.read` | `query`*; `{"query":{"gateway_id":"gateway-id"}}` | Hipóteses sobre o gateway com evidências e lacunas |
| `diagnose_component` / `troubleshooting.read` | `query`*; `{"query":{"component_id":"component-id"}}` | Hipóteses sobre componente descoberto |
| `explain_hypothesis` / `troubleshooting.read` | `hypothesis_id`*, `result_id` opcional; `{"hypothesis_id":"hypothesis-id","result_id":"result-id"}` | Justificativa, suporte, contradições e evidência faltante; prefira informar resultado |
| `get_troubleshooting_plan` / `troubleshooting.read` | `result_id`*; `{"result_id":"result-id"}` | Etapas de inspeção recomendadas, requisitos e classes de segurança; não executa o plano |

Estados incluem `CANDIDATE`, `SUPPORTED`, `REJECTED`, `INCONCLUSIVE` e
`BLOCKED_BY_MISSING_EVIDENCE`. `SUPPORTED` deve ser lido junto às evidências e
limitações. Sintoma relatado pelo usuário não se transforma em evidência observada.

### 7.8 Virtual Trace e probes — 5 ferramentas

Pré-requisito: recursos/topologia confiáveis. Planejamento não autoriza execução.
Probes exigem configuração, permissão, contexto e destino aprovados.

| Ferramenta / permissão | Parâmetros e exemplo | Retorno e utilização |
|---|---|---|
| `trace_resource` / `trace.read` | `query: CorrelationQuery`*, `direction="outgoing"`, `max_depth` opcional; `{"query":{"resource_id":"resource-id"},"max_depth":2}` | Virtual Trace com hops, ramos e lacunas estruturais |
| `trace_gateway_component` / `trace.read` | Mesmos parâmetros; `{"query":{"component_id":"component-id"},"direction":"both"}` | Percurso estrutural do componente de gateway |
| `explain_trace` / `trace.read` | `trace_id`*; `{"trace_id":"trace-id"}` | Explicação do trace armazenado, suporte e limitações |
| `plan_probes` / `probe.plan` | `trace_id` ou `troubleshooting_id`; `{"trace_id":"trace-id"}` | Plano com alvos derivados de contexto confiável, bloqueios e orçamento; informar um contexto |
| `execute_probe_plan` / `probe.execute.active_readonly` | `plan_id`*; `{"plan_id":"plan-id"}` | Resultados de observações permitidas, status e evidências; produz tráfego de rede |

Direções de trace: `outgoing`, `incoming`, `both` (diferentes de RuntimeQuery).
Profundidade é limitada pela política a no máximo 3. Para executar, o operador
precisa configurar `probes.enabled: true` e `execution_mode: execute_allowed`,
além de hosts/CIDRs/portas/protocolos permitidos e endpoints associados a recursos.
`active_readonly` aparece no nome da permissão, não é valor de `execution_mode`.
O plano deve estar no cache autorizado; o cliente não fornece URL, shell ou
payload arbitrário. Repetir execução pode gerar nova observação e novo tráfego.
Consulte [probe-safety](docs/security/probe-safety.md) antes da ativação.

### 7.9 Observabilidade — 5 ferramentas

Todas exigem `query: ObservabilityQuery`. Modelo de argumentos para adaptar
ao período real do incidente (timestamps abaixo são apenas ilustrativos):

```json
{
  "environment_id": "dev",
  "query": {
    "environment_id": "dev",
    "resource_refs": ["resource-id"],
    "time_window": {
      "start": "2026-09-17T12:00:00Z",
      "end": "2026-09-17T12:10:00Z"
    },
    "limit": 20
  }
}
```

Use esse objeto como `arguments` em cada chamada abaixo; selecione fontes
realmente disponíveis. Pré-requisito: referências autorizadas, janela limitada
e bindings para fontes habilitadas. Não basta informar um nome de serviço.

| Ferramenta / permissão | Exemplo de chamada | Retorno e utilização |
|---|---|---|
| `inspect_logs` / `observability.logs.read` | `await client.call_tool("inspect_logs", arguments)` | Evidências de logs sanitizadas; nesta release, fonte em memória/fixture |
| `inspect_metrics` / `observability.metrics.read` | `await client.call_tool("inspect_metrics", arguments)` | Métricas de intenção predefinida; configure Prometheus para fonte real |
| `inspect_trace` / `observability.traces.read` | `await client.call_tool("inspect_trace", arguments)` | Evidências de spans/traces; fonte em memória/fixture, diferente de Virtual Trace |
| `build_evidence_timeline` / `observability.timeline.read` | `await client.call_tool("build_evidence_timeline", arguments)` | Evidências ordenadas e proveniência; timeline descritiva |
| `inspect_observability` / `observability.timeline.read` | `await client.call_tool("inspect_observability", arguments)` | Composição de fontes disponíveis e enriquecimento de diagnóstico |

O resultado composto oferece `id`, `query`, `status` (`COMPLETE`/`PARTIAL`),
`evidence`, `timeline`, `sources`, `warnings`, `virtual_trace` opcional e
`diagnosis`. Confira status por fonte: `OK`, `FORBIDDEN`, `UNAVAILABLE`,
`TIMEOUT`, `INVALID_DATA`, `UNSUPPORTED`. Evidências ordenadas não confirmam
causalidade; falha de uma fonte não deve ser escondida pela disponibilidade de outra.

## 8. Fluxos de utilização

1. **Primeira conexão:** `list_tools()` → `system_health` → `list_environments`
   → `list_capabilities`. Confirme versão e selecione ambiente. No perfil local,
   use `list_gateways` e `discover_gateway` com `gateway-01`.
2. **Recurso indisponível:** `discover_environment` → `inspect_resource` →
   `inspect_events` → `get_resource_topology`. Copie IDs retornados e examine
   categorias incompletas antes de interpretar ausência de endpoints.
3. **Gateway/3scale:** `discover_gateway` com namespace/tipo →
   `get_gateway_topology` → `inspect_gateway_component` →
   `get_gateway_dependencies`. Dependências externas não são automaticamente falhas.
4. **API com erro:** `correlate_evidence` → `diagnose_api` →
   `explain_hypothesis` → `get_troubleshooting_plan`. Mantenha IDs e ambiente
   entre chamadas; recomendações precisam de avaliação humana.
5. **Enriquecimento:** busque runbooks/documentação da versão correta; execute
   `inspect_metrics` ou `inspect_observability` com janela e referências reais.
   Separe histórico, referência documental e observação atual.
6. **Observação ativa autorizada:** `trace_resource` → `explain_trace` →
   `plan_probes` → revisar plano/destinos → `execute_probe_plan` somente com
   política e permissão de execução habilitadas. Não contorne plano bloqueado.
7. **Resultado inconclusivo:** conserve evidência faltante e status parcial;
   obtenha a capacidade/dado necessário e repita apenas a consulta afetada.

Os fluxos com cluster/fontes reais não funcionam apenas com o perfil sintético.
Não há ferramenta de exportação de arquivo arbitrário: o cliente pode conservar
respostas sanitizadas conforme a política local de retenção.

## 9. Operação contínua e solução de problemas

### 9.1 Logs, dados e ciclo de vida

Logs saem em stderr; auditoria registra IDs, principal, status e referências
hash de consultas/recursos. Não habilite logging de headers/token ou dump de
payloads para diagnosticar falhas. Encaminhe logs ao coletor aprovado do ambiente.

Caches e índices são efêmeros, limitados e isolados por escopo. Reiniciar perde
IDs de resultados/planos e exige repopular conhecimento. Não há HA ou banco
durável de incidentes. Faça backup de configuração sanitizada, fontes permitidas,
versão/locks, digest da imagem e procedimento de reconstrução. Credenciais
devem permanecer no mecanismo próprio de backup/rotação de segredos.

Para atualização, prepare novo venv/imagem do commit aprovado, valide a
configuração, faça smoke de health e leitura autorizada e então troque o serviço.
Preserve a versão anterior para rollback; restaure também configuração compatível.
Não atualize dependências em massa dentro do serviço ativo. Rotação de token e
alteração de configuração exigem restart/rollout. No cluster, respeite os 45 s
de grace period e a drenagem configurada (padrão 30 s).

### 9.2 Diagnóstico operacional

| Sintoma | Ação |
|---|---|
| Python abre Microsoft Store | Usar caminho absoluto do interpretador do venv ou `py -3.12` para criá-lo |
| `No module named agt_mcp` | Instalar o projeto no mesmo venv do comando/cliente; verificar diretório e executável |
| FastMCP ausente/versão incorreta | Conferir `importlib.metadata`, reinstalar em venv limpo com constraints; não trocar para SDK antigo |
| `pip check` falha | Recriar ambiente isolado com locks aprovados; revisar compatibilidade da plataforma |
| Configuração inválida | Executar `validate-config`; revisar IDs, listas substituídas e variáveis obrigatórias |
| Ferramenta não aparece | Conferir `enabled_tools` e reiniciar; comparar `list_tools()` com catálogo |
| `authorization` | Revisar ambiente, permissão da ferramenta e capacidades transitivas; não ampliar RBAC indiscriminadamente |
| HTTP 401 | Conferir bearer e referência de credencial; reiniciar após rotação |
| Host/Origin rejeitado | Usar hostname exato autorizado e cliente MCP; não liberar wildcard/origem arbitrária |
| API Kubernetes inacessível | Conferir contexto, CA, credencial, DNS e egress sem desabilitar TLS |
| RBAC forbidden / resultado parcial | Conferir RoleBinding no namespace e registrar categorias não observadas |
| `unsupported_capability` | Backend não implementa a operação; configurar fonte suportada ou registrar limitação |
| `resource_not_found` para resultado/plano | ID inválido, escopo diferente, expiração ou reinício; refazer coleta/planejamento |
| Conhecimento sem resultados | Confirmar ingestão no mesmo Runtime, filtros e ACLs; CLI padrão inicia vazio |
| Prometheus indisponível | Conferir URL, TLS, bindings, credenciais e janela; preservar status parcial |
| Probe bloqueada | Conferir contexto, plano, política, permissões e `execute_allowed`; bloqueio é padrão esperado |
| Timeout/truncamento | Reduzir janela, profundidade, namespaces ou limite; consultar orçamento antes de alterar configuração |
| Readiness falha com liveness normal | Verificar inicialização/configuração/credencial; não confundir com saúde downstream |

Não existe comando `doctor`. Ferramentas operacionais disponíveis: validação
offline, health endpoints, inventário de capacidades e consultas limitadas.
Mais detalhes: [operations](docs/deployment/operations.md) e
[runbook](docs/operations/runbook.md).

## 10. Segurança, software gratuito e licenças

Use somente software gratuito, open source, community edition ou recurso
oficialmente disponibilizado sem custo para este laboratório. Não use produto,
imagem, Operator, plugin ou serviço com licença paga, assinatura obrigatória,
trial condicionado a cobrança ou direito de uso não gratuito.

Obedeça licenças, direitos autorais, marcas, termos e restrições de distribuição.
Não copie, modifique ou redistribua conteúdo proprietário sem permissão; não
contorne entitlement, subscription, paywall, autenticação comercial ou licença.
Se não houver opção gratuita legalmente utilizável, registre `BLOCKED` e proponha
alternativa compatível. Antes de downloads relevantes, valide origem oficial e
condições de uso quando houver dúvida. Código upstream aberto não concede
direitos sobre imagens comerciais de um produto derivado.

O [inventário de dependências](docs/release/dependency-inventory.json) registra
versões e metadados de licença. Complete o inventário do laboratório com SO,
Python, Git, engine, imagens por digest, distribuição do cluster, Operators e
fontes documentais. Registre origem, versão, licença e evidência de uso gratuito.
Licenças desconhecidas e a licença de redistribuição ainda não especificada do
próprio projeto requerem decisão do mantenedor antes de distribuir artefatos a
terceiros; este guia não atribui uma licença nova.

Use identidade dedicada, menor privilégio, namespaces explícitos e TLS. O bearer
compartilhado não oferece SSO nem atribuição por pessoa. Credenciais nunca devem
ser colocadas em Git, exemplos, logs ou parâmetros de ferramentas. Conteúdo
externo é dado não confiável; não autoriza ações. Consulte
[SECURITY](SECURITY.md) e [revisão da release](docs/release/security-review.md).

## 11. Checklist para outro ambiente

- [ ] Registrar responsável, propósito, SO/arquitetura, recursos e escopo autorizado.
- [ ] Verificar origem oficial, gratuidade e licenças dos componentes escolhidos.
- [ ] Fixar commit, Python, locks e hashes/digests dos artefatos.
- [ ] Instalar em venv isolado; confirmar FastMCP 4.0.5 e `pip check`.
- [ ] Substituir IDs, contexto, cluster, namespaces e caminhos ilustrativos.
- [ ] Definir ferramentas e ACLs mínimas; revisar substituição de listas nos overlays.
- [ ] Preparar kubeconfig de leitura ou ServiceAccount/RoleBinding por namespace.
- [ ] Validar configuração offline; proteger referências de credenciais.
- [ ] Validar STDIO ou HTTP; configurar TLS/Hosts/bearer antes de acesso remoto.
- [ ] Conferir `list_tools`, `system_health`, `/livez` e `/readyz` quando HTTP.
- [ ] Fazer leitura de um recurso autorizado e confirmar rejeição fora do escopo.
- [ ] Verificar comportamento parcial para fontes/APIs ausentes e limites de consulta.
- [ ] Preparar ingestão no mesmo Runtime antes de prometer recuperação de conhecimento.
- [ ] Qualificar bindings Prometheus; registrar logs/traces reais como não integrados.
- [ ] Manter probes desativadas até revisão de política e autorização específica.
- [ ] Validar restart, rotação de credencial, reconstrução de índice e rollback.
- [ ] Executar a qualificação real aplicável e arquivar resultados sem segredos.
- [ ] Registrar cada requisito indisponível como limitação ou `BLOCKED`.

Para os testes reais opt-in, siga [real-lab](docs/development/real-lab.md).
O comando `pytest -m real_lab --real-lab` exige preparação explícita das variáveis
e infraestrutura ali descritas; não provisiona ambiente automaticamente. Não
substitua homologação real por testes sintéticos aprovados.

## 12. Ambiente utilizado e limites de homologação

| Componente/cenário | Situação documentada |
|---|---|
| Windows + Python 3.12.10 + FastMCP 4.0.5 | Validado localmente com venv |
| Instalação wheel em venv isolado | Validada na Sprint 11 |
| Cliente STDIO e ferramentas do exemplo local | Validados com dados sintéticos |
| HTTP/autenticação/health/lifecycle | Testes offline/loopback aprovados |
| Regressão Sprint 11 | 1.133 testes aprovados, 97,81% de cobertura de branches |
| Prometheus | Contrato de protocolo testado; sem homologação em servidor real |
| Linux/container/Kubernetes/OpenShift/3scale reais | Ainda não qualificados nesta baseline |
| Laboratório OpenShift local | `BLOCKED`; não houve instalação de cluster |
| Logs e traces externos | Adaptadores reais não entregues nesta versão |
| SSO, HA, armazenamento durável e remediação | Fora do escopo da v1.0.0 |

Os resultados acima são os resultados existentes da release, não uma declaração
de novos testes de infraestrutura executados durante a redação deste guia.
Referências: [validação Sprint 11](docs/release/sprint-11-validation.md),
[matriz de compatibilidade](docs/release/compatibility.md),
[contratos e limites](docs/release/contracts.md),
[catálogo gerado](docs/release/tool-catalog.md) e
[estado do projeto](PROJECT_STATE.md).
