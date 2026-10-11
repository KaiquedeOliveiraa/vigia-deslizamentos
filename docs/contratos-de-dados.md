# Contratos de dados

Formato dos arquivos trocados entre o backend, o repositório e o frontend. Datas e horários seguem ISO 8601 com fuso; números usam ponto decimal no JSON (a vírgula é só de exibição).

## `backend/config/municipios.json`

Parâmetros de cada município, versionados no repositório. Incluir um município é acrescentar um item.

| Campo | Tipo | Descrição |
|---|---|---|
| `ibge` | string (7 dígitos) | Código IBGE; chave do município em todo o sistema |
| `nome` | string | Nome oficial (IBGE) |
| `limiar_mm` | número | Limiar crítico de 24 h. Enquanto não houver valor de fonte oficial: 150 (provisório da equipe; o hipotético do GeoRisk é 250) |
| `fonte_limiar` | string | Origem do limiar (ex.: "GeoRisk, limiar hipotético padrão") |
| `mv_h` | número | Meia-vida da água no solo, em horas. Padrão: 24 |
| `pontos` | lista de `{lat, lon}` | Pontos de cálculo; no mínimo o centroide do município |

## `frontend/public/data/indices.json`

Gerado pelo Exportador a cada execução do pipeline e publicado por commit automático no repositório (o commit dispara o deploy do site). O site só lê este arquivo.

**Raiz**

| Campo | Tipo | Descrição |
|---|---|---|
| `schema_version` | inteiro | Versão deste contrato; começa em 1 |
| `gerado_em` | data-hora | Fim da execução que gerou o arquivo |
| `dia_alvo_d0` | data (UTC) | Dia-alvo corrente (D0) |
| `municipios_sem_dados` | lista de `ibge` | Municípios que falharam nesta execução |
| `municipios` | lista | Um item por município com dados |

**Item de `municipios`**

| Campo | Tipo | Descrição |
|---|---|---|
| `ibge`, `nome` | string | Como em `municipios.json` |
| `limiar_mm`, `fonte_limiar`, `mv_h` | — | Parâmetros usados no cálculo |
| `dias` | lista (D0–D3) | Resultado por dia-alvo (ver abaixo) |
| `historico` | lista | Até 15 dias anteriores ao D0: `{dia_alvo, indice, classe}`, lidos da tabela `indices` (último cálculo de cada dia-alvo), do mais antigo para o mais recente; dia sem cálculo fica de fora (a tela mostra 7 por padrão) |
| `chuva_acum_mm` | objeto | `{"24h", "48h", "72h", "96h"}`: chuva acumulada até a última hora cheia da execução, calculada da série horária da própria execução, no ponto do município com o maior valor |

**Item de `dias`**

| Campo | Tipo | Descrição |
|---|---|---|
| `dia_alvo` | data (UTC) | Dia-alvo |
| `d` | inteiro 0–3 | Distância em dias do D0 |
| `indice` | número | Índice de risco, sem arredondamento |
| `classe` | inteiro 1–7 | 1 extremamente baixo … 7 extremamente alto |
| `efr_mm` | número | Chuva efetiva antecedente: média ponderada, entre os membros, do valor do ponto que deu o maior subíndice em cada membro |
| `rtotal_mm` | número | Chuva prevista para o dia-alvo, agregada da mesma forma que `efr_mm` |
| `n_membros` | inteiro | Quantidade de subíndices (rodadas × modelos) usados |
| `prob` | objeto | `{pontuais, esparsos, generalizados}`, frações de 0 a 1 |

**Agregação**

Para cada membro (rodada × modelo), calcula-se o subíndice em cada ponto do município e fica o **maior**. O índice do município é a média ponderada desses máximos. O EfR é calculado por membro, porque as horas previstas de D1–D3 vêm do modelo daquele membro.

**Regras de leitura no site**

- `agora − gerado_em` maior que 12 horas: o site mostra o aviso de dados desatualizados.
- Município em `municipios_sem_dados`: aparece como "sem dados", sem cor de classe.
- `schema_version` desconhecido: o site mostra erro de carregamento em vez de dados parciais.

## `frontend/public/data/ocorrencias.json`

Histórico de ocorrências, levantado manualmente (Defesa Civil e S2iD) e versionado. A raiz é uma lista de objetos:

| Campo | Tipo | Descrição |
|---|---|---|
| `ibge` | string | Município |
| `data` | data | Data da ocorrência |
| `tipo` | string | Ex.: "deslizamento", "decreto de emergência" |
| `descricao` | string | Resumo curto |
| `fonte` | string | Origem do registro |

## `frontend/public/data/estacoes.json`

Estações automáticas do INMET na região, geradas uma vez por script (`backend/scripts/gerar_estacoes.py`) e versionadas. A raiz é uma lista de objetos:

| Campo | Tipo | Descrição |
|---|---|---|
| `codigo` | string | Código da estação no INMET |
| `nome` | string | Nome da estação |
| `ibge_referencia` | string | Município de **referência**: o mais próximo da estação dentro do raio de corte — **não** o município onde a estação fica |
| `distancia_km` | número | Distância entre a estação e o centroide desse município |
| `lat`, `lon` | número | Coordenadas em graus decimais |

**Por que `ibge_referencia` e não `ibge`.** Nenhuma estação automática do INMET fica dentro dos seis municípios: a mais próxima operante está a ~30 km, e a resposta do INMET não traz código IBGE nenhum, só nome livre e coordenadas. A associação é por proximidade do centroide. O campo tem nome próprio para não significar, aqui, algo diferente do que `ibge` significa em `indices.json` e em `municipios.json` — e `distancia_km` existe para que a distância real não possa ficar escondida.

**Regra de leitura no site:** a estação é regional, então o texto não pode afirmar que ela fica no município. Exibir a distância junto do nome (ex.: "ITAJAI, a 76 km de Ibirama") e usar `distancia_km` para filtrar o que vale mostrar. Essa é também a razão pela qual o raio de corte do script é generoso (100 km por padrão): o arquivo entrega o dado e a tela decide.

## `frontend/public/data/contatos.json`

Contatos da Defesa Civil de cada município, levantados com as prefeituras e versionados. O site só exibe os itens com `verificado: true`. A raiz é uma lista de objetos:

| Campo | Tipo | Descrição |
|---|---|---|
| `ibge` | string | Município |
| `nome` | string | Nome do município |
| `verificado` | booleano | Se o contato foi confirmado com a prefeitura |
| `responsavel` | string ou nulo | Coordenador(a) municipal de Defesa Civil |
| `telefone` | string ou nulo | Telefone de exibição, ex.: "(47) 98838-5645" |
| `email` | string ou nulo | E-mail |
| `endereco` | string ou nulo | Endereço completo, usado no "Como chegar" |
| `site` | string ou nulo | Site da prefeitura, exibido quando não há telefone |

## Publicação

- Caminho: `frontend/public/data/indices.json`, no branch `main`.
- Token: *fine-grained*, com permissão só de `contents: write` neste repositório e data de expiração registrada.
- Falha no commit: o erro é registrado e o pipeline continua; os avisos do bot não dependem da publicação.
- Nenhum município calculado: a execução não publica; o `indices.json` anterior permanece e o aviso de dados desatualizados (12 h) cobre o caso.
