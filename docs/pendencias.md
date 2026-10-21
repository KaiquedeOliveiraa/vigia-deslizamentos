# Pendências de desenvolvimento

Levantamento de 10/10/2026. Marque como resolvido (ou apague o item) no PR que fechar cada um.

Legenda: 🔴 bloqueia o deploy · 🟡 bloqueia só uma funcionalidade · ⚪ não bloqueia

## Integrações e credenciais

- 🔴 **Bot do Telegram.** Bot criado no @BotFather como `@VigiaDeslizamentosBot`, o mesmo nome do padrão de `PUBLIC_TELEGRAM_BOT`, então o link do site já aponta para ele. Falta o operador conferir o `TELEGRAM_TOKEN` nos secrets do GitHub e do Worker (e o `TELEGRAM_WEBHOOK_SEGREDO` no Worker). Sem token o processo sai com código 2; com token inválido, código 3.
- ⚪ **Token do INMET + Tarefa 12.** Pedir o token por e-mail a `cadastro.act@inmet.gov.br` e preencher `INMET_TOKEN`. Com ele, confirmar com resposta real os campos `DT_MEDICAO`, `HR_MEDICAO`, `CHUVA` e o fuso UTC, que ainda são suposição ([ensemble.md §10](decisoes/ensemble.md)). Sem o token o sistema roda; só a conferência de chuva fica de fora.
- ⚪ **Secret `TOKEN_DADOS` (PAT `vigia_publicacao`): renovar antes de expirar** — conferir a data em github.com/settings/personal-access-tokens; sem ele a publicação do `indices.json` falha com 401/403; o run continua verde, mas o erro aparece como aviso no resumo. Renovar antes de 03/01/2027.

## Autorizações externas

- 🟡 **Defesa Civil de SC (RN10).** O mapa oficial em iframe já funciona (`PUBLIC_SC_IFRAME=true`), mas só pode ir para produção com autorização. Pedir junto o uso da API GraphQL de `monitoramento.defesacivil.sc.gov.br`, que tem estação dentro de cada município (o INMET só tem duas estações dentro dos 27) e pode substituir o INMET na conferência de chuva.

## Infraestrutura e deploy

- ~~🔴 **Hospedagem do backend**~~ **Resolvida:** pipeline no GitHub Actions e bot no Cloudflare Worker (`bot-worker/`). A unidade systemd em `backend/deploy/vigia.service` segue como alternativa.
- ⚪ **Commit do `indices.json` a cada execução.** São 4 commits e 4 deploys do Pages por dia na `main` (≈120 por mês). Decidir antes de ligar: aceitar, ou publicar numa branch `dados` com o site lendo dela via `PUBLIC_DADOS_URL`.
- ~~⚪ **Atualizar `actions/checkout` e `actions/setup-node` do `pages.yml`**~~ **Resolvida:** runner `ubuntu-24.04` e actions com Node.js 24 fixadas por SHA (inclusive `upload-pages-artifact` e `deploy-pages`).
- ~~⚪ **CI só cobre o frontend.**~~ **Resolvida em parte:** o `ci.yml` roda o `pytest -W error` do backend e os testes do Worker em todo PR. O axe-core continua pendente (ver "Qualidade e testes").

## Metodologia e calibração

- 🔴 **Validar o limiar provisório de 150 mm.** Foi reduzido de 250 mm para a simulação mostrar mudança de classe, mas ele muda o índice real (≈ +67%) e a frequência de avisos do bot. A equipe decidiu mantê-lo e confirmar o valor com o responsável técnico antes do deploy.
- 🔴 **Validar os pesos fixos do ensemble** ([ensemble.md §5](decisoes/ensemble.md)), que não são calibrados.
- ~~⚪ **Bancos já existentes**~~ **Resolvida:** `banco.historico()` converte cada cálculo para o limiar atual (`indice × limiar_gravado / limiar_mm`, classe recalculada), sem alterar o banco. Vale para qualquer troca futura de limiar; troca de `mv_h` não é coberta.
- ⚪ **Atraso de disponibilização dos modelos** foi medido uma vez só. Acompanhar por alguns dias e ajustar os horários do agendador se preciso.

## Dados e documentação

- ⚪ **Contatos:** o endereço de Ibirama foi corrigido (o antigo era de uma escola) e segue com `verificado: true` em `frontend/public/data/contatos.json`. Presidente Getúlio também passou a `verificado: true` com o telefone (47) 99754-0438, confirmado pelo time; faltam e-mail e endereço. Os outros quatro municípios têm dados preliminares, tirados de fontes oficiais, com `verificado: false`: falta confirmar por telefone com cada prefeitura (RN09), completar os campos `null` e trocar para `true`.
- ⚪ **README:** completar a citação da RADIAN ("autoria e ano a completar"); o repositório da UFSC exige VPN.
- ~~⚪ **Fixture de exemplo**~~ **Resolvida:** `indices.exemplo.json` usa o limiar de 150 mm e a fonte nova, com índice e classe recalculados.

## Frontend

