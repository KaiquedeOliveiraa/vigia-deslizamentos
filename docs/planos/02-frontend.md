# Plano 02 — Frontend (site no GitHub Pages)

**Objetivo:** implementar as 7 telas do protótipo navegável, com o mesmo comportamento, lendo os dados publicados pelo backend, com PT/ES e acessibilidade, no GitHub Pages.

**Base:**
- README: Telas, RF01–RF13, RNF01–RNF07, RN01–RN12;
- [Contratos de dados](../contratos-de-dados.md);
- protótipo navegável (`vigia-prototipo/`): fonte de verdade para layout, textos e interações. Este plano lista tudo o que o protótipo faz; quando o protótipo e a spec divergem, vale a spec (ver "Divergências do protótipo" no fim).

**Stack:** Astro + React (ilhas), TypeScript, react-leaflet + Leaflet, Vitest para a lógica, axe-core e Lighthouse para verificação. Ícones: Lucide. Fontes: Archivo e IBM Plex Mono (Google Fonts).

**Regra de trabalho:** toda lógica fica em `src/lib/`, com teste antes do código. Os componentes reproduzem o protótipo e só chamam funções de `src/lib/`. Commit ao fim de cada tarefa.

---

## Tarefa 1 — Projeto, deploy e design system

**Arquivos:** `frontend/` (Astro), `.github/workflows/pages.yml`, `src/styles/tokens.css`, `src/styles/base.css`

- [ ] Criar o projeto Astro com a integração React e o `base` do GitHub Pages.
- [ ] Workflow: build e deploy a cada push em `main` que altere `frontend/**`, inclusive os arquivos de `frontend/public/data/`.
- [ ] Converter `design-system/tokens.json` do protótipo em CSS custom properties com os mesmos nomes (`--nav-900`, `--accent`, `--on-accent`, `--accent-ink`, `--risk-1…7`, `--risk-icon-1…7`, `--acc-1…7`, `--acc-icon-1…7`, `--rain`, `--rain-track`, `--alert-bg`, `--danger-bg`…). Temas por `[data-theme="dark" | "contraste"]`; sem atributo, segue `prefers-color-scheme`. `--risk-7` = `#713371`.
- [ ] Paleta do mapa por classe no contêiner (`pal-geo` / `pal-acc`), com os componentes usando `var(--c1)…var(--c7)`.
- [ ] Criar `src/fixtures/indices.exemplo.json`, `ocorrencias.exemplo.json`, `estacoes.exemplo.json` e `contatos.exemplo.json` seguindo o contrato. O site lê as URLs de `PUBLIC_DADOS_URL` (padrão `data/`); em desenvolvimento, aponta para os exemplos.
- [ ] Copiar o GeoJSON dos 6 municípios e dos vizinhos (malha IBGE) para `src/data/`.

## Tarefa 2 — Leitura e validação dos dados

**Arquivos:** `src/lib/dados.ts`, `src/lib/dados.test.ts`

- [ ] Testes:
  - JSON válido → objeto tipado;
  - `schema_version` desconhecido → erro de carregamento (não mostra dados parciais);
  - `gerado_em` há mais de 12 h → `desatualizado = true` (RN12);
  - município em `municipios_sem_dados` → estado "sem dados";
  - `contatos.json`: só itens com `verificado: true` são devolvidos (RN09).
- [ ] Validar `indices.json` com o mesmo `docs/indices.schema.json` do backend.

## Tarefa 3 — Regras de exibição

**Arquivos:** `src/lib/formato.ts`, `src/lib/classes.ts`, `src/lib/texto.ts` e testes

