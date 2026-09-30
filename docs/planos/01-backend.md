# Plano 01 — Backend (pipeline, banco, exportação e bot)

**Objetivo:** implementar o pipeline que calcula o índice GeoRisk a cada 6 horas, grava no SQLite, publica o `indices.json` e avisa os inscritos pelo Telegram.

**Base:** README (Metodologia, Funcionamento, Banco de dados, RN07, RN08, RN12) e [Contratos de dados](../contratos-de-dados.md).

**Stack:** Python 3.12, `requests`, `python-telegram-bot` (v21+), `APScheduler` 3.x (`>=3.10,<4`; a API do `AsyncIOScheduler` mudou na 4.x), `tzdata` (fuso de Brasília também no Windows), `sqlite3` (biblioteca padrão), `pytest` e `jsonschema` (testes). pandas/NumPy só se o cálculo pedir; as funções abaixo funcionam com listas.

**Regra de trabalho:** em cada tarefa, escrever o teste primeiro, ver falhar, implementar o mínimo e ver passar. Commit ao fim de cada tarefa.

**Convenções (valem para todas as tarefas):**
- Cálculo (`calculo/`, `classificacao/`, `bot/regra_aviso.py`, `bot/mensagens.py`, `exportacao/exportar.py`) é puro: sem rede, banco, relógio ou `os.environ`.
- I/O recebe as dependências por parâmetro: cliente HTTP (`requests.Session` ou dublê), conexão SQLite, `agora_utc`. Nada de estado global; só `main.py` monta as dependências.
- Todo `datetime` é *aware* em UTC; `datetime` sem fuso levanta erro. No banco, data-hora é texto ISO `YYYY-MM-DDTHH:MM:SSZ` (ordena como texto) e data é `YYYY-MM-DD`.
- Comparações de `float` nos testes com `pytest.approx`, exceto as fronteiras de classe (literais exatos).
- Nomes seguem o contrato: `ibge`, `dia_alvo`, `indice`, `classe`, `efr_mm`, `rtotal_mm`, `limiar_mm`, `n_membros`, `prob`, `municipios_sem_dados`, `chuva_acum_mm`.

---

## Tarefa 0 — Spike: fonte das rodadas do ensemble

Antes de codificar a coleta, confirmar na documentação do Open-Meteo:

- [ ] Qual endpoint devolve a chuva horária das 168 h anteriores (parâmetro `past_days`) e em qual fuso (`timezone=UTC`).
- [ ] Convenção do rótulo horário da precipitação (soma da hora anterior ou da seguinte ao rótulo). Ela fixa quais 169 rótulos formam a janela do EfR (Tarefa 6).
- [ ] Qual endpoint devolve rodadas anteriores de um mesmo modelo (necessário para o *time-lagged ensemble* de até 36 h). Candidato: API de rodadas anteriores (*Previous Runs*). Confirmar a granularidade do atraso (6 h ou 24 h) e ajustar a tabela de pesos ao que existir.
- [ ] Quais modelos cobrem SC com precipitação horária (ex.: GFS, ECMWF IFS, ICON) e se o horizonte de cada rodada, com o atraso máximo, alcança o fim do D3.
- [ ] Limite de chamadas do plano gratuito × volume previsto (municípios × pontos × modelos × 4 execuções/dia).
- [ ] INMET: endpoint da lista de estações automáticas e da chuva horária, fuso dos horários, se exige token e qual campo permite associar a estação ao `ibge`.

**Saída:** uma tabela em `docs/decisoes/ensemble.md` com modelos escolhidos, pesos fixos por atraso da rodada (0, 6, 12… 36 h) e por rodada 00/12 × 06/18, e o `n_min` de membros. Abaixo de `n_min`, o município vai para `municipios_sem_dados`.

> Esta tarefa fecha a lacuna "modelos e pesos a definir" e deve ser validada pela equipe antes das Tarefas 5 e 6. Registrar também o horário (UTC) em que cada rodada fica disponível, para fixar os horários do agendador.

## Tarefa 1 — Estrutura e configuração

**Arquivos:** `backend/pyproject.toml`, `backend/app/config.py`, `backend/config/municipios.json`, `backend/.env.exemplo`, `.gitignore`, `docs/indices.schema.json`, `backend/tests/test_config.py`

