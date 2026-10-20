# Ampliação para o Alto Vale do Itajaí (27 municípios)

Parte 1 de 5 do pacote "site mais completo e oficial". As outras partes terão especificação própria: histórico do Atlas/S2iD, setores de risco do SGB, filtros de período 7/30/personalizado e cartilha com fontes oficiais.

Revisão 2: incorpora duas revisões independentes, uma conferindo o código e os dados e outra procurando falhas de desenho e casos de borda.

## Objetivo

Hoje o VIGIA cobre 6 municípios. O objetivo é cobrir as microrregiões IBGE **42011 (Rio do Sul, 20 municípios)** e **42014 (Ituporanga, 7)**, 27 no total. O cálculo do índice não muda, e os contratos de dados mudam o mínimo possível.

**Pronto quando:**
- o pipeline calcula os 27;
- o site mostra os 27 de forma legível em 320, 390 e 1366 px, em PT, ES e EN;
- o bot deixa escolher qualquer um deles;
- nenhum aviso se perde por limite de envio do Telegram;
- o Worker em produção continua funcionando antes e depois do deploy dele.

## Decisões

| Tema | Decisão |
|---|---|
| Área | Microrregiões IBGE 42011 e 42014 (divisão de 1989, substituída pelas regiões imediatas em 2017; serve porque o script roda uma vez e a saída é versionada) |
| Limiar | 150 mm provisório para os 21 novos, com a mesma `fonte_limiar`; validação fica com o time |
| Ponto de coleta | O centroide do polígono, um por município, como hoje |
| Rótulos do mapa | Regra de zoom que já existe (`.longe`, zoom < 8,5): longe, só o selecionado e os em alerta; perto, todos |
| Bot | Teclado em dois passos (região, depois municípios), sem estado no servidor |
| Contratos | Só acréscimos opcionais; nenhum campo renomeado ou removido; `schema_version` igual; `indices.json` inalterado |
| Inscritos atuais em "Todos" | Continuam com os 6 que escolheram. O D1 guarda uma linha por `(chat_id, ibge)`, sem uma marca de "todos", e não se adivinha a intenção do inscrito. O README explica como passar a receber os 27 |

## 1. Lista de municípios

**Script novo:** `backend/scripts/gerar_municipios.py`, no padrão do `gerar_estacoes.py`. Roda sob demanda (não no pipeline) e grava `backend/config/municipios.json`.

1. **Lista:** busca `servicodados.ibge.gov.br/api/v1/localidades/microrregioes/{codigo}/municipios` para 42011 e 42014, nessa ordem; os dois códigos são a única configuração. Falha com erro se uma microrregião vier vazia ou se a resposta HTTP não for 200. O `id`, que o IBGE devolve como número, é convertido em texto de 7 dígitos, como no contrato.
2. **Contorno:** lido da malha `tbrugz/geodata-br`, no mesmo commit fixado em `frontend/scripts/gerar-geojson.mjs`. Falha se algum código não estiver na malha ou se a geometria não for um `Polygon` de um anel só. Conferido em 2026-10-19: os 27 são assim.
3. **Ponto:** centroide ponderado pela área do polígono, na ordem (lon, lat) do GeoJSON e arredondado a 4 casas, como os pontos atuais. Falha se o ponto arredondado não estiver dentro do polígono, pelo teste par-ímpar semiaberto. Conferido: o centroide dos 27 cai dentro. A frase do contrato "no mínimo o centroide" continua verdadeira.
4. **Mescla com o arquivo atual:**
   - **Municípios que já existem não mudam:** ponto, limiar, fonte, `mv_h` e `nome` ficam iguais. Se o IBGE trouxer outro nome, o script avisa no log e mantém o atual.
   - **Município que existe no arquivo e não veio do IBGE:** o script para com erro e nunca o remove.
   - **Novos:** entram com `limiar_mm: 150`, a `fonte_limiar` provisória atual, `mv_h: 24` e um ponto.
   - **Todos:** ganham `microrregiao: {"codigo": "42011", "nome": "Rio do Sul"}` (ou 42014, "Ituporanga").
   - **Ordem:** pelo nome normalizado (NFD sem acentos, depois `casefold`), com o `ibge` como desempate. A saída é estável no diff.