- [ ] Testes:
  - `formatarIndice(1.3449) === "1,34"`; `formatarMm(72) === "72,0"`; `formatarRazao(0.6) === "0,60×"` (RN05);
  - coordenadas: `formatarCoord(-27.0007, -49.5212) === "27,0007° S, 49,5212° O"`;
  - `classe()` com as fronteiras do backend (0,70 → 3; 0,9999 → 3; 1,00 → 4; 1,80 → 5; 3,40 → 7);
  - `gerado_em` (data-hora) exibido no horário de Brasília; `dia_alvo` (data) sem conversão: `2026-09-29` → "29/09/2026" e, no formato curto, "29/09/26";
  - tendência = índice − valor do dia anterior; acima de +0,005 "subindo", abaixo de −0,005 "descendo", senão "estável";
  - busca: `normalizar("José Boiteux")` = `"jose boiteux"`; `"jose"` encontra José Boiteux;
  - texto de compartilhar: `"Ibirama — moderado (1,34)"`.
- [ ] `classes.ts`: para cada classe, nome em minúsculas, faixa (`< 0,40`, `0,40 – 0,70`, `0,70 – 1,00`, `1,00 – 1,80`, `1,80 – 2,60`, `2,60 – 3,40`, `≥ 3,40`), cor, cor do ícone e ícone:
  - 1–2: círculo com ✓;
  - 3: olho;
  - 4: triângulo com !;
  - 5: triângulo com !!;
  - 6: octógono com !;
  - 7: octógono com ×.
- [ ] Hachura por classe: nenhuma até 3; espaçamento 16, 11, 8 e 6 px para as classes 4 a 7; cruzada nas classes 6 e 7 (RN03).

## Tarefa 4 — Simulação (RN07)

**Arquivos:** `src/lib/simulacao.ts`, `src/lib/simulacao.test.ts`

- [ ] Testes:
  - h = 24: `(efr + chuva) / limiar`;
  - h = 48 com MV = 24: EfR × 0,5; h = 72: EfR × 0,25;
  - chuva fora de 0–400 mm é limitada à faixa;
  - modo regional aplica a mesma chuva a todos os municípios; sem ele, só o escolhido muda;
  - `nivelAviso(atual, simulado)`:
    - simulado ≥ 2,60 → `crit`;
    - ≥ 1,00 com atual < 1,00 → `entra`;
    - ≥ 1,00 com atual ≥ 1,00 → `continua`;
    - abaixo disso → `ok`;
  - `municipiosEmAlerta(valores)` devolve a lista e a contagem.
- [ ] A simulação nunca altera os dados carregados.

## Tarefa 5 — Gráficos (lógica)

**Arquivos:** `src/lib/graficos.ts`, `src/lib/graficos.test.ts`

- [ ] Testes:
  - escala do pluviômetro: máximo = maior valor entre 150 mm e limiar × 1,2 (com limiar 120 → 150; com limiar 250 → 300), para a linha do limiar sempre aparecer;
  - eixo Y do gráfico de evolução: até 2,00, ampliado para o maior índice arredondado para cima em 0,5 quando algum valor passar de 2,00;
  - mudança de classe entre dias consecutivos gera a marca "↑ classe" / "↓ classe";
  - indicadores: monitorados, em alerta (índice ≥ 1,00), chuva efetiva máxima (valor e município) e pico da semana (maior índice do `historico` + D0, com município e data);
  - etiqueta de chuva: acumulado 24 h > 1 mm → "choveu nas últimas 24h"; senão "sem chuva agora".

## Tarefa 6 — Estrutura comum

**Arquivos:** `src/layouts/Base.astro`, `src/components/Menu.tsx`, `Cabecalho.tsx`, `PainelAcessibilidade.tsx`, `JanelaTelegram.tsx`, `BannerTelegram.tsx`, `Dialogo.tsx`, `src/lib/preferencias.ts`, `src/i18n/`

**Menu (rail)**
- [ ] Desktop: barra de 64 px à esquerda, só ícones, com o nome em tooltip no hover.
- [ ] O botão de menu (hambúrguer) expande para 232 px com rótulos, sobrepondo o conteúdo (`aria-expanded`).
- [ ] Itens, na ordem: Monitoramento (mapa), Simulação (nuvem com chuva), Dados da análise (gráfico), Monitoramento SC (antena), Estações (estação), Cartilha (livro) e Contatos (telefone), sempre por último.
- [ ] Item ativo: fundo `nav-800`, ícone `accent`, barra de 3 px à esquerda, `aria-current="page"`.
- [ ] Rodapé do rail: botão Acessibilidade.
- [ ] Abaixo de 900 px: barra inferior com rótulos curtos (Mapa, Simular, Dados, SC, Estações, Cartilha, Contatos), que cabe em 320 px sem cortar itens.

