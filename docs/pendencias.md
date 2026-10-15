# Pendências de desenvolvimento

Levantamento de 10/10/2026. Marque como resolvido (ou apague o item) no PR que fechar cada um.

Legenda: 🔴 bloqueia o deploy · 🟡 bloqueia só uma funcionalidade · ⚪ não bloqueia

## Integrações e credenciais

- 🔴 **Bot do Telegram.** Criar o bot no @BotFather e pôr o `TELEGRAM_TOKEN` nos secrets do GitHub e do Worker. Sem token o processo sai com código 2; com token inválido, código 3. Se o nome não for `VigiaDeslizamentosBot`, definir `PUBLIC_TELEGRAM_BOT` no build do site (hoje o link aponta para um bot que não existe).
- ⚪ **Token do INMET + Tarefa 12.** Pedir o token por e-mail a `cadastro.act@inmet.gov.br` e preencher `INMET_TOKEN`. Com ele, confirmar com resposta real os campos `DT_MEDICAO`, `HR_MEDICAO`, `CHUVA` e o fuso UTC, que ainda são suposição ([ensemble.md §10](decisoes/ensemble.md)). Sem o token o sistema roda; só a conferência de chuva fica de fora.
- ⚪ **Secret `TOKEN_DADOS` (PAT `vigia_publicacao`): renovar antes de expirar** — conferir a data em github.com/settings/personal-access-tokens; sem ele a publicação do `indices.json` falha com 401/403 e o run continua verde. Renovar antes de 03/01/2027.

## Autorizações externas

- 🟡 **Defesa Civil de SC (RN10).** O mapa oficial em iframe já funciona (`PUBLIC_SC_IFRAME=true`), mas só pode ir para produção com autorização. Pedir junto o uso da API GraphQL de `monitoramento.defesacivil.sc.gov.br`, que tem estação dentro de cada um dos 6 municípios (o INMET mais próximo fica a ~30 km) e pode substituir o INMET na conferência de chuva.

## Infraestrutura e deploy

- ~~🔴 **Hospedagem do backend**~~ **Resolvida:** pipeline no GitHub Actions e bot no Cloudflare Worker (`bot-worker/`). A unidade systemd em `backend/deploy/vigia.service` segue como alternativa.
- ⚪ **Commit do `indices.json` a cada execução.** São 4 commits e 4 deploys do Pages por dia na `main` (≈120 por mês). Decidir antes de ligar: aceitar, ou publicar numa branch `dados` com o site lendo dela via `PUBLIC_DADOS_URL`.
- ⚪ **Atualizar `actions/checkout` e `actions/setup-node` do `pages.yml`** para versões com Node.js 24 e fixar o runner (`ubuntu-24.04`), como já foi feito no `pipeline.yml`.
- ⚪ **CI só cobre o frontend.** `pages.yml` não roda o `pytest` do backend nem o axe-core, que o README exige antes de cada publicação.

## Metodologia e calibração

- 🔴 **Validar o limiar provisório de 150 mm.** Foi reduzido de 250 mm para a simulação mostrar mudança de classe, mas ele muda o índice real (≈ +67%) e a frequência de avisos do bot. A equipe decidiu mantê-lo e confirmar o valor com o responsável técnico antes do deploy.
- 🔴 **Validar os pesos fixos do ensemble** ([ensemble.md §5](decisoes/ensemble.md)), que não são calibrados.
- ⚪ **Bancos já existentes:** o histórico gravado com o limiar de 250 mm se mistura com o novo e cria saltos falsos no gráfico de evolução. Limpar ou recalcular a tabela `indices` ao trocar o limiar.
- ⚪ **Atraso de disponibilização dos modelos** foi medido uma vez só. Acompanhar por alguns dias e ajustar os horários do agendador se preciso.

## Dados e documentação