- [ ] Teste: carregar `municipios.json` retorna todos os municípios configurados, cada um com `ibge` de 7 dígitos, `limiar_mm > 0`, `mv_h > 0` e ao menos um ponto.
- [ ] Teste: arquivo com campo faltando levanta erro com o nome do campo; `ibge` repetido levanta erro.
- [ ] Implementar `carregar_municipios(caminho) -> list[Municipio]` (dataclass imutável, campos do contrato).
- [ ] Preencher `municipios.json` com os códigos IBGE (API de Localidades), `limiar_mm: 250`, `fonte_limiar: "GeoRisk, limiar hipotético padrão"`, `mv_h: 24` e o centroide de cada município.
- [ ] `.env.exemplo` com `TELEGRAM_TOKEN`, `GITHUB_TOKEN_DADOS`, `GITHUB_REPO` (`dono/repo`), `SITE_URL`, `DB_PATH` e `LOG_PATH`; o `.env` real fica no `.gitignore`.
- [ ] Teste: `carregar_env(ambiente: Mapping[str, str]) -> Config` sem uma variável obrigatória levanta erro com o nome dela (e nunca com o valor de outra). Nenhum outro módulo lê `os.environ`.
- [ ] Criar `docs/indices.schema.json` (JSON Schema do contrato, com todos os campos obrigatórios e `schema_version: const 1`). O frontend depende dele desde a sua Tarefa 2. Teste: o schema aceita um exemplo mínimo válido e rejeita um sem `dia_alvo_d0`.

## Tarefa 2 — Chuva efetiva antecedente (EfR)

**Arquivos:** `backend/app/calculo/chuva_efetiva.py`, `backend/tests/test_chuva_efetiva.py`

- [ ] Testes:
  - 10 mm só na hora t=0 → EfR = 10.
  - 10 mm só em t=24 com MV=24 → EfR = 5.
  - 10 mm só em t=48 com MV=24 → EfR = 2,5.
  - série vazia → 0.
  - valores faltantes (`None`) ou mais de 169 valores → erro, não resultado silencioso.
- [ ] Implementar `efr(chuva_horaria: list[float], mv_h: float) -> float`, com `chuva_horaria[0]` = hora mais recente, até 169 valores (t = 0…168).

## Tarefa 3 — Subíndice e índice ponderado

**Arquivos:** `backend/app/calculo/indice.py`, `backend/tests/test_indice.py`

- [ ] Testes:
  - `subindice(efr=100, rtotal=20, limiar=120) == 1.0`.
  - Índice com pesos iguais = média simples.
  - Pesos `[3, 1]` e subíndices `[1.0, 2.0]` → 1,25.
  - Lista vazia, tamanhos diferentes entre `subs` e `pesos` ou soma dos pesos 0 → erro.
- [ ] Implementar `subindice(efr, rtotal, limiar) -> float` e `indice_ponderado(subs: list[float], pesos: list[float]) -> float`.

## Tarefa 4 — Classificação e probabilidades

**Arquivos:** `backend/app/classificacao/classes.py`, `backend/app/classificacao/probabilidades.py`, `backend/tests/test_classes.py`, `backend/tests/test_probabilidades.py`

> Probabilidades ficam no Classificador, como no README (Componentes principais).

- [ ] Testes de fronteira (faixas `[a, b)`, sem arredondar):
  - 0,3999 → 1 · 0,40 → 2 · 0,70 → 3 · 0,9999 → 3 · 1,00 → 4 · 1,7999 → 4 · 1,80 → 5 · 2,60 → 6 · 3,3999 → 6 · 3,40 → 7.
  - `em_alerta(0,9999)` é falso; `em_alerta(1,00)` é verdadeiro.
- [ ] Testes de probabilidades:
  - subíndices `[0.5, 1.2, 2.0, 3.0]` com pesos iguais → pontuais 0,75; esparsos 0,5; generalizados 0,25.
  - Comparação estrita: `[1.0, 1.8, 2.6]` → pontuais 2/3, esparsos 1/3, generalizados 0 (valor igual ao limite não conta).
  - Ponderação: `[0.5, 2.0]` com pesos `[3, 1]` → pontuais 0,25.
- [ ] Implementar `classe(indice) -> int`, `em_alerta(indice) -> bool` e `probabilidades(subs, pesos) -> Probabilidades` (`pontuais`, `esparsos`, `generalizados`).

## Tarefa 5 — Coleta

**Arquivos:** `backend/app/modelos/tipos.py`, `backend/app/coleta/open_meteo.py`, `backend/tests/test_open_meteo.py`, `backend/tests/fixtures/open_meteo_*.json`

- [ ] Em `modelos/tipos.py`, os tipos que ligam coleta e cálculo (dataclasses imutáveis):
  - `Membro(modelo: str, rodada: datetime, chuva: list[dict[datetime, float]])`: uma série por ponto, chave = hora UTC;
  - `DadosMunicipio(ibge: str, antecedente: list[dict[datetime, float]], membros: list[Membro])`: `antecedente` é a chuva das horas até `agora_utc`, uma série por ponto.
