# Tela "Áreas de risco" (setores do SGB e ocorrências)

Parte 3 de 5 do pacote "site mais completo e oficial". Depende da parte 1 (Alto Vale, 27 municípios, PR #12) e da parte 2 (ocorrências do Atlas, PR #13).

Revisão 2: incorpora duas revisões independentes. Uma conferiu o código e o serviço real do SGB. A outra procurou falhas de desenho, de segurança e de acessibilidade.

## Objetivo

A tela "Estações" mostra estações do INMET quase todas fora da região. Ela dá lugar a uma tela que mostra:
- **onde** está o risco geológico de movimento de massa dentro dos municípios, pelos setores mapeados em campo pelo Serviço Geológico do Brasil (SGB/CPRM);
- **o que já aconteceu** em cada município, pelo histórico de ocorrências do Atlas Digital de Desastres, feito na parte 2.

**Pronto quando:**
- o morador abre a tela, vê na região onde há setores, escolhe o município e entende quais áreas o SGB mapeou como de risco, quantas pessoas vivem nelas, o que o SGB recomenda e o histórico de eventos;
- ninguém sai achando que "fora do setor é seguro";
- ninguém confunde o risco geológico do terreno com o índice de chuva das outras telas;
- tudo funciona em PT, ES e EN, a 320, 390 e 1366 px, com toque, mouse e teclado;
- a fonte oficial e a data do mapeamento estão sempre visíveis.

## Decisões

| Tema | Decisão |
|---|---|
| Abertura | Mapa da região e painel ao lado (opção A) |
| Setores | Movimento de massa (deslizamento, rastejo, corrida de massa, queda) em **qualquer** uma das tipologias `tipolo_g1` a `tipolo_g5` do SGB. Inundação, enchente, enxurrada e erosão sozinhas ficam de fora |
| Dados | Script sob demanda que grava um arquivo versionado. O site o carrega em tempo de execução com `carregar()`, como os outros arquivos de dados; não vai embutido no bundle |
| Exibição | Tudo visível: local, tipo, grau, pessoas, moradias, recomendação, data do mapeamento e a fonte |
| Nome do risco | Sempre "risco geológico alto" e "risco geológico muito alto (SGB)". Cores e formas próprias, diferentes das classes do índice de chuva |
| Segurança | Uma faixa fixa, em todos os estados: "Mapeamento parcial do SGB: fora dos setores também pode haver risco. Isto é o terreno, não o alerta de chuva de hoje (veja Monitoramento). Em perigo, ligue 199." Mais a ressalva RN04 de que o sistema não é alerta oficial |
| Visão regional | Um marcador por município com o número de setores. Os setores individuais aparecem ao escolher o município ou ao aproximar |
| Ocorrências | Saem da tela Dados e ficam só aqui. A tela Dados ganha um link para esta tela |
| Estações do INMET | Camada que se pode ligar, desligada por padrão (decisão do time). O `estacoes.json` continua, porque o pipeline o usa |
| Rota | `/areas-de-risco/` (e `/es/`, `/en/`). `/estacoes/` redireciona para ela |
| Estado na URL | `?municipio=<ibge>&setor=<id>`, com `replaceState`. Valor desconhecido é ignorado. `setor` implica o município dele |

Medição de 2026-10-21 nos 27 municípios:
- 249 setores no total;
- 94 com movimento de massa na tipologia principal e mais 4 com movimento de massa numa tipologia secundária, cerca de 98 no total;
- tipos na principal: 65 deslizamento, 17 rastejo, 11 corrida de massa, 1 queda;
- 17 municípios com pelo menos um setor;
- pessoas: 3.062 nos 94, mais 139 nos 4;
- todas as geometrias são `Polygon`;
- `num_setor` é único;
- datas de 2011 a 2024;
- arquivo de cerca de 120 KB.

## 1. Dados

**Script:** `backend/scripts/gerar_setores_risco.py`, no padrão dos outros geradores.

- **Consulta:** `https://geoportal.sgb.gov.br/server/rest/services/gestaoterritorial/risco/MapServer/0/query` com:
  - `where=cd_geocmu IN ('<ibge>', …)`, com os códigos **entre aspas**, porque o campo é texto, tirados de `backend/config/municipios.json`;
  - `outFields=*`, `returnGeometry=true`, `outSR=4326`, `geometryPrecision=5`, `f=geojson`.
- **Completude:** antes, uma chamada com `returnCountOnly=true`. Se o número de feições recebidas for diferente da contagem, o script para com erro. É mais simples e verificável que paginar: o `maxRecordCount` do serviço é 100000 e hoje são 249.
- **Erros:** HTTP diferente de 200, ou resposta com `error`, interrompe o script.
- **Filtro e tipo:** o `tipo` é a **primeira** tipologia de movimento de massa entre `tipolo_g1` e `tipolo_g5`; setores sem nenhuma ficam de fora. O contrato usa **códigos estáveis** (a tradução fica no site):
  - "Deslizamento" → `deslizamento`
  - "Rastejo" → `rastejo`
  - "Corrida de massa" → `corrida_massa`
  - "Queda", "Tombamento" e "Rolamento" → `queda`
- **Grau:** "Alto" → `alto`, "Muito alto" → `muito_alto`. Outro valor descarta o setor, com aviso no log.
- **Limpeza de texto:**
  - tirar espaços das pontas;
  - " " ou vazio vira `null`;
  - quebras de linha internas viram " · ";
  - espaços repetidos viram um só.
- **Números:**
  - `pessoas` vem de `num_pess` e `moradias` de `num_domi`; os dois são convertidos para inteiro;
  - `0` continua `0`;
  - vazio ou inválido vira `null`.
- **Data:** `data_setor` vem em epoch ms e vira a data UTC em AAAA-MM-DD, ou `null`.
- **`id`:** é o `num_setor`. O script para com erro se houver `id` repetido.
- **`centro`:** um ponto `[lon, lat]` garantidamente dentro do polígono, onde o marcador do setor é desenhado. Usa o centroide se ele cai dentro; se não, o meio do maior trecho interno da horizontal que passa pelo centroide. A função `dentro` de `scripts/gerar_municipios.py` é reaproveitada. Em `MultiPolygon` usa a maior parte.
- **Aviso de dado pessoal:** o script avisa no log se `local`, `descricao` ou `recomendacao` tiverem algo com cara de telefone ou CPF. O dado é público e institucional do SGB, e o aviso serve para não publicar nada pessoal por engano.
- **Saída:** `frontend/public/data/setores_risco.geojson`, numa linha só, `ensure_ascii=False`, `newline="\n"`, ordenada por `ibge` e depois `id`.

**Contrato** (vai para `docs/contratos-de-dados.md`):

```
{ "type": "FeatureCollection",
  "fonte": "Serviço Geológico do Brasil (SGB), setorização de riscos geológicos",
  "gerado_em": "AAAA-MM-DDTHH:MM:SSZ",
  "features": [ { "type": "Feature",
    "geometry": Polygon | MultiPolygon (lon, lat; WGS84),
    "properties": {
      "id": string, "ibge": string, "centro": [lon, lat],
      "local": string | null,
      "tipo": "deslizamento" | "rastejo" | "corrida_massa" | "queda",
      "grau": "alto" | "muito_alto",
      "descricao": string | null, "recomendacao": string | null,
      "pessoas": int | null, "moradias": int | null,
      "data": "AAAA-MM-DD" | null } } ] }
```

## 2. Tela e mapa

**Rota e menu:**
- **`frontend/src/lib/telas.ts`:** a entrada `estacoes` vira `{ rota: "areas-de-risco", nome: "Áreas de risco", curto: "Áreas" }`, na mesma posição.
- **Ícone:** `Menu.tsx` troca `estacoes: Gauge` por `"areas-de-risco": Mountain`.
- **Página:** `pages/[...lang]/estacoes.astro` dá lugar a `areas-de-risco.astro`, com `Base tela="areas-de-risco"`, `<h1>` sr-only e `client:only="react"`.
- **Testes e dicionários afetados:** `telas.test.ts` (ordem das 7 rotas) e `es.json`/`en.json` (`nome`, `curto`, "VIGIA · Áreas de risco", "Tela Áreas de risco"). As chaves "Estações", "VIGIA · Estações" e "Tela Estações" saem; as frases de estação que a camada continua usando ficam.
- **Redirecionamento:**
  - em `astro.config.mjs`, `redirects` com o **destino incluindo o `base`**: `"/estacoes": "/vigia-deslizamentos/areas-de-risco/"`, e o mesmo para `/es/estacoes` e `/en/estacoes`;
  - motivo: medido no Astro 7.3.5, um destino sem o `base` gera um link que dá 404 no GitHub Pages;
  - o HTML gerado é conferido no build, numa checagem manual com grep no `dist`;
  - a página de redirecionamento perde `?query` e `#âncora`, o que é aceitável para links antigos.

**`MapaLeaflet`/`Mapa`** (trabalho novo; hoje o componente só desenha os municípios e pinos de um tipo):
- **Props novas:**
  - `setores` (as feições já lidas);
  - `setorSelecionado`;
  - `onSelecionarSetor`;
  - `mostrarSetoresIndividuais` (boolean controlado pela tela).
- **Visão regional:** a tela calcula `mostrarSetoresIndividuais = municípioSelecionado || !rotulosDeLonge(zoom, zoomInicial)`, com o `zoomInicial` desta tela. Para isso o `MapaLeaflet` passa a avisar a tela quando o zoom muda (`onZoom`).
- **Sem setores individuais:** um marcador por município que tem setores (um `divIcon` com o número de setores, no ponto interno do município). Tocar nele seleciona o município.
- **Com setores individuais:**
  - de longe, cada setor vira um marcador no `centro`; de perto, vira o polígono real;
  - **forma e cor por grau**, nunca só a cor (RN03): alto é um **círculo**, muito alto é um **losango**; os polígonos de muito alto ganham hachura;
  - tokens novos em `tokens.css`, `--setor-alto` e `--setor-muito-alto`, definidos para os temas claro e escuro e independentes da paleta das classes. Ficam num laranja-terra e num vinho, que não são as cores do índice de chuva. O contraste contra o fundo neutro do município é medido nos dois temas;
  - **área de toque:** o marcador visível tem cerca de 14 px, mas a área clicável tem no mínimo 24 px, e 44 px com `pointer: coarse`.
- **Teclado e leitor de tela:**
  - marcadores e polígonos de setor ficam **fora** do Tab (`tabindex=-1`, `aria-hidden`); o caminho por teclado é a lista de setores do painel. Isso evita 98 paradas de Tab;
  - os municípios continuam focáveis como hoje, e o `aria-label` deles nesta tela diz o nome e o número de setores, sem índice.
- **Seleção de setor:** centraliza o mapa no setor com `fitBounds`, com zoom máximo limitado.
- **Camada INMET:** os pinos de hoje passam a depender de uma prop que liga e desliga a camada. O enquadramento inicial **não** inclui os pinos, e o `aria-label` do mapa deixa de depender deles.
- **Legenda própria:** os símbolos de alto e muito alto, "marcador de município: número de setores", e o título "Risco geológico mapeado pelo SGB".
- **Município sem valores de índice:** fundo neutro. Isso já acontece hoje com `valores={{}}`.

**Celular:**
- o mapa vem em cima, ocupando a área visível, como nas outras telas com mapa;
- o painel vem embaixo;
- ao selecionar algo, o painel rola até ficar à vista;
- listas longas (setores, ocorrências) rolam dentro do próprio bloco, com altura máxima.

## 3. Painel

**Faixa de segurança fixa** (a da tabela de decisões), acima dos três estados, com link para Monitoramento.

1. **Nada selecionado:**
   - "{N} setores de risco geológico em {N} dos {N} municípios · {N} pessoas nos setores mapeados";
   - "Mapeamentos de {ano} a {ano}";
   - a lista dos municípios com setores, do maior número para o menor (desempate pelo nome), cada item como botão;
   - os municípios sem setor aparecem num item recolhido, "Sem setores mapeados: {M}, {M}, …".
2. **Município selecionado:**
   - "{M}: {N} setores ({N} risco muito alto, {N} alto) · {N} pessoas nos setores mapeados", com singular e plural corretos;
   - a lista dos setores (tipo, grau e local) como botões;
   - sem setores: "O SGB não mapeou setores em {M}. O mapeamento é parcial: isso não significa que não haja risco.";
   - o cartão de ocorrências, extraído de `Dados.tsx` para `components/Ocorrencias.tsx`. Ele recebe o `ibge` e o nome, com o seu CSS. Aparece mesmo sem setores e lembra que inclui eventos de chuva que não são deslizamento;
   - o link "Ver o índice de {M} em Monitoramento".
3. **Setor selecionado:**
   - título com o tipo e o grau, com o símbolo do grau;
   - local, descrição de campo, pessoas e moradias expostas ("não informado" quando nulo);
   - "Recomendação do SGB" e "Mapeado em {data}" ("data não informada" quando nula). O ano vem da `data`;
   - fonte com link para o geoportal do SGB;
   - o botão "Voltar para {M}", que devolve o foco ao botão do setor na lista.

**Somas:** contam só valores conhecidos e falam sempre em "pessoas nos setores mapeados", nunca em "pessoas em risco no município".

**Carregamento e erro:** enquanto carrega, "Carregando os setores…". Se o arquivo falhar, a mensagem "Não foi possível carregar os setores de risco." Um erro **nunca** aparece como "zero setores". O mapa dos municípios e as ocorrências continuam funcionando.

**Acessibilidade:**
- a seleção é anunciada com `anunciar()`;
- o foco vai para o título do painel;
- `local`, `descricao` e `recomendacao` levam `lang="pt-BR"`, e em ES e EN aparecem com a nota "texto original do SGB, em português".

**Tela Dados:**
- saem o cartão de ocorrências e o carregamento do `ocorrencias.json`;
- entra uma linha "Histórico de ocorrências e áreas de risco de {M}: ver em Áreas de risco", com link levando `?municipio=`.

**Idiomas:**
- **traduzidos em ES e EN:** a interface, os 4 tipos, os 2 graus, as somas com singular e plural, e a faixa de segurança;
- **sempre em português, com `lang`:** `local`, `descricao` e `recomendacao`.

## 4. Testes

- **Backend, `gerar_setores_risco`, com respostas fixas do SGB:**
  - tipologia secundária;
  - inundação e erosão sozinhas ficam de fora;
  - grau desconhecido;
  - " ", `\n` e espaços extras nos textos;
  - epoch convertido para data;
  - `0` contra vazio nos números;
  - `id` repetido dá erro;
  - contagem diferente da recebida dá erro;
  - erro HTTP e resposta com `error`;
  - `centro` dentro de um polígono côncavo;
  - aviso de telefone e CPF;
  - contrato da saída;
  - o arquivo versionado só tem municípios configurados, códigos de tipo e grau válidos e `id` único.
- **Frontend, funções puras:**
  - `lerSetores` descarta feições inválidas;
  - resumo da região e por município (nulos fora das somas; singular e plural);
  - ordenação da lista;
  - leitura e escrita de `?municipio=`/`?setor=`, ignorando valores inválidos e com o setor implicando o município;
  - a regra de setores individuais.
- **Build (checagem manual):** a página de redirecionamento aponta para `/vigia-deslizamentos/…/areas-de-risco/` nos 3 idiomas.
- **i18n:** paridade das chaves, com as chaves antigas de Estações removidas.
- **Navegador:**
  - PT, ES e EN, a 320, 390 e 1366 px;
  - os três estados, o marcador por município, a troca para setores, a forma por grau e a camada INMET;
  - URL compartilhada, redirecionamento e erro de carregamento (simulado);
  - teclado: municípios, lista de setores, "Voltar" com retorno do foco;
  - sem rolagem horizontal.

## 5. Documentação e implantação

- **`contratos-de-dados.md`:** o contrato novo.
- **README:**
  - a tela nova;
  - a tabela de rotas (`/areas-de-risco`);
  - RF07 (histórico nesta tela);
  - RF09 (estações como camada);
  - RF13 (PT, ES e EN);
  - o SGB na tabela de fontes.
- **`pendencias.md`:** atualizar os setores quando o SGB publicar um mapeamento novo.
- **Sem mudança:** pipeline, bot, Worker, `indices.json` e `estacoes.json`.
- **PR:**
  - um só, com base em `feat/ocorrencias-atlas`, em cascata depois do #12 e do #13;
  - se o #12 ou o #13 mudarem, este PR precisa de rebase.
- **Reversão:** reverter o PR. A tela Estações volta, e o cartão de ocorrências volta para Dados.

## Fora do escopo

- Setores só de inundação, enchente, enxurrada ou erosão.
- Consulta ao SGB em tempo real.
- Pluviômetros do Cemaden.
- Tradução dos textos do SGB.
- Agrupamento automático de marcadores (biblioteca de cluster); o marcador por município cobre isso.
- Aviso de "mapeamento antigo".
- Manter `?query` no redirecionamento.
- Setores na tela Monitoramento.