**Cabeçalho**
- [ ] Marca (alvo laranja + "VIGIA" / "DESLIZAMENTOS").
- [ ] Região "Vale Norte — Alto Vale do Itajaí, SC".
- [ ] Botão "Alertas no Telegram".
- [ ] Seletor PT | ES com ícone de globo.
- [ ] Botão de acessibilidade.
- [ ] Status "dia-alvo dd/mm/aaaa · atualizado hh:mm" com ponto verde (RN11). Se desatualizado, faixa de aviso (RN12).
- [ ] No celular, PT/ES continua visível e nada é cortado.

**Painel de acessibilidade** (diálogo)
- [ ] Idioma: Português / Español.
- [ ] Tema: Automático / Claro / Escuro / Alto contraste, com a nota "Alto contraste: melhor leitura sob sol forte. Escuro: para ambientes com pouca luz."
- [ ] Cores do mapa: GeoRisk / Acessível (daltonismo), com a nota "Em qualquer opção, cada classe também tem ícone, nome e hachura no mapa."
- [ ] `preferencias.ts` guarda `{lang, theme, pal}` no `localStorage` com `try/catch`; padrão: pt, auto, geo. Teste: leitura com `localStorage` indisponível devolve o padrão (RF13).

**Janela do Telegram** (diálogo)
- [ ] Título "Receba os alertas no Telegram" e o texto de instrução.
- [ ] 3 linhas:
  - "Aviso quando um município entrar em alerta";
  - "Você escolhe os municípios dentro do bot";
  - "Grátis. Para sair, envie /parar".
- [ ] Botão "Abrir no Telegram" (`https://t.me/<bot>`, com `?start=<ibge>` quando aberto do painel de um município).
- [ ] "Ou procure @<bot> no Telegram", com botão de copiar.
- [ ] Ao lado, prévia "Como aparece no Telegram": mensagem do bot e teclado com os municípios + "Todos".
- [ ] Portas de entrada: botão do cabeçalho, botão do painel do município e banner (Cartilha e Contatos).

**Banner do Telegram**
- [ ] "Receba os alertas no Telegram", texto curto e botão "Quero receber", que abre a janela.

**Diálogos**
- [ ] Foco preso, Esc fecha e devolve o foco ao botão de origem, clique no fundo fecha.

**Acessibilidade comum**
- [ ] Link "Pular para o conteúdo"; `nav`, `main` e um `h1` por tela.
- [ ] Foco visível de 3 px; alvos de toque ≥ 44 px.
- [ ] Região `aria-live` que anuncia:
  - seleção de município;
  - dia de previsão;
  - resultado da simulação;
  - troca de idioma, tema e paleta;
  - cópia de texto.
- [ ] `prefers-reduced-motion` desliga animações.

**i18n**
- [ ] Chaves PT/ES a partir do dicionário do protótipo (`data/i18n-es.json`, 415 frases), com marcadores `{M}`, `{C}` e `{N}`. O atributo `lang` do documento acompanha o idioma.

## Tarefa 7 — Componentes do mapa

**Arquivos:** `src/components/Mapa.tsx`, `SeloClasse.tsx`, `Legenda.tsx`, `Busca.tsx`, `Previsoes.tsx`, `Camadas.tsx`