**Efeito da ordem nova:** o teclado do bot, o `/status` e a confirmação de "Todos" passam da ordem antiga (por código) para a alfabética. Com os 6 atuais as duas ordens coincidem; com os 27, a primeira é Agrolândia.

**Backend (`app/config.py`):**
- `Municipio` ganha o campo `microrregiao: Microrregiao | None = None`, com valor padrão para não quebrar quem já constrói o objeto;
- `_municipio_a_partir_de` lê e valida o campo quando ele existe (`codigo` com 5 dígitos e `nome` não vazio);
- a ausência do campo continua aceita.

**Contrato (`docs/contratos-de-dados.md`):** acrescenta o campo opcional `microrregiao` em `municipios.json`.

**GeoJSON do mapa (`frontend/scripts/gerar-geojson.mjs`):**
- a constante `MONITORADOS` sai, e a lista passa a ser lida do `backend/config/municipios.json`;
- os 27 saem como monitorados e os que encostam neles como contexto;
- o script falha se algum monitorado vier como `MultiPolygon`, porque `FeicaoMunicipio` e `posicoes()` só tratam `Polygon`;
- o arquivo `src/data/municipios.geojson` é regenerado. A estimativa é de cerca de 98 KB (23 KB comprimido), contra 38 KB hoje; ele entra no JavaScript de cada tela com mapa via `?raw`;
- um teste falha se ele passar de 150 KB.

## 2. Pipeline e coleta

- **Sem código novo no cálculo:** o pipeline já percorre a lista e isola a falha de cada município (`pipeline.py`, `municipios_sem_dados`).
- **Volume:** 27 × (3 modelos + 1 de chuva antecedente) = 108 chamadas, mais 3 `meta.json` em cache, dá 111 por execução e cerca de 444 por dia. Os limites são 600 por minuto e 10.000 por dia, então não é preciso agrupar coordenadas. Atualizar o `ensemble.md` §9.
- **Tempo:** as chamadas são sequenciais (`TIMEOUT_S=30`, 3 tentativas). O tempo de uma execução local completa (`scripts/rodar_local.py`) vai para a descrição do PR, e o critério é menos de 10 minutos em condição normal.
  - No pior caso, com o Open-Meteo degradado, as 111 chamadas podem passar do `timeout-minutes: 30` do job, e aí nada é publicado. Com 6 municípios esse risco já existia (cerca de 37 minutos).
  - O `timeout-minutes` passa a 60, e um prazo total de coleta fica registrado em `docs/pendencias.md` como próximo passo.
- **Histórico:** os 21 novos começam vazios e se completam em 15 dias, sem reconstrução do passado. Ver a seção 3 sobre o aviso por município.
- **Banco:** sem migração. As linhas dos novos aparecem conforme os cálculos rodam.
- **Avisos e limite do Telegram** (`app/bot/avisos.py`):
  - **O problema:** o envio é sequencial, sem espaçamento. Num evento regional, um chat inscrito em todos pode receber até 27 mensagens seguidas, e o Telegram responde 429 (`RetryAfter`), que hoje é tratado como falha transitória. Como a classe é registrada quando outro chat recebeu, aquele chat perde o aviso sem ninguém saber.
  - **Correção:**
    - capturar `telegram.error.RetryAfter`, esperar `retry_after` (com teto de 60 s) e tentar mais uma vez;
    - espaçar os envios em pelo menos 50 ms;
    - se ainda falhar, registrar no log como erro, que já vira aviso no resumo do Actions.
  - **Teste:** um bot falso que levanta `RetryAfter` uma vez e depois entrega; o teste confere que a mensagem chega e que houve uma espera.