- ⚪ **Contatos:** só Ibirama está com `verificado: true` em `frontend/public/data/contatos.json`; os coordenadores dos demais municípios estão "a confirmar".
- ⚪ **README:** tabela de códigos IBGE ainda "a preencher" (os códigos já estão em `backend/config/municipios.json`); grafia "Vitor Meirelles" × "Vitor Meireles"; a lista de tecnologias cita FastAPI e pandas/NumPy, que o código não usa.
- ⚪ **Fixture de exemplo** `frontend/src/fixtures/indices.exemplo.json` ainda usa limiar 250 mm e a fonte antiga.

## Frontend

- ⚪ **Conferência visual dos gráficos novos da tela Dados** (linha-guia, dica, mini-gráficos, pluviômetro) com histórico de vários dias. Também: rótulo do último ponto perto da linha de ALERTA e seletor de camadas da Simulação com avisos abertos em telas largas.
- ⚪ **Período maior que o histórico:** com menos dias de histórico que o período escolhido (5/7/15), o eixo mostra dias vazios. Avisar "histórico de N dias" ou desabilitar o período.
- ⚪ **Contorno do município sem classe nos fundos detalhados:** `--cor-mun` vira `var(--surface-000)` (`MapaLeaflet.tsx`), e no tema escuro sobre o Satélite o contorno fica quase invisível.
- ⚪ **Seletor de camadas da Simulação some abaixo de 900 px** (regra geral de `.layers` em `mapa.css`), como já acontecia no Monitoramento. Avaliar uma versão para celular.
- ⚪ **Altura fixa do iframe da Defesa Civil** (760 px em `sc.css`): trocar por `min(80vh, 760px)` para não cortar em notebooks pequenos.

## Backend

- 🔴 **Remover o comando `/simular` do bot antes do deploy.** Existe só para demonstração (liga com `VIGIA_SIMULACAO=1`). Apagar `app/bot/simulacao.py`, `tests/test_simulacao.py`, o `comando_simular` e o registro dele em `app/bot/bot.py`, a variável `VIGIA_SIMULACAO` (`app/config.py`, `.env.exemplo`, `backend/README.md`, a variável do workflow `pipeline.yml`), o campo `simulacao` do `bot.json` (`app/exportacao/bot_json.py` e o contrato em `docs/contratos-de-dados.md`) e a parte do `/simular` no Worker (`bot-worker/`). Opcional: os campos de chuva e horário do `Aviso` (`app/bot/regra_aviso.py`) aceitam `None` só por causa dela. `faixas_das_classes` fica: a barra de cores das mensagens reais também a usa.

- ⚪ **`rodar_local.py` grava em `frontend/public/data/indices.json`**, o mesmo caminho que o bot publica na `main`. O arquivo não pode ir para o `.gitignore`; cuidado para não commitá-lo, e apagar a cópia local antes de um `git pull` depois da primeira publicação.
- ⚪ **Recálculo do histórico quando o `limiar_mm` muda:** criar um comando ou aviso para não misturar limiares no gráfico de evolução.
- ⚪ **Conferência de chuva com as estações da Defesa Civil**, no lugar ou ao lado do INMET (depende da autorização RN10).
- ⚪ **Execução com o Worker indisponível termina verde:** o erro fica só no log. Avaliar um código de saída próprio ou um `::warning::` no workflow para avisar o operador.
- ⚪ **Fixture de contrato do `bot.json`:** gerar o exemplo dos testes do Worker a partir de `montar_bot_json`, para um campo renomeado falhar nos dois lados.

## Qualidade e testes

- ⚪ **Workflow `backend.yml`** com `pytest -W error` (a suíte é offline e leva ~3 s).
- ⚪ **axe-core no `pages.yml`** sobre o `dist/`, como o README exige antes de cada publicação.
- ⚪ **Teste de componente da Evolução:** dia mais próximo do ponteiro e navegação por ←/→ não têm teste.
- ⚪ **O PR não roda CI:** `pages.yml` só dispara em push na `main`. Adicionar `pull_request` para os testes rodarem antes do merge.

## Documentação

- ⚪ Documentar no `backend/README.md` o `scripts.rodar_local` e o `frontend/.env.development.local` com `PUBLIC_DADOS_URL=data/`, para ver dados reais no `npm run dev` (por padrão o dev mostra os dados de exemplo).
