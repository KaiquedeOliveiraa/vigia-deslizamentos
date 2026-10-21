# Tela "Áreas de risco" (setores do SGB e ocorrências)

Parte 3 de 5 do pacote "site mais completo e oficial". Antes dela vêm a parte 1 (Alto Vale, 27 municípios, PR #12) e a parte 2 (ocorrências do Atlas, PR #13). Esta parte depende das duas.

## Objetivo

Trocar a tela "Estações", que mostra estações do INMET quase todas fora da região, por uma tela que mostra **onde** está o risco de deslizamento dentro dos municípios e **o que já aconteceu ali**:
- os setores de risco geológico mapeados em campo pelo Serviço Geológico do Brasil (SGB/CPRM);
- o histórico de ocorrências do Atlas Digital de Desastres, feito na parte 2.

**Pronto quando:**
- o morador abre a tela, vê os setores de risco alto e muito alto da região, escolhe o município dele e entende quais áreas são de risco, quantas pessoas moram nelas, o que o SGB recomenda e o histórico de eventos;
- tudo funciona em PT, ES e EN, em 320, 390 e 1366 px, por toque, mouse e teclado;
- a fonte oficial e a data do mapeamento aparecem sempre.

## Decisões

| Tema | Decisão |
|---|---|
| Abertura da tela | Mapa da região com os setores e um painel ao lado (opção A) |
| Setores | Só movimento de massa: deslizamento, rastejo, corrida de massa e queda (com tombamento e rolamento, se aparecerem). Inundação, enchente, enxurrada e erosão ficam de fora |
| Dados | Script sob demanda que grava um arquivo versionado (mesmo padrão das partes 1 e 2). O site não consulta o SGB ao vivo |
| Exibição | Tudo visível: local, tipo, grau, pessoas, moradias, recomendação do SGB com o ano, data do mapeamento e a frase "fora dos setores também pode haver risco" |
| Ocorrências | Saem da tela Dados e ficam só nesta tela |
| Estações do INMET | Camada que se pode ligar, desligada por padrão; o `estacoes.json` continua (o pipeline usa) |
| Rota | `/areas-de-risco/` (e `/es/`, `/en/`); `/estacoes/` redireciona para ela |

Medição de 2026-10-21 nos 27 municípios:
- 94 setores de movimento de massa: 65 de deslizamento, 17 de rastejo, 11 de corrida de massa e 1 de queda;
- graus: 67 alto e 27 muito alto;
- 3.062 pessoas expostas;
- 17 municípios com pelo menos um setor;
- cerca de 78 KB com 5 casas decimais.

## 1. Dados

**Script:** `backend/scripts/gerar_setores_risco.py`, no padrão de `gerar_estacoes.py`, `gerar_municipios.py` e `gerar_ocorrencias.py`.
- Consulta `https://geoportal.sgb.gov.br/server/rest/services/gestaoterritorial/risco/MapServer/0/query` com:
  - `where=cd_geocmu IN (<os códigos de backend/config/municipios.json>)`;
  - `outFields=*`, `returnGeometry=true`, `outSR=4326`, `geometryPrecision=5` e `f=geojson`.
- Paginação: se a resposta indicar `exceededTransferLimit`, buscar o resto com `resultOffset`.
- HTTP diferente de 200 ou resposta com `error` interrompe o script com erro.
- Filtro: `tipolo_g1` em TIPOS, um mapa do rótulo do SGB para o rótulo publicado:
  - "Deslizamento" → "Deslizamento"
  - "Rastejo" → "Rastejo"
  - "Corrida de massa" → "Corrida de massa"
  - "Queda", "Tombamento" e "Rolamento" → "Queda"
- `grau_risco`: "Alto" → `"alto"`; "Muito alto" → `"muito alto"`. Outro valor descarta o setor, com aviso no log.
- Limpeza de texto:
  - tirar espaços das pontas;
  - " " ou vazio vira `null`;
  - quebras de linha internas viram " · ";
  - espaços repetidos viram um só.
- `data_setor` vem em epoch ms; vira a data UTC em AAAA-MM-DD.
- Saída: `frontend/public/data/setores_risco.geojson`, ordenada por `ibge` e depois `id`, gravada com `json.dumps(..., ensure_ascii=False, separators=(",", ":"))` e `newline="\n"`. Fica numa linha só, para o arquivo ser pequeno.

**Contrato** (vai para `docs/contratos-de-dados.md`):

```
{
  "type": "FeatureCollection",
  "fonte": "Serviço Geológico do Brasil (SGB), setorização de riscos geológicos",
  "gerado_em": "AAAA-MM-DDTHH:MM:SSZ",
  "features": [ {
    "type": "Feature",
    "geometry": Polygon | MultiPolygon (lon, lat; WGS84),
    "properties": {
      "id": string,            // num_setor do SGB, único
      "ibge": string,          // 7 dígitos, um dos municípios configurados
      "local": string | null,
      "tipo": "Deslizamento" | "Rastejo" | "Corrida de massa" | "Queda",
      "grau": "alto" | "muito alto",
      "descricao": string | null,
      "pessoas": int | null,
      "moradias": int | null,
      "recomendacao": string | null,
      "data": "AAAA-MM-DD" | null
    } } ]
}
```

## 2. Tela e mapa

**Rota e menu:**
- `TELAS` em `frontend/src/lib/telas.ts`: a entrada `estacoes` vira `{ rota: "areas-de-risco", nome: "Áreas de risco", curto: "Riscos" }`, na mesma posição do menu.
- A página `frontend/src/pages/[...lang]/estacoes.astro` dá lugar a `areas-de-risco.astro`.
- `/estacoes/` (e `/es/estacoes/`, `/en/estacoes/`) redireciona para a rota nova. Pode ser pela opção `redirects` do Astro ou por uma página com `<meta http-equiv="refresh">` e um link, a que funcionar com `base`.
- Ícone do menu: um ícone de terreno ou alerta do lucide, por exemplo `Mountain`.

**Mapa (componente `Mapa`/`MapaLeaflet` de hoje):**
- **Municípios:** os 27 com preenchimento neutro (sem cor de índice) e contorno; tocar num município seleciona o município.
- **Setores, de longe:** com o zoom abaixo da abertura + 1 passo (a regra relativa da parte 1, `rotulosDeLonge`), cada setor aparece como um marcador circular no centro do polígono. As cores vêm dos tokens das classes: alto = `var(--c5)`, muito alto = `var(--c6)`.
- **Setores, de perto:** os polígonos reais, com a mesma cor.
- **Tocar num setor**, marcador ou polígono, seleciona o setor.
- **Legenda própria:** risco alto, risco muito alto e a frase "Setores mapeados pelo SGB".
- **Estações do INMET:** camada desligada por padrão, com um botão "Estações do INMET". Ligada, mostra os pinos de hoje.
- **Busca de município:** como hoje.
- **Celular:** o mapa vem em cima, ocupando a área visível, e o painel embaixo, como na tela Estações de hoje.

## 3. Painel

1. **Nada selecionado:**
   - o resumo da região: "{N} setores de risco de movimento de massa em {N} dos {N} municípios · {N} pessoas em áreas de risco alto ou muito alto";
   - a lista dos municípios com setores, do maior número para o menor (desempate pelo nome), com o número de setores e de pessoas; cada item é um botão;
   - a frase fixa: "Fora dos setores mapeados também pode haver risco. Em perigo, ligue 199."
2. **Município selecionado:**
   - o resumo: "{M}: {N} setores ({N} muito alto, {N} alto) · {N} pessoas";
   - a lista dos setores, um botão por setor com tipo, grau e local. É a alternativa por teclado e leitor de tela aos marcadores; tocar seleciona o setor e centraliza o mapa nele;
   - sem setores: "O SGB não mapeou setores de risco de deslizamento em {M}. Isso não significa que não haja risco.";
   - o cartão de ocorrências da parte 2, que sai de `Dados.tsx` para um componente próprio.
3. **Setor selecionado:**
   - título com o tipo e o grau, na cor do grau;
   - local, descrição, pessoas e moradias expostas;
   - "Recomendação do SGB ({ano})";
   - "Mapeado em {data}";
   - a fonte com link para o geoportal do SGB;
   - o botão "Voltar para {M}".

`pessoas` e `moradias` nulos aparecem como "não informado" e não entram nas somas. O resumo conta só os valores conhecidos.

**Textos e idiomas:**
- **Traduzidos em ES e EN:** a interface, os 4 tipos e os 2 graus.
- **Em português:** `local`, `descricao` e `recomendacao`, que vêm do SGB. Isso fica registrado como limitação.

**Tela Dados:** o cartão de ocorrências sai dela, junto com o carregamento do `ocorrencias.json`. As frases do cartão continuam no dicionário, usadas pelo componente novo.

## 4. Testes

- **Backend, `gerar_setores_risco`:** com uma resposta fixa do SGB, incluindo setores de inundação e erosão, campos com " ", quebras de linha e grau desconhecido:
  - filtro por tipo e mapeamento do tipo;
  - grau;
  - limpeza dos textos;
  - data a partir do epoch;
  - paginação com `exceededTransferLimit`;
  - erro HTTP;
  - contrato da saída;
  - o arquivo versionado só tem municípios configurados, os 4 tipos e os 2 graus, com `id` único.
- **Frontend, funções puras em `frontend/src/lib/`:**
  - leitura e validação do GeoJSON (feições inválidas são descartadas);
  - resumo da região e por município (nulos fora das somas);
  - ordenação da lista de municípios;
  - centro do polígono para o marcador;
  - escolha marcador × polígono pela regra de zoom.
- **i18n:** as frases novas em `es.json` e `en.json`, com o teste de paridade.
- **Navegador:** PT, ES e EN, a 320, 390 e 1366 px:
  - os três estados do painel;
  - a troca entre marcador e polígono;
  - a camada do INMET;
  - o redirecionamento de `/estacoes/`;
  - nenhuma rolagem horizontal;
  - a lista de setores percorrível pelo teclado.

## 5. Documentação e implantação

- **Documentação:**
  - `contratos-de-dados.md`: o contrato novo;
  - README: a tela nova e o SGB na tabela de fontes;
  - `pendencias.md`: atualizar os setores quando o SGB publicar um mapeamento novo.
- **Sem mudança:** pipeline, bot, Worker, `indices.json` e `estacoes.json`.
- **PR:** um só, em cascata depois do #12 e do #13, com base em `feat/ocorrencias-atlas`.
- **Reversão:** reverter o PR. A tela Estações volta, e o cartão de ocorrências volta para a tela Dados.

## Fora do escopo

- Setores de inundação, enchente, enxurrada e erosão.
- Consulta ao SGB em tempo real.
- Pluviômetros do Cemaden (item separado, depende de cadastro na PED).
- Tradução de `local`, `descricao` e `recomendacao`.
- Setores como camada na tela Monitoramento.