- **Estações do INMET:**
  - `gerar_estacoes.py` roda de novo com os 27, e o número de estações vai para a descrição do PR.
  - Se passar de 12, o `RAIO_DE_CORTE_KM` cai de 100 para 50 km, porque cada estação é uma chamada sequencial na comparação de 24 h quando há token.
  - A863 Ituporanga e A861 Rio do Campo passam a ficar **dentro** de municípios monitorados. Os textos "nenhuma estação fica dentro" mudam para algo verdadeiro, por exemplo "algumas ficam dentro dos municípios; as outras mostram a distância até o município mais próximo". Isso vale para a tela Estações (PT, ES e EN), `contratos-de-dados.md`, os docstrings de `inmet.py` e `gerar_estacoes.py`, o `ensemble.md` §8 e o `backend/README.md`.

## 3. Site

**Telas com mapa (Monitoramento, Simulação e Estações):**
- **Rótulos:**
  - **Hoje:** o `MapaLeaflet` já põe a classe `.longe` no mapa abaixo do zoom 8,5.
  - **Regra nova:** o rótulo do município ganha a classe `sel` quando está selecionado e `alerta` quando o índice é ≥ `LIMIAR_ALERTA`. A classe é decidida por uma função pura em `lib/mapa.ts`, com teste.
  - **CSS:** `.longe .mlabel:not(.sel):not(.alerta)` esconde os demais, e os rótulos de contexto já somem com `.longe`. Não há nova renderização ao trocar o zoom.
  - **Limiar de zoom:** o 8,5 é recalibrado em 320, 390 e 1366 px.
  - **Sem selecionado e sem alerta, de longe,** nenhum rótulo aparece; a cor da classe informa.
  - **Acessibilidade:** os rótulos são tooltips com `aria-hidden`, e o `aria-label` do polígono continua carregando o nome e a classe.
- **Enquadramento:** `limites()` já enquadra só os monitorados. A área cresce de cerca de 0,6° × 0,5° para 0,97° × 1,16°, então o zoom inicial cai; conferir no celular.

**Dados:**
- **Evolução:**
  - **Linhas:** o município em destaque continua como linha. As 26 linhas cinza viram uma **faixa mínimo–máximo dos demais**, calculada por dia só com os municípios que têm dado naquele dia; num dia com menos de 2, não há faixa. A legenda ganha "faixa: mínimo e máximo dos demais municípios". O cálculo é uma função pura em `lib/graficos.ts`, testada com dias em que só parte dos municípios tem dado.
  - **Abas:** as abas com um botão por município (27 no celular) viram um `<select>` nativo, como nas camadas.
  - **Dica ao passar o mouse:** passa a mostrar o valor do município em destaque, o mínimo e o máximo dos demais, em vez de 27 linhas.
  - **Tabela para leitor de tela (sr-only):** fica só com o município em destaque, e isso é documentado no componente.
- **Aviso de histórico curto:** hoje ele usa os dias com dado de qualquer município, por isso nunca aparece para os novos. Passa a usar os dias do **município em destaque**: "Por enquanto há histórico de N dias para {M}…", com uma frase nova em PT, ES e EN.

**Cabeçalho e textos:**
- "Vale Norte — Alto Vale do Itajaí, SC" vira "Alto Vale do Itajaí, SC". É a mesma chave do dicionário, trocada, em PT, ES e EN, e "Alto Vale do Itajaí" é nome próprio, então não se traduz.
- A janela do Telegram no site (`JanelaTelegram.tsx`), que imita o teclado do bot, passa a mostrar o primeiro passo: "Região de Rio do Sul", "Região de Ituporanga" e "Todos".

**Sem mudança:** a busca, o resumo ("X de 27"), o select da Simulação, a chuva regional, a tabela da tela Dados e os Contatos. Os novos mostram o aviso do 199; levantar os contatos deles vai para `docs/pendencias.md`.

## 4. Bot do Telegram

