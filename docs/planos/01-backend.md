# Plano 01 — Backend (pipeline, banco, exportação e bot)

**Objetivo:** implementar o pipeline que calcula o índice GeoRisk a cada 6 horas, grava no SQLite, publica o `indices.json` e avisa os inscritos pelo Telegram.

**Base:** README (Metodologia, Funcionamento, Banco de dados, RN07, RN08, RN12) e [Contratos de dados](../contratos-de-dados.md).

**Stack:** Python 3.12, `requests`, `python-telegram-bot`, `APScheduler`, `sqlite3` (biblioteca padrão), `pytest`. pandas/NumPy só se o cálculo pedir; as funções abaixo funcionam com listas.

**Regra de trabalho:** em cada tarefa, escrever o teste primeiro, ver falhar, implementar o mínimo e ver passar. Commit ao fim de cada tarefa.

---

## Tarefa 0 — Spike: fonte das rodadas do ensemble

Antes de codificar a coleta, confirmar na documentação do Open-Meteo:

- [ ] Qual endpoint devolve a chuva horária das 168 h anteriores (parâmetro `past_days`) e em qual fuso (`timezone=UTC`).
- [ ] Qual endpoint devolve rodadas anteriores de um mesmo modelo (necessário para o *time-lagged ensemble* de até 36 h). Candidato: API de rodadas anteriores (*Previous Runs*).
- [ ] Quais modelos cobrem SC com precipitação horária (ex.: GFS, ECMWF IFS, ICON).
- [ ] Limite de chamadas do plano gratuito × volume previsto (6 municípios × pontos × modelos × 4 execuções/dia).

**Saída:** uma tabela em `docs/decisoes/ensemble.md` com modelos escolhidos, pesos fixos por atraso da rodada (0, 6, 12… 36 h) e por rodada 00/12 × 06/18, e o `n_min` de membros. Abaixo de `n_min`, o município vai para `municipios_sem_dados`.

> Esta tarefa fecha a lacuna "modelos e pesos a definir" e deve ser validada pela equipe antes das Tarefas 5 e 6. Registrar também o horário (UTC) em que cada rodada fica disponível, para fixar os horários do agendador.

## Tarefa 1 — Estrutura e configuração

**Arquivos:** `backend/pyproject.toml`, `backend/app/config.py`, `backend/config/municipios.json`, `backend/.env.exemplo`, `.gitignore`, `docs/indices.schema.json`, `backend/tests/test_config.py`

- [ ] Teste: carregar `municipios.json` retorna todos os municípios configurados, cada um com `ibge` de 7 dígitos, `limiar_mm > 0`, `mv_h > 0` e ao menos um ponto.
- [ ] Teste: arquivo com campo faltando levanta erro com o nome do campo.
- [ ] Implementar `carregar_municipios(caminho) -> list[Municipio]` (dataclass).
- [ ] Preencher `municipios.json` com os códigos IBGE (API de Localidades), `limiar_mm: 250`, `fonte_limiar: "GeoRisk, limiar hipotético padrão"`, `mv_h: 24` e o centroide de cada município.
- [ ] `.env.exemplo` com `TELEGRAM_TOKEN`, `TELEGRAM_BOT_USERNAME`, `GITHUB_TOKEN_DADOS`, `GITHUB_REPO` e `SITE_URL`; o `.env` real fica no `.gitignore`.
- [ ] Criar `docs/indices.schema.json` (JSON Schema do contrato). O frontend depende dele desde a sua Tarefa 2.

## Tarefa 2 — Chuva efetiva antecedente (EfR)

**Arquivos:** `backend/app/calculo/chuva_efetiva.py`, `backend/tests/test_chuva_efetiva.py`

- [ ] Testes:
  - 10 mm só na hora t=0 → EfR = 10.
  - 10 mm só em t=24 com MV=24 → EfR = 5.
  - 10 mm só em t=48 com MV=24 → EfR = 2,5.
  - série vazia → 0.
  - valores faltantes (`None`) → erro, não zero silencioso.
- [ ] Implementar `efr(chuva_horaria: list[float], mv_h: float) -> float`, com `chuva_horaria[0]` = hora mais recente, até 169 valores (t = 0…168).

## Tarefa 3 — Subíndice, índice ponderado e probabilidades

