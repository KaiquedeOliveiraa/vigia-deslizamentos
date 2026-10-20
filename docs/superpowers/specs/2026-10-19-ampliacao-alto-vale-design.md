# Ampliação para o Alto Vale do Itajaí (27 municípios)

Parte 1 de 5 do pacote "site mais completo e oficial". As outras partes têm especificação própria: histórico do Atlas/S2iD, setores de risco do SGB, filtros de período 7/30/personalizado e cartilha com fontes oficiais.

## Objetivo

Hoje o VIGIA cobre 6 municípios. O objetivo é cobrir as microrregiões IBGE **42011 (Rio do Sul)** e **42014 (Ituporanga)**, 27 municípios no total, sem mudar o cálculo do índice e mexendo o mínimo nos contratos de dados.

**Pronto quando:** o pipeline calcula os 27, o site mostra os 27 de forma legível no celular e no notebook e o bot deixa escolher qualquer um deles. Tudo isso sem quebrar o Worker em produção antes do deploy dele.

## Decisões tomadas com o time

| Tema | Decisão |
|---|---|
| Área | Microrregiões IBGE 42011 e 42014 (27 municípios), incluindo os 6 atuais |
| Limiar | 150 mm provisório para os 21 novos, com a mesma `fonte_limiar`; validação fica com o time |
| Pontos de coleta | Um ponto por município, gerado dentro do polígono; o campo `pontos` continua aceitando mais |
| Rótulos do mapa | Por zoom: na visão da região só o selecionado e os em alerta; com zoom, todos |
| Bot | Teclado em dois passos: região, depois os municípios dela |
| Contratos | Só acréscimos opcionais; nenhum campo renomeado ou removido; `schema_version` igual; `indices.json` inalterado |

## 1. Lista de municípios

**Script novo:** `backend/scripts/gerar_municipios.py`, no padrão do `gerar_estacoes.py`. Roda sob demanda e grava um arquivo versionado.

1. Busca a lista em `servicodados.ibge.gov.br/api/v1/localidades/microrregioes/{codigo}/municipios` para 42011 e 42014. Os dois códigos são a única configuração.
2. Pega os contornos na mesma malha do IBGE que o mapa usa: `tbrugz/geodata-br`, no commit fixado em `frontend/scripts/gerar-geojson.mjs`.
3. Para cada município novo, calcula um ponto garantido dentro do polígono, em Python puro, sem dependência nova:
   - usa o centroide quando ele cai dentro;
   - se cair fora, usa o meio do maior trecho interno da linha horizontal que passa pelo centroide.
4. Faz uma mescla com o `backend/config/municipios.json`:
   - **os municípios que já existem não são alterados** (ponto, limiar, fonte e `mv_h` ficam como estão), o que mantém o histórico gravado coerente;
   - os novos entram com `limiar_mm: 150`, a `fonte_limiar` provisória atual, o `mv_h` igual ao dos atuais e um ponto;
   - todos ganham `microrregiao: {"codigo", "nome"}`;
   - a saída sai ordenada por nome, para o diff ser estável.

**Contrato (`docs/contratos-de-dados.md`, `municipios.json`):** o campo opcional `microrregiao` é acrescentado. O carregador do backend aceita a ausência dele.

**GeoJSON do mapa:** `frontend/scripts/gerar-geojson.mjs` deixa de ter a constante `MONITORADOS` e passa a ler `backend/config/municipios.json`. Os 27 saem como `monitorado: true`, e os que encostam neles saem como contexto. O arquivo `src/data/municipios.geojson` é regenerado.

## 2. Pipeline e coleta

- O pipeline já itera sobre a lista e isola falhas por município (`municipios_sem_dados`). Não há código novo no cálculo.
- **Volume por execução:** 27 pontos × (3 modelos + 1 de chuva antecedente) = 108 chamadas; 4 execuções dão 432 por dia, contra o limite de 10.000 por dia e 600 por minuto. Não é preciso agrupar coordenadas. A conta do `docs/decisoes/ensemble.md` §9 é atualizada.
- Antes do PR, uma execução local completa (`scripts/rodar_local.py`) mede o tempo, e o número vai para a descrição do PR.
- **Histórico:** os 21 novos começam vazios. A tela Dados já avisa "há histórico de N dias", e o histórico se completa em 15 dias. Não há reconstrução do passado.
- **Avisos:** a regra não muda. Juntar vários avisos de uma execução numa só mensagem fica em `docs/pendencias.md`, caso o volume incomode.
- **Banco:** sem migração.

## 3. Mapa e telas

- **Rótulos:** uma função pura em `lib/mapa.ts` decide se o rótulo de um município aparece, a partir de selecionado, em alerta (índice ≥ `LIMIAR_ALERTA`) e o zoom atual comparado a um nível mínimo.
  - O `MapaLeaflet` aplica a função nas quatro telas com mapa.
  - Os rótulos dos vizinhos (contexto) só aparecem a partir do nível mínimo de zoom.
  - O `aria-label` dos polígonos não muda.
  - O nível mínimo é calibrado em 320, 390 e 1366 px.
