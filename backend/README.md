# Backend do VIGIA Deslizamentos

Calcula o índice de risco de deslizamento dos 27 municípios do Alto Vale do
Itajaí a cada 6 horas, grava no SQLite, publica o `indices.json` que o site lê e
avisa pelo Telegram quem estiver inscrito. Roda no GitHub Actions; o bot que
atende os comandos é um Cloudflare Worker (`bot-worker/`).

A metodologia, os requisitos e as regras de negócio estão no [README do
projeto](../README.md). O formato dos arquivos trocados entre backend, repositório
e site está em [docs/contratos-de-dados.md](../docs/contratos-de-dados.md), e as
decisões sobre fontes, pesos do ensemble e horários em
[docs/decisoes/ensemble.md](../docs/decisoes/ensemble.md).

## Como está organizado

```
app/
  coleta/          chuva observada e membros do ensemble (Open-Meteo), estações (INMET)
  calculo/         chuva efetiva antecedente, subíndice, índice e agregação por dia-alvo
  classificacao/   classes de risco e probabilidades complementares
  modelos/         tipos compartilhados e persistência em SQLite
  exportacao/      monta o indices.json e publica por commit no repositório
  bot/             mensagens, inscrição, regra de aviso e envio
  pipeline.py      encadeia uma execução inteira
  main.py          `--uma-vez` (usado pelo Actions) ou serviço: long polling + agendador
config/
  municipios.json  parâmetros de cada município (incluir um é acrescentar um item)
scripts/
  gerar_estacoes.py  gera frontend/public/data/estacoes.json (roda uma vez)
  preparar_estado.py checkpoint do WAL do vigia.db antes do commit na branch estado
deploy/
  vigia.service    unidade systemd
tests/             a suíte; nenhum teste da suíte padrão acessa a rede
```

Dois princípios atravessam o código: o **cálculo é puro** (sem rede, banco,
relógio ou variáveis de ambiente) e **só `main.py` lê `os.environ`** e cria
cliente HTTP e conexões SQLite. Tudo o mais recebe essas dependências por
parâmetro — é o que permite testar o sistema inteiro sem rede.

## Instalação