**Mapa**
- [ ] react-leaflet com o GeoJSON: municípios preenchidos por `var(--cN)`, hachura por classe e contorno `map-stroke`; vizinhos em cinza com o nome.
- [ ] Selecionado: contorno grosso `nav-900`, trazido para frente.
- [ ] Rótulo de cada município: selo da classe + "Nome 0,00" + nome da classe.
- [ ] Troca de cor animada em 0,6 s; "piscar" 2× ao escolher pela busca.
- [ ] Polígonos focáveis (Tab) e selecionáveis por Enter/Espaço, com `aria-label` "Nome: índice X, classe Y[, em alerta]".
- [ ] Município sem dados em cinza (`risk-nm`), sem índice.
- [ ] Zoom +/−.

**SeloClasse**
- [ ] Cor + ícone da classe (Tarefa 3), com tamanho normal e grande.

**Legenda recolhível**
- [ ] Recolhida: faixa de 32 px com as 7 cores e "não monitorado", do maior risco para o menor.
- [ ] Abre com hover, foco ou toque; fecha ao sair, se não estiver fixada.
- [ ] Botão cadeado fixa e destrava; × recolhe e destrava.
- [ ] Cartão:
  - título "Análise regional dinâmica de risco de deslizamento";
  - linhas com selo, nome e faixa;
  - troca GeoRisk / Acessível, sincronizada com o painel de acessibilidade;
  - nota "Alerta a partir de 1,00 (moderado). Classes com hachuras no mapa: moderado ou acima."

**Busca**
- [ ] Botão redondo de lupa no canto inferior esquerdo que abre o campo "Buscar município…".
- [ ] Busca sem acento, com o trecho encontrado destacado; cada resultado mostra selo, nome, classe e índice.
- [ ] ↑/↓ navega, Enter escolhe e Esc fecha (`role="combobox"`, `aria-activedescendant`).
- [ ] Sem resultado: "Nenhum município monitorado com esse nome."

**Previsões**
- [ ] Cartão com os 4 dias (dd/mm/aa e "hoje", "+1d", "+2d", "+3d") e botões voltar, reproduzir/pausar e avançar.
- [ ] Reproduzir avança um dia a cada ~1,1 s, em ciclo.
- [ ] Em D1–D3, faixa "Previsão · dd/mm/aa — valores estimados" sobre o mapa (RN06).

**Camadas**
- [ ] Botões Satélite, Neutro, Ruas e Relevo, trocando o *tile layer*. Ruas = OpenStreetMap; para os outros, escolher provedores gratuitos e manter a atribuição de cada um.

## Tarefa 8 — Monitoramento (`/`)

- [ ] Layout: mapa em toda a largura + painel do município à direita (330 px); no celular, o painel vai para baixo do mapa.
- [ ] Sobre o mapa:
  - zoom e Previsões no alto à esquerda;
  - Camadas no alto à direita;
  - Legenda e Busca embaixo à esquerda;
  - resumo "N de M municípios em alerta · maior índice X" embaixo à direita (RF01);
  - atribuição dos mapas.
- [ ] Município inicial: o de maior índice no D0.
- [ ] Painel:
  - "Município selecionado";
  - nome;
  - pílula "Em alerta" / "Sem alerta" com a classe;
  - índice grande com selo;
  - "índice de risco · classe", acrescido de "· previsão dd/mm/aa" em D1–D3.
- [ ] Variáveis (RF02):
  - chuva efetiva antecedente (mm, com barra);
  - limiar crítico (mm);
  - razão chuva/limiar (com barra);
  - membros de ensemble (`n_membros`).
- [ ] Botões (RF04):
  - Compartilhar (primário): Web Share quando disponível; senão copia o texto e mostra o toast "Link copiado: …" por ~2 s;
  - Simular chuva: abre `/simulacao?municipio=<ibge>`;
  - "Receber alertas de <município> no Telegram".
- [ ] Aviso "Sistema de apoio à decisão… Não constitui alerta oficial e não substitui o Cemaden nem a Defesa Civil." (RN04).

## Tarefa 9 — Simulação (`/simulacao`)

- [ ] Layout: formulário à esquerda e mapa à direita.
- [ ] Topo:
  - rótulo "Simulação de cenário";
  - título "E se chover…?";
  - texto "Parte das condições de agora (dd/mm, hh:mm). Informe a chuva que você espera e veja como o índice do município reagiria."