**Rótulos dos botões.** O Worker não guarda estado e reconhece o botão pelo texto, então **todo rótulo de botão é único no `bot.json` inteiro**:
- os 27 nomes de município;
- o `textos.opcao_todos` global, "Todos", que não muda;
- os rótulos dos grupos, "Região de Rio do Sul" e "Região de Ituporanga";
- o `opcao_todos` de cada grupo, "Todos da Região de Rio do Sul" e "Todos da Região de Ituporanga";
- o `textos.opcao_voltar`, "Voltar".

Um teste confere que todos são diferentes entre si, comparando com o mesmo `normalizarNome` que o Worker usa.

**Contrato (`bot.json`), só acréscimos opcionais**, escritos pelo backend em `app/exportacao/bot_json.py`:
- `grupos`: lista de `{nome, municipios: [ibge], opcao_todos, escolha, confirmacao}`, ordenada pelo código da microrregião (42011 e depois 42014). Os municípios de cada grupo seguem a ordem da configuração;
- `textos.opcao_voltar`;
- `textos.boas_vindas_grupos`: resposta ao `/start` sem município quando há grupos, algo como "Escolha a sua região ou toque em 'Todos'". O `textos.boas_vindas` atual continua igual, para o Worker antigo.

**Worker (`bot-worker/src`):**
- **Sem `grupos` no `bot.json`:** tudo funciona como hoje.
- **Com `grupos`:**
  - **`/start` sem município:** responde `boas_vindas_grupos` e o teclado de grupos (um botão por grupo, mais "Todos").
  - **`/start` com município sugerido:** usa o `boas_vindas_sugerido` atual, que cita o nome e "Todos". O teclado traz na primeira linha o botão do município sugerido, depois os grupos e "Todos". O texto continua verdadeiro sem ser alterado.
  - **Botão de um grupo:** responde com a mensagem `escolha` e um teclado com os municípios do grupo em duas colunas, mais `opcao_todos` do grupo e "Voltar".
  - **Botão de um município:** inscreve como hoje.
  - **"Todos da Região…":** inscreve nos municípios do grupo e responde `confirmacao`.
  - **"Todos":** como hoje, inscreve nos 27.
  - **"Voltar"** e **`opcao_desconhecida`:** mostram o teclado de grupos.
- **Texto digitado:** a comparação com nomes e rótulos passa a usar `normalizarNome`, que já existe, nos dois casos (com e sem grupos). "blumenau", "ibirama" e "IBIRAMA" funcionam.
- **`/status` com 27 municípios:**
  - **Tamanho medido:** cerca de 3.818 a 4.115 caracteres de HTML bruto. Depois que o Telegram processa as marcações fica abaixo de 4.096, mas com pouca folga.
  - **Divisão por segurança:** uma função pura divide pelo comprimento do HTML bruto (estimativa conservadora). Os cortes são sempre entre blocos inteiros; o cabeçalho fica na primeira parte e o rodapé na última. Um bloco sozinho maior que o limite é tratado como erro de programação.
  - **Envio:** as partes saem em ordem.

**Bot local em Python (`app/bot/bot.py`, sem Worker):**
- continua com um botão por município, sem grupos (anotado no `backend/README.md`);
- `mensagens.texto_do_status` ganha a mesma divisão em partes, com teste, porque o limite vale para ele também.

## 5. Testes

Todos sem rede (pytest em `-W error` e vitest).

**Testes que mudam porque contam 6 municípios ou usam a configuração real:**
- `backend/tests/test_bot_json.py`:
  - `test_status_bate_com_texto_do_status_nas_63_combinacoes` percorre todas as combinações dos municípios configurados. Com 27 isso dá 2^27 − 1, cerca de 134 milhões, e o CI nunca termina. O teste passa a usar uma lista fixa de 6 municípios da fixture, sem ler a configuração real;
  - o conjunto exato de chaves da raiz (agora com `grupos`) e as contagens.
- `backend/tests/test_config.py`: as contagens.
- `frontend/src/lib/mapa.test.ts`:
  - os limites do enquadramento (sul −27,66, oeste −50,35, leste −49,19);
  - a contagem de 27;
  - o primeiro da lista, agora Agrolândia.