Python 3.12 ou mais novo.

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e .          # Windows: .venv\Scripts\pip
cp .env.exemplo .env                # preencha os valores
```

### Dependências travadas

O CI (`ci.yml`) e o pipeline (`pipeline.yml`) não instalam o projeto: instalam só as
dependências, pelo `requirements.lock`, com versões fixas, hashes conferidos e apenas
wheels (`pip install --only-binary :all: --require-hashes -r requirements.lock`).

O `requirements.lock` é exportado do `uv.lock`. Sempre que mudar a lista de
`dependencies` do `pyproject.toml`, regenere os dois dentro de `backend/` e commite
os arquivos juntos:

```powershell
py -m pip install uv
py -m uv lock --python 3.12
py -m uv export --frozen --format requirements.txt --no-emit-project -o requirements.lock
```

### Variáveis de ambiente

Obrigatórias — a falta de qualquer uma faz o processo sair com código 2,
nomeando a que falta:

| Variável | Para que serve |
|---|---|
| `TELEGRAM_TOKEN` | Token do bot, obtido com o [@BotFather](https://t.me/BotFather) |
| `GITHUB_TOKEN_DADOS` | Token *fine-grained* com permissão só de `contents: write` neste repositório. No Actions vem do secret `TOKEN_DADOS` (veja a seção do Actions). Local, use um valor falso |
| `GITHUB_REPO` | Repositório de publicação, no formato `dono/repo`. Local, use um valor falso: nenhuma execução local publica na `main` |
| `SITE_URL` | URL pública do site, usada nas mensagens do bot |
| `DB_PATH` | Arquivo do banco SQLite, num disco persistente |
| `LOG_PATH` | Arquivo de log |

Opcional:

| Variável | Para que serve |
|---|---|
| `INMET_TOKEN` | Token da API do INMET, solicitado por e-mail a `cadastro.act@inmet.gov.br`. Sem ele o sistema roda igual; só a comparação de conferência entre a chuva medida e a calculada deixa de ser registrada. |
| `VIGIA_SIMULACAO` | **Só para demonstração.** Com `1`, o bot ganha o comando `/simular`, que envia a mensagem de aviso de cada classe de risco sem chuva real, sem gravar classe notificada e sem publicar nada. Fica vazia em produção; o comando será removido antes do deploy (`docs/pendencias.md`). No Actions vem da variável `VIGIA_SIMULACAO`. |
| `VIGIA_WORKER_URL` | URL do Worker do bot. Com ela, os avisos usam os inscritos do Worker em vez dos do SQLite local. Vem sempre junto de `VIGIA_WORKER_SEGREDO` |
| `VIGIA_WORKER_SEGREDO` | Segredo compartilhado com o Worker, para listar e apagar inscritos |
| `BOT_JSON_PATH` | Onde gravar o `bot.json` com os textos do bot. Sem ele, o arquivo não é gerado |

O `.env` real **nunca** é versionado. Em produção ele vira o `EnvironmentFile`
do systemd, com permissão 600; no Actions, as variáveis vêm de secrets e variables
do repositório.

## Rodando

### No GitHub Actions (produção)

O workflow [`.github/workflows/pipeline.yml`](../.github/workflows/pipeline.yml)
roda `python -m app.main --uma-vez` às **3, 9, 15 e 21 UTC** (minuto 7, para fugir
do pico das horas cheias) e também por **Run workflow** na aba Actions. Em cada
execução ele:

1. restaura a branch órfã `estado` (com `vigia.db` e `bot.json`) na pasta `estado/`;
2. roda o pipeline, que busca os inscritos no Worker e envia os avisos;
3. publica o `indices.json` na `main` com o `TOKEN_DADOS`;
4. faz o checkpoint do WAL e commita o `vigia.db` e o `bot.json` na `estado`.

Se a branch `estado` não existir, é criada. Um erro de rede ao consultá-la falha o
job, em vez de recomeçar com estado vazio, o que repetiria avisos.

Configuração em Settings > Secrets and variables > Actions:

| Tipo | Nome | Para que serve |
|---|---|---|
| Secret | `TELEGRAM_TOKEN` | Token do bot |
| Secret | `TOKEN_DADOS` | PAT *fine-grained* `vigia_publicacao`, só este repositório, *Contents: Read and write*. Publica o `indices.json` na `main`. Tem validade: confira a data em github.com/settings/personal-access-tokens e renove antes. Vencido, a publicação falha com 401/403 e o run continua verde |
| Secret | `VIGIA_WORKER_SEGREDO` | Mesmo valor do secret do Worker |
| Secret (opcional) | `INMET_TOKEN` | Veja a tabela de variáveis |
| Variable | `VIGIA_WORKER_URL` | `https://vigia-bot.kaiquedeoliveira0412.workers.dev` |
| Variable | `SITE_URL` | URL pública do site |
| Variable | `VIGIA_SIMULACAO` | Com `1` só durante a demonstração; sai antes da entrega final |

> **O GitHub pode atrasar execuções agendadas** nos horários de pico, e **desativa
> o agendamento depois de 60 dias sem atividade** no repositório. Para reativar:
> aba Actions, workflow Pipeline, **Enable workflow**. Os commits diários do
> `indices.json` na `main` mantêm o repositório ativo; mesmo assim, confira em Actions
> que a última execução agendada é recente.

### Worker do bot

O Worker (`vigia-bot`, em `bot-worker/`) guarda os inscritos no D1 `vigia` e lê os
textos do `bot.json` da branch `estado`. Deploy e migrações:

```bash
cd bot-worker
npm ci
npx wrangler d1 migrations apply vigia --remote
npm run deploy
```

Os secrets do Worker são definidos uma vez com `npx wrangler secret put <NOME>`
(o valor é pedido no terminal): `TELEGRAM_TOKEN`, `TELEGRAM_WEBHOOK_SEGREDO` e
`VIGIA_WORKER_SEGREDO`. O webhook do Telegram aponta para `<URL do Worker>/telegram`
e é registrado com `setWebhook` (comando abaixo).

> **Rodar o `app.main` no seu PC derruba o bot.** O modo serviço
> (`python -m app.main`, sem `--uma-vez`) usa long polling, e o Telegram não
> mantém webhook e polling juntos: o `run_polling` **apaga o webhook do
> @VigiaDeslizamentosBot**, e o Worker deixa de receber mensagens. O `--uma-vez` não
> apaga o webhook, mas **não o rode no PC com `VIGIA_WORKER_URL` e
> `VIGIA_WORKER_SEGREDO` no `.env`**: ele leria os inscritos reais do D1 e decidiria a
> RN08 com um `vigia.db` local, diferente do da `estado`, mandando avisos repetidos
> aos inscritos reais. Depois de usar o modo serviço, refaça o webhook:

```powershell
# Dentro de backend/. Lê o .env sem mostrar os valores. TELEGRAM_WEBHOOK_SEGREDO
# é o mesmo valor do secret do Worker; guarde-o no .env local (não versionado).
$cfg = @{}
Get-Content .env | Where-Object { $_ -match '^\s*[A-Z_]+=' } | ForEach-Object {
  $k, $v = $_ -split '=', 2; $cfg[$k.Trim()] = $v.Trim()
}
$api = "https://api.telegram.org/bot$($cfg['TELEGRAM_TOKEN'])"
Invoke-RestMethod -Method Post "$api/setWebhook" -Body @{
  url          = "$($cfg['VIGIA_WORKER_URL'])/telegram"
  secret_token = $cfg['TELEGRAM_WEBHOOK_SEGREDO']
}
# Conferência:
(Invoke-RestMethod "$api/getWebhookInfo").result |
  Select-Object url, pending_update_count, last_error_message
```

Se `url` voltar vazia no `getWebhookInfo`, o webhook não está registrado; se
`last_error_message` vier preenchido, o Telegram está chegando ao Worker e
recebendo erro.

### Serviço (bot + agendador)

Alternativa ao Actions e ao Worker, para uso local ou em um servidor próprio.

O bot local em Python mostra um botão por município, sem as regiões; o teclado
por região é do Worker.

```bash
.venv/bin/python -m app.main
```

Um processo, um loop asyncio: o bot atende em long polling e o
`AsyncIOScheduler` dispara o pipeline às **3, 9, 15 e 21 UTC** (0, 6, 12 e 18 em
Brasília). Os horários são 9 h depois de cada rodada sinótica, porque o modelo
mais lento do ensemble (ECMWF) leva ~8 h para publicar a rodada — medido na
Tarefa 0, com a evidência em `docs/decisoes/ensemble.md` §7.

Uma execução perdida (máquina suspensa, reinício) é recuperada em até 1 h
(`misfire_grace_time`), várias perdidas viram uma só (`coalesce`) e duas
execuções nunca rodam ao mesmo tempo (`max_instances=1`).

### Execução manual

```bash
.venv/bin/python -m app.main --uma-vez
```

Faz uma execução, envia os avisos e sai. Códigos de saída: **0** em sucesso,
**1** quando nenhum município foi calculado, **2** quando a configuração está
incompleta e **3** quando o Telegram rejeitou o token. Os códigos 2 e 3 estão em
`RestartPreventExitStatus` da unidade systemd: são falhas permanentes, e
reiniciar a cada 10 s só poluiria o journal.

> **Pare o serviço antes** (só vale para quem usa o modo serviço em servidor próprio). Dois processos executando o pipeline gravam no mesmo
> banco e decidem os avisos a partir do mesmo estado: o resultado são **avisos
> duplicados** para os inscritos.
>
> ```bash
> sudo systemctl stop vigia
> sudo -u vigia .venv/bin/python -m app.main --uma-vez
> sudo systemctl start vigia
> ```

### Execução local, sem bot e sem publicar

```bash
.venv/bin/python -m scripts.rodar_local
```

Roda coleta, cálculo, gravação no SQLite e conferência com o INMET, mas não
envia avisos (só os conta no log) nem faz commit: grava o `indices.json` em
`frontend/public/data/`. `TELEGRAM_TOKEN` e `GITHUB_TOKEN_DADOS` precisam existir
no `.env`, mas qualquer valor serve.

Para o `npm run dev` do site ler esse arquivo em vez dos dados de exemplo, crie
`frontend/.env.development.local` (já ignorado pelo git) com:

```bash
PUBLIC_DADOS_URL=data/
```

> Esse `indices.json` local ocupa o mesmo caminho do que o pipeline publica na
> `main`. Não o commite, e apague a cópia local antes de um `git pull`.

### Gerar o `estacoes.json`

```bash
.venv/bin/python -m scripts.gerar_estacoes
```

Roda uma vez, e de novo quando a rede de estações do INMET mudar. O arquivo
gerado é versionado no repositório.