- [ ] Campos (RF05):
  - Município: lista, pré-selecionado por `?municipio=`;
  - Período: "próximas 24h / 48h / 72h", padrão 48 h;
  - Chuva esperada: controle deslizante e campo numérico sincronizados, de 0 a 400 mm;
  - atalhos: fraca 10, moderada 30, forte 60, muito forte 100 e extrema 180;
  - caixa "Aplicar a mesma chuva a todos os municípios (chuva regional)".
- [ ] Botões "Simular" (primário) e "Voltar à condição atual".
- [ ] Resultado no formulário:
  - "Agora" (índice e classe) → "Simulado" (índice e classe);
  - escala de 0 a 4 colorida pelas classes, com marcadores "agora" e "simulado" e as marcas 0, "1,00 alerta", 2,60 e 4,00;
  - chuva efetiva atual, chuva efetiva simulada e limiar crítico.
- [ ] Aviso sobre o mapa, conforme `nivelAviso`:
  - `crit`: "Risco <classe> em <M>" e "…poderá entrar em estado de alerta máximo… ligue 199";
  - `entra`: "<M> poderá entrar em alerta";
  - `continua`: "<M> continuaria em alerta";
  - `ok`: "Abaixo do nível de alerta".
- [ ] Com chuva regional, um segundo aviso: "Chuva regional: N de M em alerta", com os municípios que passariam de 1,00.
- [ ] Mapa:
  - recolore com animação e faz o município piscar;
  - alternância Agora | Simulado no alto à direita;
  - cartão "Condição atual · dd/mm hh:mm" ou "Cenário simulado", com "N de M municípios em alerta";
  - legenda e zoom;
  - clique num município o escolhe no formulário.
- [ ] Aviso de RN04 no formulário.

## Tarefa 10 — Dados da análise (`/dados`)

- [ ] Topo: "Dados da análise · dia-alvo dd/mm/aaaa", título "Como a região chegou até aqui", texto e seletor 7 / 5 / 15 dias (padrão 7), que muda o gráfico e os minigráficos.
- [ ] Quatro indicadores (Tarefa 5):
  - municípios monitorados;
  - em alerta (índice ≥ 1,0);
  - chuva efetiva máxima (mm, com município);
  - pico da semana (índice, município e data).
- [ ] Gráfico "Evolução do índice — <município>" (RF06):
  - chips para trocar o município e legenda "subindo / descendo / mudança de classe";
  - faixas de fundo pelas classes (22 % de opacidade);
  - grade e eixo Y (Tarefa 5);
  - linha tracejada "ALERTA 1,00";
  - demais municípios em linhas cinza finas;
  - destaque em linha grossa com pontos na cor da classe do dia;
  - variação do dia sobre cada ponto (+ em vermelho, − em verde);
  - marca de mudança de classe abaixo do ponto.
- [ ] Pluviômetro "Chuva acumulada" do município em destaque:
  - etiqueta "choveu nas últimas 24h" / "sem chuva agora";
  - subtítulo com a fonte;
  - 4 tubos (24H, 48H, 72H, 96H) com marcas a 25 %;
  - linha tracejada "limiar N mm";
  - valor "N,N mm" abaixo de cada tubo;
  - escala da Tarefa 5.
- [ ] Tabela "Índice por município":
  - colunas: município, índice, classe (selo + nome), variação 24 h (seta + valor), últimos dias (minigráfico com a linha de alerta), chuva efetiva / limiar (valor + barra), alerta (sim/não);
  - clicar numa linha troca o destaque do gráfico e do pluviômetro e marca a linha.
- [ ] Bloco "Detalhes do cálculo" do município em destaque (RF07):
  - probabilidades de deslizamentos pontuais, esparsos e generalizados;
  - EfR, chuva prevista, limiar e fonte, membros;
  - data da execução.