**Testes novos:**
- **Backend:**
  - `gerar_municipios` com respostas fixas do IBGE e da malha: 27 códigos como texto de 7 dígitos, `microrregiao` em todos, os 6 atuais iguais ao arquivo de hoje, ordem normalizada, erro quando falta um código existente, aviso quando o nome muda, erro com microrregião vazia ou `MultiPolygon`;
  - o centroide fica dentro depois do arredondamento;
  - `Municipio` com e sem `microrregiao`;
  - `bot_json`: `grupos` na ordem certa, rótulos únicos, `opcao_voltar` e `boas_vindas_grupos`; a fixture `bot-worker/test/fixtures/bot.exemplo.json` é regenerada com `VIGIA_REGERAR_FIXTURES=1`;
  - `avisos`: `RetryAfter` seguido de entrega;
  - divisão do `/status` em Python.
- **Worker:**
  - teclado sem `grupos`, como hoje;
  - fluxos grupo → município, grupo → todos do grupo, "Todos", "Voltar", opção desconhecida, `/start` com sugerido sob grupos e texto digitado normalizado;
  - divisão do `/status` com 27 blocos: nenhuma parte acima de 4.096 e nenhum bloco cortado.
- **Frontend:**
  - classe do rótulo (selecionado, alerta e nenhum);
  - faixa mínimo–máximo com dados parciais;
  - aviso de histórico por município;
  - GeoJSON com no máximo 150 KB;
  - frases novas cobertas pelo teste de paridade entre `es.json` e `en.json`.
- **Navegador:** 320, 390 e 1366 px em PT, ES e EN, nas telas Monitoramento, Simulação, Estações e Dados, seguidos de uma revisão por subagente.

## 6. Documentação

**Textos que deixam de ser verdade e são corrigidos:**
- `README.md`: as cerca de 10 menções a "seis municípios" e ao "Vale Norte" (escopo, tabelas e bot), e uma linha nova sobre como quem já estava inscrito em "Todos" passa a receber os 27 (tocar em "Todos" de novo no bot);
- `backend/README.md`;
- os docstrings de `pipeline.py`, `open_meteo.py`, `inmet.py` e `gerar_estacoes.py`;
- o comentário do `gerar-geojson.mjs`;
- o `ensemble.md` §8 e §9;
- o `contratos-de-dados.md`.

**Pendências novas (`docs/pendencias.md`):**
- validar o limiar dos 27;
- contatos dos 21 novos;
- prazo total de coleta no pipeline;
- agrupar avisos por chat, se o volume incomodar.

## 7. Implantação e reversão

1. **PR único** a partir da `main`.
2. **Logo depois do merge,** disparar o pipeline à mão (`workflow_dispatch`).
   - **Por quê:** o Pages publica o mapa com 27 municípios no merge, mas o `indices.json` ainda traz 6 até a próxima execução, por até 6 horas.
   - **Nesse intervalo:** os 21 novos aparecem sem cor e o resumo mostra "X de 6".
3. **Até o deploy do Worker:** o Worker atual ignora `grupos` e mostra um teclado de 28 linhas (27 municípios e "Todos"). O Telegram não limita o tamanho desse tipo de teclado, então funciona, só fica longo.
4. **Deploy manual do Worker** (`npm run deploy`): ativa o fluxo em dois passos.
5. **Reversão:**
   - reverter primeiro o `municipios.json` e o GeoJSON, e só depois o Worker; o `bot.json` sem `grupos` já cai no comportamento de hoje;
   - as linhas do D1 e do `vigia.db` para os 21 não têm efeito: o `/status` e os avisos ignoram municípios fora do `bot.json`.

## Fora do escopo

- Limiar validado por município ou por região.
- Mais de um ponto de coleta por município.
- Reconstrução do histórico com dados ERA5.
- Agrupar avisos de uma execução numa só mensagem.
- Contatos dos 21 municípios novos.
- Grupos no bot local em Python.
- Migrar quem já estava inscrito em "Todos".
- Prazo total de coleta no pipeline.