O campo chama-se `ibge_referencia`, não `ibge`: só duas estações ficam dentro de
municípios monitorados (A863 Ituporanga e A861 Rio do Campo) e a resposta do
INMET não traz código IBGE nenhum. É o município **mais próximo** dentro do raio
de corte, e `distancia_km` registra a distância real — estação de referência
regional, não local. O contrato
([docs/contratos-de-dados.md](../docs/contratos-de-dados.md)) traz a regra de
leitura para o site.

## Testes

```bash
cd backend
.venv/bin/python -m pytest              # suíte padrão, sem rede
.venv/bin/python -m pytest -W error     # como a revisão confere a saída
.venv/bin/python -m pytest -m rede      # só os testes que chamam a API de verdade
```

Os testes marcados `rede` ficam fora da suíte padrão (`addopts` em
`pyproject.toml`). Todo o resto roda com fixtures de respostas reais e dublês de
cliente HTTP: nenhum teste da suíte padrão abre conexão.

`bot-worker/test/fixtures/bot.exemplo.json` é gerado a partir de
`montar_bot_json` e lido pelos testes do Worker. Ao mudar o `bot.json`, regenere
e commite o arquivo:

```bash
VIGIA_REGERAR_FIXTURES=1 .venv/bin/python -m pytest tests/test_bot_json.py
```

## Implantação em servidor próprio (systemd)

Opcional: a produção atual roda no Actions e no Worker. Esta é a alternativa com
o processo em execução contínua.

```bash
# código
sudo install -d -o vigia -g vigia /opt/vigia
sudo -u vigia git clone https://github.com/KaiquedeOliveiraa/vigia-deslizamentos /opt/vigia
cd /opt/vigia/backend
sudo -u vigia python -m venv .venv
sudo -u vigia .venv/bin/pip install -e .

# dados e log, em disco persistente (o `StateDirectory` da unidade também o
# cria na primeira subida, com dono e permissão certos)
sudo install -d -o vigia -g vigia -m 750 /var/lib/vigia

# segredos
sudo install -d -m 755 /etc/vigia
sudo install -o vigia -g vigia -m 600 .env /etc/vigia/vigia.env

# serviço
sudo cp deploy/vigia.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vigia
sudo systemctl status vigia
```

No `.env` de produção, `DB_PATH` e `LOG_PATH` apontam para dentro de
`/var/lib/vigia` (o único caminho gravável que a unidade concede):

```
DB_PATH=/var/lib/vigia/vigia.db
LOG_PATH=/var/lib/vigia/vigia.log
```

Acompanhar:

```bash
sudo journalctl -u vigia -f        # saída do processo
sudo tail -f /var/lib/vigia/vigia.log
```

Cada execução registra uma linha com quantos municípios tiveram dados, quantos
ficaram sem, se a publicação deu certo e quantos avisos havia a tratar.

## Como o sistema se comporta quando algo falha

| Falha | O que acontece |
|---|---|
| Coleta de um município | Só ele vai para `municipios_sem_dados`; os outros seguem |
| Coleta de todos | Nada é gravado, nada é publicado, nenhum aviso é enviado — o último `indices.json` continua no ar (RNF04/UC06) e a classe notificada de cada município fica intacta |
| Um modelo do ensemble | Aquele membro é descartado; o cálculo segue com os demais, e `n_membros` no JSON mostra quantos entraram. Abaixo de 3 membros em qualquer dia-alvo, o município fica "sem dados" |
| Publicação no GitHub | O erro é registrado e a execução continua: os avisos **não** dependem da publicação |
| Worker fora do ar ao buscar os inscritos | Nada é enviado e a classe notificada não é gravada; a próxima execução tenta de novo |
| Envio a um chat que bloqueou o bot | As inscrições daquele chat são apagadas (RNF05) e o laço segue |
| Envio falhando por rede em todos os inscritos | A classe notificada não é gravada, e a próxima execução reenvia |
| INMET fora do ar ou sem token | Só a linha de comparação deixa de ser registrada; o índice não muda |
| Banco numa versão de schema que o código não conhece | `abrir()` falha na subida com as duas versões na mensagem, em vez de deixar a primeira gravação quebrar a cada 6 h em silêncio |

Uma queda do processo entre o envio de um aviso e a gravação da classe pode
repetir aquele aviso na execução seguinte. É a troca escolhida: repetir é
preferível a perder um aviso.
