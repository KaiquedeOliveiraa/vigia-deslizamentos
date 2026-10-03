# Backend do VIGIA Deslizamentos

Calcula o índice de risco de deslizamento dos seis municípios do Alto Vale do
Itajaí a cada 6 horas, grava no SQLite, publica o `indices.json` que o site lê e
avisa pelo Telegram quem estiver inscrito.

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
  main.py          processo: bot em long polling + agendador
config/
  municipios.json  parâmetros de cada município (incluir um é acrescentar um item)
scripts/
  gerar_estacoes.py  gera frontend/public/data/estacoes.json (roda uma vez)
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

### Variáveis de ambiente

Obrigatórias — a falta de qualquer uma faz o processo sair com código 2,
nomeando a que falta:

| Variável | Para que serve |
|---|---|
| `TELEGRAM_TOKEN` | Token do bot, obtido com o [@BotFather](https://t.me/BotFather) |
| `GITHUB_TOKEN_DADOS` | Token *fine-grained* com permissão só de `contents: write` neste repositório |
| `GITHUB_REPO` | Repositório de publicação, no formato `dono/repo` |
| `SITE_URL` | URL pública do site, usada nas mensagens do bot |
| `DB_PATH` | Arquivo do banco SQLite, num disco persistente |
| `LOG_PATH` | Arquivo de log |

Opcional:

| Variável | Para que serve |
|---|---|
| `INMET_TOKEN` | Token da API do INMET, solicitado por e-mail a `cadastro.act@inmet.gov.br`. Sem ele o sistema roda igual; só a comparação de conferência entre a chuva medida e a calculada deixa de ser registrada. |

O `.env` real **nunca** é versionado. Em produção ele vira o `EnvironmentFile`
do systemd, com permissão 600.

## Rodando

### Serviço (bot + agendador)

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

> **Pare o serviço antes.** Dois processos executando o pipeline gravam no mesmo
> banco e decidem os avisos a partir do mesmo estado: o resultado são **avisos
> duplicados** para os inscritos.
>
> ```bash
> sudo systemctl stop vigia
> sudo -u vigia .venv/bin/python -m app.main --uma-vez
> sudo systemctl start vigia
> ```

### Gerar o `estacoes.json`

```bash
.venv/bin/python -m scripts.gerar_estacoes
```

Roda uma vez, e de novo quando a rede de estações do INMET mudar. O arquivo
gerado é versionado no repositório.

O campo chama-se `ibge_referencia`, não `ibge`: nenhuma estação automática do
INMET fica dentro dos seis municípios (a mais próxima operante está a ~30 km) e
a resposta do INMET não traz código IBGE nenhum. É o município **mais próximo**
dentro do raio de corte, e `distancia_km` registra a distância real — estação de
referência regional, não local. O contrato
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

## Implantação (systemd)

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
| Envio a um chat que bloqueou o bot | As inscrições daquele chat são apagadas (RNF05) e o laço segue |
| Envio falhando por rede em todos os inscritos | A classe notificada não é gravada, e a próxima execução reenvia |
| INMET fora do ar ou sem token | Só a linha de comparação deixa de ser registrada; o índice não muda |
| Banco numa versão de schema que o código não conhece | `abrir()` falha na subida com as duas versões na mensagem, em vez de deixar a primeira gravação quebrar a cada 6 h em silêncio |

Uma queda do processo entre o envio de um aviso e a gravação da classe pode
repetir aquele aviso na execução seguinte. É a troca escolhida: repetir é
preferível a perder um aviso.