- ~~⚪ **Conferência visual dos gráficos novos da tela Dados**~~ **Resolvida:** conferido com 15 dias em 1366 e 375 px, claro e escuro. Duas correções: no celular a Evolução abre rolada até o D0, e as camadas da Simulação foram para baixo, acima do zoom, porque os avisos as cobriam entre 920 e ~1600 px (até 1040 px viram o select, para a legenda aberta não cobri-las).
- ~~⚪ **Período maior que o histórico**~~ **Resolvida:** a tela Dados avisa "Por enquanto há histórico de N dias" quando o período escolhido é maior (`diasComDados` em `graficos.ts`).
- ~~⚪ **Contorno do município sem classe nos fundos detalhados**~~ **Resolvida:** sem classe, o contorno usa `--muted`, que contrasta nos dois temas; o preenchimento segue `--surface-000`.
- ~~⚪ **Seletor de camadas some abaixo de 900 px**~~ **Resolvida:** no Monitoramento e na Simulação os botões viram um `<select>` nativo abaixo de 900 px.
- ~~⚪ **Altura fixa do iframe da Defesa Civil**~~ **Resolvida:** `height: min(80vh, 760px)` em `sc.css`.
- ~~⚪ **Rótulo "hoje" das previsões pela posição**~~ **Resolvida:** o rótulo (e o anúncio para leitor de tela) agora compara o `dia_alvo` com a data de Brasília; com o `indices.json` atrasado, o dia passado aparece como "ontem" ou "-Nd", e não como "hoje".

## Backend

- 🔴 **Remover o comando `/simular` do bot antes do deploy.** Existe só para demonstração (liga com `VIGIA_SIMULACAO=1`). Apagar `app/bot/simulacao.py`, `tests/test_simulacao.py`, o `comando_simular` e o registro dele em `app/bot/bot.py`, a variável `VIGIA_SIMULACAO` (`app/config.py`, `.env.exemplo`, `backend/README.md`, a variável do workflow `pipeline.yml`), o campo `simulacao` do `bot.json` (`app/exportacao/bot_json.py`, o contrato em `docs/contratos-de-dados.md` e o `simulacao=True` de `test_fixture_do_worker_igual_ao_montar_bot_json`, regenerando `bot-worker/test/fixtures/bot.exemplo.json` com `VIGIA_REGERAR_FIXTURES=1`) e a parte do `/simular` no Worker (`bot-worker/`). Opcional: os campos de chuva e horário do `Aviso` (`app/bot/regra_aviso.py`) aceitam `None` só por causa dela. `faixas_das_classes` fica: a barra de cores das mensagens reais também a usa.

- ⚪ **`rodar_local.py` grava em `frontend/public/data/indices.json`**, o mesmo caminho que o bot publica na `main`. O arquivo não pode ir para o `.gitignore`; cuidado para não commitá-lo, e apagar a cópia local antes de um `git pull` depois da primeira publicação.
- ~~⚪ **Recálculo do histórico quando o `limiar_mm` muda**~~ **Resolvida:** a conversão é automática na leitura (ver "Bancos já existentes").
- ⚪ **Conferência de chuva com as estações da Defesa Civil**, no lugar ou ao lado do INMET (depende da autorização RN10).
- ~~🔴 **Worker aceitava cabeçalho vazio quando o segredo não estava configurado**~~ **Resolvida:** sem `TELEGRAM_WEBHOOK_SEGREDO` (ou com ele vazio), `segredoConfere` recusa toda requisição, em vez de aceitar `X-Telegram-Bot-Api-Secret-Token` vazio.
- ~~⚪ **Execução com o Worker indisponível termina verde**~~ **Resolvida:** a etapa "Avisar erros registrados no log" do `pipeline.yml` transforma as linhas ERROR do log em avisos no resumo do run. O job continua verde de propósito, para o estado ser gravado.
- ~~⚪ **Fixture de contrato do `bot.json`**~~ **Resolvida:** `bot-worker/test/fixtures/bot.exemplo.json` sai de `montar_bot_json` (teste `test_fixture_do_worker_igual_ao_montar_bot_json`); o Worker confere o formato no `tsc` e nos testes. Para regenerar: `VIGIA_REGERAR_FIXTURES=1 pytest tests/test_bot_json.py`.

## Ampliação para os 27 municípios

- ⚪ **Limiar dos 27 municípios:** todos com 150 mm provisório; validar com o time, por município ou por região.
- ⚪ **Contatos dos 21 municípios novos:** levantar e confirmar com cada prefeitura (RN09).
- ⚪ **Prazo total de coleta:** com o Open-Meteo degradado, 111 chamadas × até 92 s podem passar do `timeout-minutes: 60`; limitar o tempo total da coleta e marcar os restantes como sem dados.
- ⚪ **Avisos agrupados por chat:** se quem segue os 27 receber mensagens demais num evento regional, juntar os avisos de uma execução numa só mensagem.

## Qualidade e testes

- ~~⚪ **Workflow `backend.yml`**~~ **Resolvida:** o job `backend` do `ci.yml` roda o `pytest -W error`.
- ⚪ **axe-core no `pages.yml`** sobre o `dist/`, como o README exige antes de cada publicação.
- ~~⚪ **Teste de componente da Evolução**~~ **Resolvida:** ponteiro e setas viraram funções puras em `lib/graficos.ts` (`indiceMaisProximo`, `focoAposSeta`, `vizinhoCiclico`, `passoDaSeta`), com teste.
- ~~⚪ **O PR não roda CI**~~ **Resolvida:** o `ci.yml` roda frontend, backend e Worker em todo PR para a `main`.

## Documentação

- ~~⚪ Documentar o `scripts.rodar_local`~~ **Resolvida:** seção "Execução local, sem bot e sem publicar" no `backend/README.md`, com o `frontend/.env.development.local`.