- [ ] Bloco "Ocorrências registradas" do município, de `ocorrencias.json` (data, tipo, descrição, fonte); sem registros: "Nenhuma ocorrência registrada" (RF07).
- [ ] Camada de suscetibilidade do CPRM, **só se** o levantamento confirmar os dados (RF07, opcional).
- [ ] Aviso de RN04.

## Tarefa 11 — Monitoramento SC (`/monitoramento-sc`)

- [ ] Cartão de introdução:
  - título "Monitoramento da Defesa Civil de SC";
  - texto sobre o mapa oficial (estações, chuva acumulada, rios e barragens);
  - botão "Abrir em nova aba" para `https://monitoramento.defesacivil.sc.gov.br/mapa`.
- [ ] Moldura:
  - barra com o título "Painel de monitoramento — Defesa Civil SC" e a URL;
  - `iframe`;
  - rodapé "Fonte: … — Secretaria de Estado da Proteção e Defesa Civil de Santa Catarina".
- [ ] O iframe só aparece com a flag `PUBLIC_SC_IFRAME=true`, ativada após a autorização (RN10). Sem a flag, ou se o carregamento falhar, aparece o plano B: "O mapa não pôde ser carregado aqui" + explicação + botão "Abrir mapa oficial" (RF08).
- [ ] Não entram: a checklist "Antes de integrar (para o time)" e o seletor "Pré-visualizar estado", que existem só no protótipo.

## Tarefa 12 — Estações (`/estacoes`)

- [ ] Mapa com os municípios em branco (sem cor de risco) e o nome escrito, mais um pin por estação de `estacoes.json` (RF09).
- [ ] Pin azul-marinho com miolo branco; o selecionado fica laranja e abre um balão com nome, município e coordenadas (Tarefa 3).
- [ ] Pins focáveis e selecionáveis por Enter; clicar de novo desmarca.
- [ ] Lista à direita:
  - título "Estações de monitoramento" e o texto de introdução;
  - um item por estação (nome, município, fonte INMET, coordenadas);
  - clicar seleciona o pin.
- [ ] Zoom.

## Tarefa 13 — Cartilha (`/cartilha`)

**Arquivos:** `src/conteudo/cartilha.ts` (textos em PT/ES), `src/pages/cartilha.astro`, componentes da tela

- [ ] Topo azul: "Cartilha", título "Deslizamento: como se proteger", "Aprenda a ver os sinais e o que fazer. É rápido: toque nos cartões." e botão grande "199 · Emergência? Ver contatos", que leva a `/contatos`.
- [ ] Navegação por âncoras "1. Sinais · 2. O que fazer · 3. Mochila · 4. Não faça", com rolagem suave e destaque da seção visível.
- [ ] **1. Sinais de perigo:** 6 cartões ilustrados que viram ao toque (`button` com `aria-pressed`). Frente com o sinal; verso com "Saia do local agora · Depois ligue 199". Os sinais:
  - rachaduras novas (no chão, muros ou paredes);
  - portas e janelas emperrando (saindo do esquadro);
  - árvores e postes inclinando (cercas e muros também);
  - água barrenta minando (na base do barranco);
  - estalos e barulhos (terra se mexendo);
  - muro estufado (embarrigando ou afastando).
- [ ] **2. O que fazer:** abas Antes / Durante / Depois (`role="tablist"`, setas ←/→), com 4 blocos cada:
  - Antes: plante grama na encosta; leve a água da chuva para longe; receba alertas (SMS 40199 ou Telegram); deixe a mochila pronta;
  - Durante: acompanhe os avisos; viu sinais? saia já; não atravesse lama correndo; ligue 199;
  - Depois: espere a Defesa Civil liberar; peça vistoria antes de voltar; fique longe da área atingida; fotografe os danos.