**Arquivos:** `backend/app/calculo/indice.py`, `backend/tests/test_indice.py`

- [ ] Testes:
  - `subindice(efr=100, rtotal=20, limiar=120) == 1.0`.
  - Índice com pesos iguais = média simples.
  - Pesos `[3, 1]` e subíndices `[1.0, 2.0]` → 1,25.
  - Probabilidades: subíndices `[0.5, 1.2, 2.0, 3.0]` com pesos iguais → pontuais 0,75; esparsos 0,5; generalizados 0,25.
  - Comparação estrita: subíndices `[1.0, 1.8, 2.6]` → pontuais 2/3, esparsos 1/3, generalizados 0 (valor igual ao limite não conta).
  - Lista vazia → erro.
- [ ] Implementar `subindice`, `indice_ponderado(subs, pesos)` e `probabilidades(subs, pesos)`.

## Tarefa 4 — Classificação

**Arquivos:** `backend/app/classificacao/classes.py`, `backend/tests/test_classes.py`

- [ ] Testes de fronteira (faixas `[a, b)`, sem arredondar):
  - 0,3999 → 1 · 0,40 → 2 · 0,70 → 3 · 0,9999 → 3 · 1,00 → 4 · 1,7999 → 4 · 1,80 → 5 · 2,60 → 6 · 3,40 → 7.
  - `em_alerta(0,9999)` é falso; `em_alerta(1,00)` é verdadeiro.
- [ ] Implementar `classe(indice) -> int` e `em_alerta(indice) -> bool`.

## Tarefa 5 — Coleta

**Arquivos:** `backend/app/coleta/open_meteo.py`, `backend/tests/test_open_meteo.py`, `backend/tests/fixtures/open_meteo_*.json`

- [ ] Gravar uma resposta real de cada endpoint escolhido na Tarefa 0 como fixture.
- [ ] Testes com a fixture (sem rede):
  - a função devolve a série horária em ordem, com a hora mais recente primeiro;
  - separa as horas passadas das horas previstas para cada dia-alvo UTC (D0–D3);
  - resposta com lacuna levanta erro identificando o município.
- [ ] Implementar `coletar(municipio, agora_utc) -> DadosMunicipio`, com timeout de 30 s e 2 novas tentativas.
- [ ] Teste de integração marcado `@pytest.mark.rede` (fora da suíte padrão) que chama a API real para 1 ponto.

## Tarefa 6 — Montagem por município e dia-alvo

**Arquivos:** `backend/app/pipeline.py`, `backend/tests/test_pipeline.py`

- [ ] Testes:
  - D0 = data UTC de `agora_utc`; D1–D3 são os dias seguintes.
  - O EfR de cada dia-alvo usa as 168 h anteriores à meia-noite UTC daquele dia.
  - Agregação (contrato): 2 pontos × 2 membros de peso igual. Membro A: pontos 1,2 e 0,8 → 1,2. Membro B: 0,6 e 0,9 → 0,9. Índice = 1,05.
  - `pesos(rodadas)`: com os valores definidos na Tarefa 0, rodada mais recente pesa mais que a anterior, e 00/12 UTC pesa mais que 06/18 UTC no mesmo atraso.
  - Membros abaixo de `n_min` → município em `sem_dados`.
- [ ] Implementar `pesos(rodadas)` e `calcular(municipios, dados, agora_utc) -> Resultado`.

## Tarefa 7 — Banco SQLite

**Arquivos:** `backend/app/modelos/banco.py`, `backend/app/modelos/schema.sql`, `backend/tests/test_banco.py`

- [ ] `schema.sql` com as tabelas `indices`, `inscritos` e `notificacoes` (campos do README).
- [ ] Testes com banco em memória:
  - gravar e ler índices;
  - `historico(ibge, dias=15)` devolve o último cálculo de cada dia-alvo, do mais antigo para o mais recente;
  - inscrever, listar e remover inscrito;
  - ler e atualizar a última classe notificada;
  - `indice_atual(ibge)` devolve o D0 do cálculo mais recente (usado pelo `/status`).
- [ ] Implementar com `sqlite3` e SQL puro. Ativar `PRAGMA journal_mode=WAL` (bot e agendador no mesmo processo).

## Tarefa 8 — Regra de aviso (RN08)

