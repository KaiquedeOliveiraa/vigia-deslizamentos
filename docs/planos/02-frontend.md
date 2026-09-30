# Plano 02 — Frontend (site no GitHub Pages)

**Objetivo:** implementar as 7 telas do README lendo `data/indices.json`, com PT/ES e acessibilidade, publicadas no GitHub Pages.

**Base:** README (Telas, RF01–RF13, RNF01–RNF04, RN01–RN07, RN11, RN12), [Contratos de dados](../contratos-de-dados.md) e o protótipo navegável (referência visual e de comportamento).

**Stack:** Astro + React (ilhas), TypeScript, react-leaflet + OpenStreetMap, Vitest para a lógica, axe-core e Lighthouse para verificação.

**Regra de trabalho:** a lógica (formatação, classes, leitura do JSON, simulação) fica em `src/lib/` com teste antes do código. Os componentes visuais seguem o protótipo.

---

## Tarefa 1 — Projeto e deploy

**Arquivos:** `frontend/` (Astro), `.github/workflows/pages.yml`

- [ ] Criar o projeto Astro com a integração React e o `base` do GitHub Pages.
- [ ] Workflow: build e deploy a cada push em `main` que altere `frontend/**`, inclusive `frontend/public/data/indices.json`.
- [ ] Copiar os tokens de cor e tipografia do protótipo para `src/styles/tokens.css` (temas claro, escuro e alto contraste).
- [ ] Criar `src/fixtures/indices.exemplo.json` seguindo o contrato. O site lê a URL de `PUBLIC_DADOS_URL` (padrão: `data/indices.json`); em desenvolvimento, ela aponta para o exemplo. O arquivo real é só o que o backend publica.

## Tarefa 2 — Leitura e validação dos dados

**Arquivos:** `src/lib/dados.ts`, `src/lib/dados.test.ts`

- [ ] Testes:
  - JSON válido → objeto tipado;
  - `schema_version` desconhecido → erro de carregamento (não mostra dados parciais);
  - `gerado_em` há mais de 12 h → `desatualizado = true` (RN12);
  - município em `municipios_sem_dados` → estado "sem dados".
- [ ] Validar com o mesmo `docs/indices.schema.json` do backend.

## Tarefa 3 — Regras de exibição

**Arquivos:** `src/lib/formato.ts`, `src/lib/classes.ts` e testes

- [ ] Testes:
  - `formatarIndice(1.3449) === "1,34"`; `formatarMm(72) === "72,0"` (RN05);
  - `classe()` com as mesmas fronteiras do backend (0,9999 → 3; 1,00 → 4; 1,80 → 5);
  - `gerado_em` (data-hora) é exibido no horário de Brasília;
  - `dia_alvo` (data) é exibido sem conversão de fuso: `2026-09-29` aparece como 29/09/2026;
  - tendência = índice D0 − último valor do `historico`; acima de +0,005 sobe, abaixo de −0,005 desce.
- [ ] `classes.ts` exporta nome, cor (classe 7 = `#713371`), ícone e hachura de cada classe (RN03).

## Tarefa 4 — Simulação (RN07)

**Arquivos:** `src/lib/simulacao.ts`, `src/lib/simulacao.test.ts`

- [ ] Testes:
  - h = 24: `(efr + chuva) / limiar`;
  - h = 48 com MV = 24: EfR multiplicado por 0,5;
  - h = 72 com MV = 24: EfR multiplicado por 0,25;
  - chuva fora de 0–400 mm é limitada à faixa;
  - modo regional aplica a mesma chuva a todos os municípios.
- [ ] Implementar `simular({efr_mm, limiar_mm, mv_h}, chuva, h)`. A simulação nunca altera os dados carregados (RN07).

## Tarefa 5 — Estrutura comum

**Arquivos:** `src/layouts/Base.astro`, `src/components/Menu.tsx`, `Cabecalho.tsx`, `PainelAcessibilidade.tsx`, `BotaoTelegram.tsx`

- [ ] Menu com as 7 telas (barra inferior abaixo de 900 px), cabeçalho com dia-alvo e horário da atualização (RN11) e aviso de desatualizado (RN12).
- [ ] Seletor PT/ES com i18n por chaves (reaproveitar o dicionário do protótipo).
- [ ] Painel de acessibilidade: tema e paleta, guardados no `localStorage` com `try/catch` (RF13).
- [ ] Botão "Alertas no Telegram" abrindo o bot (`?start=<ibge>` quando vier do painel).

## Tarefa 6 — Monitoramento (`/`)

- [ ] Mapa react-leaflet com o GeoJSON do IBGE, polígonos coloridos pela classe, hachura a partir de moderado e rótulo com nome e índice (RF01).
- [ ] Resumo "N de M em alerta" (M = municípios no JSON), seletor D0–D3 com a marca "valores estimados" (RF03, RN06).
- [ ] Busca por nome sem acento e painel do município (RF02), com Compartilhar, Simular e Telegram (RF04).
- [ ] Aviso "não constitui alerta oficial" no painel, na Simulação e em Dados da análise (RN04).

## Tarefa 7 — Simulação (`/simulacao`)

- [ ] Formulário (município, período, chuva, atalhos, modo regional), mapa recolorido, comparação agora × simulado e aviso em três níveis (RF05).

## Tarefa 8 — Dados da análise (`/dados`)

- [ ] Indicadores, gráfico de evolução com `historico` e linha de alerta, pluviômetro com `chuva_acum_mm` e limiar, tabela com tendência (RF06).
- [ ] Bloco com probabilidades e valores usados no cálculo (RF07).
- [ ] Histórico de ocorrências do município, lido de `data/ocorrencias.json` (RF07).
- [ ] Camada de suscetibilidade do CPRM no mapa, **só se** o levantamento confirmar os dados (RF07, opcional).

## Tarefa 9 — Telas de apoio

- [ ] Monitoramento SC: iframe com crédito e link, ligado por uma flag de configuração ativada só após a autorização (RN10); se bloquear, só o link (RF08).
- [ ] Estações: pins a partir de `data/estacoes.json` (RF09).
- [ ] Cartilha e Contatos, com o conteúdo do protótipo; só contatos verificados (RF10, RN09).

## Tarefa 10 — Verificação

- [ ] axe-core sem violações sérias ou críticas nos 3 temas e 2 idiomas (RNF01).
- [ ] Sem rolagem lateral de 320 px até desktop (RNF02).
- [ ] Lighthouse no celular, com 4G simulado: LCP ≤ 2,5 s; troca de dia e simulação em até 500 ms, medidas com `performance.now()` (RNF03).
- [ ] Site servido só por HTTPS e nenhum token no build (busca por `TOKEN` em `dist/`) (RNF06).
- [ ] Idioma, tema e paleta continuam após recarregar a página (RF13).
- [ ] Com o `indices.json` apagado ou antigo, o site mostra o erro ou o aviso correto (RNF04).

## Critério de pronto

- `vitest` passa.
- O deploy no GitHub Pages abre as 7 telas com o JSON de exemplo.
- As verificações da Tarefa 10 passam.