- **Enquadramento:** o mapa continua ajustando a visão aos monitorados. É preciso conferir o zoom inicial no celular.
- **Evolução (Dados):** o município em destaque continua como linha. Os demais passam a uma faixa mínimo–máximo por dia, desenhada como sombra, no lugar das 26 linhas cinza. O cálculo da faixa é uma função pura em `lib/graficos.ts`.
- **Estações:** o `gerar_estacoes.py` roda de novo com os 27 municípios.
- **Cabeçalho:** "Vale Norte — Alto Vale do Itajaí, SC" vira "Alto Vale do Itajaí, SC" em PT, ES e EN. O README é atualizado.
- **Sem mudança:** a busca, o resumo ("X de 27"), o select da Simulação, a chuva regional, a tabela da tela Dados e os Contatos (que mostram só os verificados; os outros já exibem o aviso do 199). Levantar os contatos dos novos vai para `docs/pendencias.md`.

## 4. Bot do Telegram

**Contrato (`bot.json`), só acréscimos opcionais:**
- `grupos`: lista de `{nome, municipios: [ibge], opcao_todos, escolha, confirmacao}`, um item por microrregião, na ordem da configuração;
- `textos.opcao_voltar`.

Todos os textos são escritos pelo backend (`app/exportacao/bot_json.py`), em HTML do Telegram, como os demais.

**Rótulos dos grupos:** "Região de Rio do Sul" e "Região de Ituporanga". "Rio do Sul" também é nome de município, e o teclado envia o texto do botão. Um teste garante que nenhum rótulo de grupo, `opcao_todos` ou `opcao_voltar` coincide com o nome de um município.

**Worker (`bot-worker/src`):**
- **Sem `grupos`:** o teclado é o de hoje, um botão por município mais "Todos". Assim a ordem de implantação entre Worker e `bot.json` é livre.
- **Com `grupos`:**
  1. O `/start` mostra os grupos e "Todos os municípios".
  2. O botão de um grupo responde com o texto `escolha` e um teclado com os municípios do grupo em duas colunas, mais `opcao_todos` e `opcao_voltar`.
  3. O botão de um município faz a inscrição como hoje.
  4. `opcao_todos` inscreve nos municípios do grupo e responde `confirmacao`.
  5. `opcao_voltar` volta ao primeiro teclado.
- O `/start` com município sugerido (o link do site) não muda.
- **`/status`:** uma função pura divide o texto em mensagens de até 4.096 caracteres, sempre entre blocos inteiros. Cada parte é enviada em ordem.

**Bot local em Python (`backend/app/bot/bot.py`, sem Worker):** continua com um botão por município, sem grupos. Isso fica anotado no `backend/README.md`.

## 5. Testes

Todos sem rede, com o pytest rodando em `-W error` como hoje.

- **Backend:**
  - `gerar_municipios` com respostas fixas do IBGE e um trecho fixo da malha: 27 códigos, `microrregiao` presente, os 6 atuais idênticos ao arquivo de hoje e a saída ordenada;
  - ponto dentro de um polígono côncavo, em "U", cujo centroide cai fora;
  - `bot_json`: os `grupos` corretos e nenhuma colisão de rótulos;
  - a fixture `bot-worker/test/fixtures/bot.exemplo.json` regenerada com `VIGIA_REGERAR_FIXTURES=1`, e o teste de contrato Python × Worker continua valendo.
- **Worker:**
  - teclado sem `grupos`, que é o comportamento de hoje;
  - fluxo grupo → município, grupo → todos do grupo e voltar;
  - divisão do `/status` com 27 blocos, todas as partes com no máximo 4.096 caracteres e nenhum bloco cortado.
- **Frontend:**
  - regra de visibilidade dos rótulos;
  - faixa mínimo–máximo da Evolução;
  - frases novas em `es.json` e `en.json`, já cobertas pelo teste de paridade.
- **Navegador:** 320, 390 e 1366 px em PT, ES e EN, nas telas Monitoramento, Simulação, Dados e Estações, seguidos de uma revisão por subagente.

## 6. Implantação e reversão

1. **PR único** a partir da `main`.
2. **Depois do merge:** a próxima execução do pipeline calcula os 27 e publica `indices.json` e `bot.json` com `grupos`.
3. **Até o deploy do Worker:** o Worker atual ignora `grupos` e mostra os 27 num teclado só.
4. **Deploy manual do Worker** (`npm run deploy`): ativa o teclado em dois passos.
5. **Reversão:** reverter o `municipios.json`. Os novos param de ser calculados; as linhas deles no banco ficam sem efeito.

## Fora do escopo

- Limiar validado por município ou por região.
- Mais de um ponto de coleta por município.
- Reconstrução do histórico com dados ERA5.
- Agrupar avisos de uma execução numa só mensagem.
- Contatos dos 21 municípios novos.
- Grupos no bot local em Python.