**Arquivos:** `backend/app/bot/regra_aviso.py`, `backend/tests/test_regra_aviso.py`

- [ ] Testes (entrada → avisa? / nova última classe):
  - sem anterior, D0 classe 4 → sim / 4;
  - última 4, atual 4 → não / 4;
  - última 4, atual 5 → sim / 5;
  - última 5, atual 4 → não / 5;
  - última 5, índice 0,9 → não / nenhuma (zera);
  - sem anterior (após zerar), classe 4 → sim / 4;
  - município sem dados → não / mantém a anterior;
  - classes de D1–D3 nunca geram aviso.
- [ ] Implementar `decidir(ultima_classe, indice_d0) -> (avisar: bool, nova_ultima: int | None)`; `indice_d0 = None` representa município sem dados.

## Tarefa 9 — Exportação e publicação

**Arquivos:** `backend/app/exportacao/exportar.py`, `backend/app/exportacao/publicar.py`, `backend/tests/test_exportar.py`

- [ ] Testes:
  - o JSON gerado segue o contrato (`schema_version = 1`, `gerado_em` com fuso, D0–D3, `historico`, `chuva_acum_mm`);
  - município sem dados aparece em `municipios_sem_dados` e não em `municipios`.
- [ ] Validar com um JSON Schema em `docs/indices.schema.json`, também usado pelo frontend nos testes.
- [ ] `publicar.py`: `PUT /repos/{dono}/{repo}/contents/frontend/public/data/indices.json` com o token lido de variável de ambiente (`GITHUB_TOKEN_DADOS`). Em caso de falha, registrar o erro e retornar sem exceção.
- [ ] Teste de `publicar` com o cliente HTTP simulado: envia o `sha` atual e trata a resposta 409 (conflito) tentando uma vez de novo.

## Tarefa 10 — Bot do Telegram

**Arquivos:** `backend/app/bot/bot.py`, `backend/app/bot/mensagens.py`, `backend/tests/test_mensagens.py`

- [ ] Testes de `mensagens.py` (texto puro, sem rede):
  - o aviso tem município, índice com vírgula e 2 casas, classe e link do site;
  - o texto é condicional ("poderá") e informa que não é alerta oficial (RN04).
- [ ] Comandos:
  - `/start [ibge]`: teclado com os municípios da configuração e "Todos"; o parâmetro sugere o município;
  - `/status`: índice e classe atuais dos municípios inscritos;
  - `/parar`: remove todos os registros do chat.
- [ ] Envio: `Forbidden` do Telegram → remover o inscrito (RNF05).
- [ ] Token do bot só por variável de ambiente (`TELEGRAM_TOKEN`).

## Tarefa 11 — Agendador e execução

**Arquivos:** `backend/app/main.py`, `backend/tests/test_execucao.py`

- [ ] `executar_pipeline(agora_utc)` encadeia: coleta → cálculo → gravação → exportação → publicação → avisos. Falha num município não interrompe os outros; falha geral mantém o último JSON (UC06).
- [ ] Teste ponta a ponta com fixtures e banco em memória: gera o JSON e decide os avisos esperados.
- [ ] `main.py`: um processo asyncio com o bot (long polling) e o `AsyncIOScheduler` (`cron` nos horários definidos na Tarefa 0, `misfire_grace_time=3600`, `max_instances=1`). O pipeline roda num executor, com conexão SQLite própria.
- [ ] Log em arquivo com o resultado de cada execução.

## Tarefa 12 — Estações e comparação com o INMET

**Arquivos:** `backend/scripts/gerar_estacoes.py`, `backend/app/coleta/inmet.py`, `backend/tests/test_inmet.py`

- [ ] Script que lista as estações automáticas do INMET nos municípios configurados e grava `frontend/public/data/estacoes.json` (contrato).
- [ ] Na execução, quando houver estação no município, registrar no log a diferença entre a chuva de 24 h medida e a modelada. Não altera o índice.
- [ ] Teste com fixture: a diferença é calculada e registrada; estação sem dado não interrompe o pipeline.

## Critério de pronto

- `pytest` passa sem rede.
- Uma execução manual gera um `indices.json` válido pelo schema e publica no repositório de teste.
- `/start`, `/status` e `/parar` funcionam num bot de teste.