- [ ] **3. Mochila de emergência:** 8 itens marcáveis (documentos, lanterna, rádio e pilhas, remédios, água, carregador, roupa e agasalho, apito), com barra de progresso "N de 8" e "Mochila pronta!" ao completar.
- [ ] **4. Não faça:** 6 blocos com ícone riscado: jogar lixo no barranco; soltar esgoto na encosta; cortar o barranco; desmatar a encosta; plantar bananeira na encosta; construir na beira do barranco.
- [ ] Banner do Telegram e citação das fontes (Defesa Civil RJ e SP Sempre Alerta, com links).
- [ ] Ilustrações: reaproveitar os SVGs de traço do protótipo até haver ilustrações definitivas.

## Tarefa 14 — Contatos (`/contatos`)

- [ ] Topo: "Contatos", título "Defesa Civil e emergência", "Em perigo, ligue 199 de qualquer lugar. Os números funcionam 24 horas."
- [ ] Quatro cartões grandes (≥ 72 px), com o número também como texto selecionável:
  - 199 Defesa Civil (em destaque, `tel:`);
  - 193 Bombeiros;
  - 192 SAMU;
  - 40199 "SMS com seu CEP para receber alertas" (`sms:`).
- [ ] Banner do Telegram.
- [ ] Filtro "Seu município" (Todos + municípios): destaca o cartão escolhido, esmaece os outros e rola até ele.
- [ ] Um cartão por município de `contatos.json` (só verificados, RN09):
  - nome e selo "verificado";
  - responsável ("Coordenador(a) municipal de Defesa Civil");
  - telefone, e-mail e endereço.
- [ ] Botões do cartão:
  - "Como chegar": `https://www.google.com/maps/search/?api=1&query=<endereço>`, em nova aba;
  - "Copiar telefone", que muda para "Copiado";
  - sem telefone: "Site da prefeitura" no lugar.
- [ ] Nota: "Como chegar" abre o Google Maps.

## Tarefa 15 — Verificação

- [ ] axe-core sem violações sérias ou críticas nas 7 telas, nos 3 temas e nos 2 idiomas (RNF01).
- [ ] Sem rolagem lateral de 320 px até desktop; barra inferior e cabeçalho sem cortes em 320 e 390 px (RNF02).
- [ ] Lighthouse no celular com 4G simulado: LCP ≤ 2,5 s. Troca de dia e simulação em até 500 ms, medidas com `performance.now()` (RNF03).
- [ ] Com `indices.json` ausente, antigo ou com `schema_version` desconhecido, o site mostra o erro ou o aviso certo (RNF04, RN12).
- [ ] Só HTTPS; nenhum token no build (busca por `TOKEN` em `dist/`) (RNF06).
- [ ] Idioma, tema e paleta continuam após recarregar (RF13).
- [ ] Teclado: todas as telas operáveis sem mouse, incluindo mapa, legenda, busca, previsões, abas, cartões e diálogos.
- [ ] Conferência visual lado a lado com o protótipo, tela a tela, nos temas claro e escuro.

## Critério de pronto

- `vitest` passa.
- O deploy no GitHub Pages abre as 7 telas com os JSON de exemplo.
- As verificações da Tarefa 15 passam.

## Divergências do protótipo (vale a spec)

| Protótipo | Implementação |
|---|---|
| Classe 7 com a cor `#a349a3` | `#713371` (GeoRisk) |
| Controle deslizante até 250 mm e campo até 400 | Os dois de 0 a 400 mm |
| Fórmula ilustrativa da simulação | RN07 |
| Pluviômetro com escala fixa de 0 a 150 mm | Máximo entre 150 mm e limiar × 1,2 |
| Estações de exemplo (pluviômetros, réguas, Cemaden, Epagri) | Só as estações automáticas do INMET |
| Contatos "a confirmar" visíveis | Só contatos verificados (RN09) |
| Mapa em SVG próprio | react-leaflet + GeoJSON do IBGE |
| Tradução aplicada sobre o DOM | i18n por chaves |
| "N de 6" fixo | "N de M", derivado dos dados |
| Checklist e pré-visualização no Monitoramento SC | Não entram em produção |
| Camadas e período 5/15 dias sem efeito | Funcionais |