- [ ] Gravar uma resposta real de cada endpoint escolhido na Tarefa 0 como fixture.
- [ ] Testes com a fixture e um cliente HTTP falso (sem rede):
  - as horas viram `datetime` UTC com fuso e os valores ficam associados à hora certa;
  - lacuna (`null`) na série antecedente levanta erro identificando o município;
  - lacuna ou rodada ausente num membro descarta só esse membro (quem decide se ainda há membros suficientes é a Tarefa 6);
  - erro transitório na 1ª tentativa e sucesso na 2ª → devolve os dados; 3 falhas → erro identificando o município.
- [ ] Implementar `coletar(municipio: Municipio, agora_utc: datetime, http: requests.Session) -> DadosMunicipio`, com timeout de 30 s e 2 novas tentativas (espera injetável, zero nos testes).
- [ ] Teste de integração marcado `@pytest.mark.rede` (fora da suíte padrão) que chama a API real para 1 ponto.

## Tarefa 6 — Cálculo por município e dia-alvo

**Arquivos:** `backend/app/calculo/agregacao.py`, `backend/tests/test_agregacao.py`

- [ ] Testes:
  - D0 = data UTC de `agora_utc`; D1–D3 são os dias seguintes. Virada do dia: `2026-09-30T01:00Z` (22h de 29/09 em Brasília) → D0 = `2026-09-30`.
  - Janela do EfR do dia-alvo D: as 169 horas de t=0 (hora que termina na meia-noite UTC de D) a t=168, pela convenção da Tarefa 0. Horas até `agora_utc` vêm de `antecedente`; horas depois vêm do próprio membro.
  - `rtotal` do dia-alvo = soma das 24 horas daquele dia UTC na série do membro.
  - Agregação (contrato): 2 pontos × 2 membros de peso igual. Membro A: pontos 1,2 e 0,8 → 1,2. Membro B: 0,6 e 0,9 → 0,9. Índice = 1,05 (`approx`).
  - `efr_mm` e `rtotal_mm` exportados: valor do ponto de maior subíndice em cada membro (empate: primeiro ponto da configuração), média ponderada entre os membros.
  - `peso(rodada, agora_utc)`: com os valores da Tarefa 0, rodada mais recente pesa mais que a anterior; 00/12 UTC pesa mais que 06/18 UTC no mesmo atraso; atraso > 36 h → peso 0 (membro descartado).
  - Membro sem as 24 h de um dia-alvo fica fora só daquele dia (`n_membros` é por dia).
  - Algum dia-alvo com menos de `n_min` membros → município em `municipios_sem_dados` (o contrato exige D0–D3).
  - `chuva_acum_mm`: somas das últimas 24, 48, 72 e 96 horas de `antecedente` até a última hora cheia ≤ `agora_utc`, no ponto de maior valor (ex.: 1 mm/h constante → 24, 48, 72, 96).
- [ ] Implementar `peso(rodada, agora_utc) -> float` e `calcular(municipios, dados: dict[str, DadosMunicipio], agora_utc) -> Resultado`, com `Resultado(dia_alvo_d0, municipios: list[ResultadoMunicipio], municipios_sem_dados: list[str])`; cada `ResultadoMunicipio` traz os 4 `ResultadoDia` (campos do item de `dias` do contrato) e `chuva_acum_mm`.

## Tarefa 7 — Banco SQLite

**Arquivos:** `backend/app/modelos/banco.py`, `backend/app/modelos/schema.sql`, `backend/tests/test_banco.py`

- [ ] `schema.sql` (`CREATE TABLE IF NOT EXISTS`):
  - `indices(ibge, dia_alvo, calculado_em, indice, classe, efr_mm, rtotal_mm, limiar_mm, n_membros, prob_pontuais, prob_esparsos, prob_generalizados)`, `PRIMARY KEY (ibge, dia_alvo, calculado_em)`;
  - `inscritos(chat_id, ibge, inscrito_em)`, `PRIMARY KEY (chat_id, ibge)`;
  - `notificacoes(ibge PRIMARY KEY, ultima_classe NULL, notificado_em)`.
- [ ] `abrir(caminho) -> sqlite3.Connection`: cria o schema, `PRAGMA journal_mode=WAL` e `timeout=30`. Uma conexão por thread (bot e pipeline), nunca compartilhada.
- [ ] Testes com banco em memória:
  - `gravar_resultado(conexao, resultado, calculado_em)` grava tudo numa única transação; repetir com o mesmo `calculado_em` não duplica linhas (`INSERT OR REPLACE`);
  - `historico(conexao, ibge, dia_alvo_d0, dias=15)`: para cada dia-alvo em [D0−15, D0−1], o cálculo de maior `calculado_em`, do mais antigo para o mais recente; não inclui D0 nem dias futuros; dia sem cálculo não aparece;
  - inscrever (repetir a inscrição não duplica), listar os inscritos de um município e remover todas as inscrições de um chat;
  - ler e atualizar a última classe notificada (inclusive para `NULL`);
  - `indice_atual(conexao, ibge)` devolve índice, classe e `calculado_em` do D0 do cálculo mais recente, ou `None` (usado pelo `/status`).
- [ ] Teste com arquivo temporário: uma conexão grava enquanto outra lê, sem `database is locked`.
- [ ] Implementar com `sqlite3` e SQL puro.

## Tarefa 8 — Regra de aviso (RN08)

**Arquivos:** `backend/app/bot/regra_aviso.py`, `backend/tests/test_regra_aviso.py`

- [ ] Testes (última classe, índice do D0 → avisa? / nova última classe):
  - nenhuma, 1,20 (classe 4) → sim / 4;
  - 4, 1,50 (classe 4) → não / 4;
  - 4, 2,00 (classe 5) → sim / 5;
  - 5, 1,50 (classe 4) → não / 5;
  - 5, 0,90 → não / nenhuma (zera);
  - nenhuma (após zerar), 1,20 → sim / 4;
  - 4, sem dados (`None`) → não / 4 (mantém).
- [ ] Implementar `decidir(ultima_classe: int | None, indice_d0: float | None) -> tuple[bool, int | None]`. Recebe só o D0, por isso D1–D3 não geram aviso (testado na Tarefa 11).

## Tarefa 9 — Exportação e publicação

**Arquivos:** `backend/app/exportacao/exportar.py`, `backend/app/exportacao/publicar.py`, `backend/tests/test_exportar.py`, `backend/tests/test_publicar.py`

- [ ] Implementar `montar_indices(resultado, municipios, historicos: dict[str, list], gerado_em) -> dict` (puro) e `serializar(dados) -> bytes` (UTF-8).
- [ ] Testes:
  - o JSON é válido por `docs/indices.schema.json` (Tarefa 1);
  - raiz: `schema_version = 1`, `gerado_em` com fuso, `dia_alvo_d0`, `municipios_sem_dados`, `municipios`;
  - item: `ibge`, `nome`, `limiar_mm`, `fonte_limiar`, `mv_h`, `historico`, `chuva_acum_mm` com as chaves `"24h"…"96h"`;
  - `dias`: 4 itens com `d` 0–3 e `dia_alvo` consecutivos, cada um com `indice`, `classe`, `efr_mm`, `rtotal_mm`, `n_membros` e `prob`;
  - município sem dados aparece em `municipios_sem_dados` e não em `municipios`.
- [ ] `publicar(conteudo: bytes, config, http) -> bool`: `PUT /repos/{GITHUB_REPO}/contents/frontend/public/data/indices.json` no branch `main`, com `GITHUB_TOKEN_DADOS`. Em caso de falha, registra o erro e retorna `False`, sem exceção.
- [ ] Testes de `publicar` com o cliente HTTP simulado:
  - arquivo existente: lê o `sha` e envia junto;
  - arquivo inexistente (404 na leitura): cria sem `sha`;
  - resposta 409 (conflito): lê o `sha` de novo e tenta uma vez;
  - erro de rede ou 401: registra e retorna `False`, sem exceção; o texto registrado não contém o token.

## Tarefa 10 — Bot do Telegram

**Arquivos:** `backend/app/bot/bot.py`, `backend/app/bot/mensagens.py`, `backend/app/bot/inscricao.py`, `backend/app/bot/avisos.py`, `backend/tests/test_mensagens.py`, `backend/tests/test_inscricao.py`, `backend/tests/test_avisos.py`

- [ ] Testes de `mensagens.py` (texto puro, sem rede, em português):
  - o aviso tem município, índice com vírgula e 2 casas, classe e link do site (`SITE_URL`);
  - o texto é condicional ("poderá") e informa que não é alerta oficial (RN04);
  - `/status` lista cada município inscrito com índice e classe do D0 e a hora do cálculo no horário de Brasília (`America/Sao_Paulo`); município sem cálculo aparece como "sem dados";
  - `/status` sem inscrições orienta a usar `/start`.
- [ ] Testes de `inscricao.py` (sem rede, banco em memória):
  - escolher um município inscreve só ele; "Todos" inscreve todos os configurados;
  - `/start` com código IBGE fora da configuração é ignorado e mostra o teclado normal.
- [ ] Testes de `avisos.py` com bot falso: `enviar_avisos(bot, conexao, avisos) -> None` (assíncrona):
  - envia a todos os inscritos de cada município com `avisar = True` e depois grava a nova última classe, uma vez por município;
  - `Forbidden` → remove as inscrições daquele chat (RNF05) e segue; outros erros → registra e segue para o próximo chat;
  - todos os envios de um município falham por erro de rede → não grava a nova classe (reenvia na próxima execução). Queda do processo no meio do laço pode repetir o aviso na execução seguinte; aceito, pois é preferível a perder um aviso.
- [ ] Comandos em `bot.py` (só ligam o Telegram às funções acima):
  - `/start [ibge]`: teclado com os municípios da configuração e "Todos"; o parâmetro sugere o município;
  - `/status`: índice e classe atuais dos municípios inscritos;
  - `/parar`: remove todos os registros do chat.
- [ ] Token do bot só pela `Config` (`TELEGRAM_TOKEN`). Logger `httpx` em `WARNING`, porque a URL das requisições do bot contém o token.

## Tarefa 11 — Pipeline, agendador e execução

**Arquivos:** `backend/app/pipeline.py`, `backend/app/main.py`, `backend/tests/test_pipeline.py`

- [ ] `executar_pipeline(agora_utc, municipios, conexao, http, config) -> Execucao` (síncrona) encadeia: coleta → cálculo → gravação → exportação → publicação → decisão dos avisos. Devolve `Execucao(resultado, publicado: bool, avisos: list[Aviso])`; o envio fica fora (Tarefa 10), no loop do bot. Testes com dublês:
  - falha num município (coleta ou cálculo): ele vai para `municipios_sem_dados` e os outros seguem;
  - falha geral (nenhum município calculado): não grava, não publica, não avisa; o último JSON continua no ar (UC06);
  - falha na publicação não impede os avisos;
  - `gerado_em` = horário do fim da execução (relógio injetado);
  - D0 classe 2 e D1 classe 6 → nenhum aviso;
  - execução repetida com a mesma `agora_utc` e a mesma classe → nenhum aviso novo.
- [ ] Teste ponta a ponta com fixtures e banco em memória: gera o JSON válido pelo schema, com `historico` lido do banco, e decide os avisos esperados.
- [ ] `main.py`: um processo asyncio com o bot (long polling) e o `AsyncIOScheduler(timezone=UTC)` (`cron` nos horários UTC da Tarefa 0, `misfire_grace_time=3600`, `coalesce=True`, `max_instances=1`). O job roda `executar_pipeline` com `asyncio.to_thread` e conexão SQLite própria, e depois `await enviar_avisos(...)` no loop.
- [ ] Log em arquivo (`LOG_PATH`) com o resultado de cada execução.

## Tarefa 12 — Estações e comparação com o INMET

**Arquivos:** `backend/scripts/gerar_estacoes.py`, `backend/app/coleta/inmet.py`, `backend/tests/test_inmet.py`

- [ ] Script que lista as estações automáticas do INMET nos municípios configurados e grava `frontend/public/data/estacoes.json` (contrato). Teste com fixture: converte para `{codigo, nome, ibge, lat, lon}`, associa o `ibge` pelo campo definido na Tarefa 0 e descarta estações fora da configuração.
- [ ] Na execução, quando houver estação no município, registrar no log a diferença entre a chuva de 24 h medida e `chuva_acum_mm["24h"]`. Não altera o índice.
- [ ] Teste com fixture: a diferença é calculada e registrada; estação sem dado ou erro do INMET não interrompe o pipeline.

## Tarefa 13 — Implantação

**Arquivos:** `backend/deploy/vigia.service`, `backend/README.md`

- [ ] Unidade systemd com `Restart=always`, `EnvironmentFile` apontando para o `.env` (permissão 600) e `DB_PATH` num disco persistente.
- [ ] Instruções de instalação, variáveis e como rodar uma execução manual (`python -m app.main --uma-vez`), com o serviço parado (dois processos gravando geram avisos duplicados).
- [ ] Teste do argumento `--uma-vez`: executa o pipeline e envia os avisos uma vez e sai com código 0 em sucesso e 1 em falha geral.

## Critério de pronto

- `pytest` passa sem rede.
- Uma execução manual gera um `indices.json` válido pelo schema e publica no repositório de teste.
- `/start`, `/status` e `/parar` funcionam num bot de teste.
