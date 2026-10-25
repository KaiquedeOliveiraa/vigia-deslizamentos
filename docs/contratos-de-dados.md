# Contratos de dados

Formato dos arquivos trocados entre o backend, o repositório e o frontend. Datas e horários seguem ISO 8601 com fuso; números usam ponto decimal no JSON (a vírgula é só de exibição).

## `backend/config/municipios.json`

Parâmetros de cada município, versionados no repositório. Incluir um município é acrescentar um item.

| Campo | Tipo | Descrição |
|---|---|---|
| `ibge` | string (7 dígitos) | Código IBGE; chave do município em todo o sistema |
| `nome` | string | Nome oficial (IBGE) |
| `limiar_mm` | número | Limiar crítico de 24 h. Enquanto não houver valor de fonte oficial: 100 (provisório da equipe, com base nos critérios da Defesa Civil de Blumenau; o hipotético do GeoRisk é 250) |
| `fonte_limiar` | string | Origem do limiar (ex.: "GeoRisk, limiar hipotético padrão") |
| `mv_h` | número | Meia-vida da água no solo, em horas. Padrão: 24 |
| `pontos` | lista de `{lat, lon}` | Pontos de cálculo; no mínimo o centroide do município |
| `microrregiao` | objeto, opcional | `{"codigo": 5 dígitos, "nome"}`: microrregião IBGE; agrupa o teclado do bot |

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
| `historico` | lista | Até 15 dias anteriores ao D0: `{dia_alvo, indice, classe}`, lidos da tabela `indices` (último cálculo de cada dia-alvo), do mais antigo para o mais recente; dia sem cálculo fica de fora (a tela mostra 7 por padrão). Sempre no `limiar_mm` atual: um cálculo gravado com outro limiar é convertido (`indice × limiar_gravado / limiar_mm`, classe recalculada) |
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

## `frontend/public/data/historico.json`

Histórico de um ano do índice de todos os municípios da configuração, publicado pelo pipeline antes do `indices.json`. Serialização compacta, sem indentação.

| Campo | Tipo | Descrição |
|---|---|---|
| `schema_version` | inteiro | Versão do formato (hoje 1) |
| `fonte` | texto | Origem dos dados: "Calculado pelo VIGIA a cada execução (índice publicado do dia)" |
| `municipios` | objeto | Código IBGE → item abaixo; município sem nenhum dia fica de fora; sem nenhum município é `{}` (válido) |

**Item de `municipios`**

| Campo | Tipo | Descrição |
|---|---|---|
| `inicio` | data (UTC) | Primeiro dia-alvo com dado |
| `indices` | lista | `indices[i]` é o índice do dia-alvo `inicio + i`, com 4 casas decimais; `null` é dia sem dado; a lista não termina em `null` |

Vem de `banco.historico(..., dias=365)`: último cálculo de cada dia-alvo, no `limiar_mm` atual, D0 fora. Entram todos os municípios de `municipios.json`, inclusive os que falharam na execução.

**Regras de leitura no site**

- Arquivo inválido (`schema_version` desconhecido, campo faltando, `inicio` inválido, item que não seja número finito ou `null`): falha de carregamento do arquivo inteiro, nunca dados parciais.
- A classe não vai no arquivo: o site a calcula pelo índice.
- Sem data de geração, de propósito: o conteúdo só muda quando muda um dia, e a publicação é pulada se nada mudou.

## `frontend/public/data/historico_reconstruido.json`

Índice do último ano **reconstruído** com chuva de reanálise, para os dias anteriores ao primeiro cálculo real (15/10/2026). Gerado uma vez e versionado; não é publicado pelo pipeline. Mesmo formato do `historico.json` (serialização compacta, `schema_version` 1, sem data de geração), com dois campos a mais em cada município:

| Campo | Tipo | Descrição |
|---|---|---|
| `limiar_mm` | número | Limiar do município usado na reconstrução |
| `mv_h` | número | Meia-vida da chuva (h) usada na reconstrução |

Um teste falha se `limiar_mm`/`mv_h` divergirem de `config/municipios.json`: trocar o limiar exige regerar o arquivo (evita salto falso em 15/10).

**O que a reconstrução é.** O índice publicado é a média ponderada de várias rodadas de **previsão** para o dia-alvo. O reconstruído usa uma única série de chuva de **reanálise** (ERA5, grade de ~31 km, Open-Meteo arquivo histórico) no lugar da previsão: é uma estimativa retroativa, sem ensemble e não validada. A reanálise suaviza chuvas intensas e localizadas, então **tende a subestimar picos**, justamente os dias de alerta. Não é o que o sistema publicou na época nem dado oficial. Dias de alerta podem não aparecer.

**Como regerar** (precisa de rede, ~25 s, uma única requisição sem retentativa), a partir de `backend/`:

```
python -m scripts.gerar_historico_reconstruido [--fim 2026-10-14] [--dias 365]
```

O período vai de `--fim − (dias − 1)` até `--fim`. O índice do município em cada dia é o maior entre os seus pontos; hora ausente em um ponto tira o ponto daquele dia, e dia sem nenhum ponto completo vira `null` (nunca zero). O script falha sem gravar se a resposta não trouxer um item por ponto, se algum município ficar sem nenhum dia ou se mais de 5% dos dias de algum município forem `null`.

## `frontend/public/data/ocorrencias.json`

Histórico de ocorrências, gerado por `backend/scripts/gerar_ocorrencias.py` a partir do Atlas Digital de Desastres (1991–2025), só com eventos ligados a chuva, e versionado. A raiz é uma lista de objetos:

| Campo | Tipo | Descrição |
|---|---|---|
| `ibge` | string | Município |
| `data` | data | Data da ocorrência |
| `tipo` | string | "Movimento de massa", "Enxurrada", "Inundação", "Alagamento" ou "Chuva intensa" |
| `descricao` | string | Resumo dos danos, em português |
| `fonte` | string | Origem do registro |

## `frontend/public/data/setores_risco.geojson`

Gerado por `backend/scripts/gerar_setores_risco.py` a partir do serviço público do SGB. Só setores de movimento de massa. Textos do SGB em português.

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

| Campo | Código | Significado |
|---|---|---|
| `tipo` | `deslizamento` | Deslizamento |
| `tipo` | `rastejo` | Rastejo |
| `tipo` | `corrida_massa` | Corrida de massa |
| `tipo` | `queda` | Queda, tombamento ou rolamento |
| `grau` | `alto` | Risco geológico alto |
| `grau` | `muito_alto` | Risco geológico muito alto |

## `frontend/public/data/estacoes.json`

Estações automáticas do INMET na região, geradas uma vez por script (`backend/scripts/gerar_estacoes.py`) e versionadas. A raiz é uma lista de objetos:

| Campo | Tipo | Descrição |
|---|---|---|
| `codigo` | string | Código da estação no INMET |
| `nome` | string | Nome da estação |
| `ibge_referencia` | string | Município de **referência**: o mais próximo da estação dentro do raio de corte — **não** o município onde a estação fica |
| `distancia_km` | número | Distância entre a estação e o centroide desse município |
| `lat`, `lon` | número | Coordenadas em graus decimais |

**Por que `ibge_referencia` e não `ibge`.** Só duas estações do INMET ficam dentro dos 27 municípios (A863 Ituporanga e A861 Rio do Campo); as outras ficam a dezenas de km do município mais próximo, e a resposta do INMET não traz código IBGE nenhum, só nome livre e coordenadas. A associação é por proximidade do centroide. O campo tem nome próprio para não significar, aqui, algo diferente do que `ibge` significa em `indices.json` e em `municipios.json` — e `distancia_km` existe para que a distância real não possa ficar escondida.

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

## `bot.json`

Textos prontos do bot, gerados pelo backend (`app/exportacao/bot_json.py`) a cada execução com algum município calculado e lidos pelo Cloudflare Worker em `https://raw.githubusercontent.com/vigia-defesa-civil/vigia-deslizamentos/estado/bot.json`. O Worker não escreve texto do domínio: só repassa estes. Todos os textos são HTML do Telegram (`parse_mode: "HTML"`). Um `schema_version` desconhecido faz o Worker responder que o bot está indisponível.

| Campo | Conteúdo |
|---|---|
| `schema_version` | `1` |
| `gerado_em` | `"YYYY-MM-DDTHH:MM:SSZ"` |
| `municipios` | `[{"ibge", "nome"}]` na ordem da configuração |
| `grupos` | opcional: `[{nome, municipios: [ibge], opcao_todos, escolha, confirmacao}]` por microrregião, na ordem do código. Sem ele, o Worker mostra um botão por município |
| `textos.opcao_todos` | Rótulo da opção que inscreve em todos os municípios |
| `textos.boas_vindas` | Resposta ao `/start` sem município |
| `textos.boas_vindas_sugerido` | `{ibge: texto}`: `/start` já com um município sugerido |
| `textos.inscricao_confirmada` | `{ibge: texto}`: confirmação de inscrição em um município |
| `textos.inscricao_confirmada_todos` | Confirmação de inscrição em todos, na ordem da configuração |
| `textos.opcao_desconhecida` | Resposta a uma opção que não existe |
| `textos.inscricoes_apagadas` | Resposta ao `/parar` |
| `textos.opcao_voltar` | opcional: botão que volta às regiões |
| `textos.boas_vindas_grupos` | opcional: /start sem município quando há grupos |
| `status.cabecalho` | Início do `/status` |
| `status.blocos` | `{ibge: bloco}`: situação atual de cada município |
| `status.separador` | Entre blocos |
| `status.rodape` | Fim do `/status`, com o link do site |
| `status.sem_inscricao` | `/status` de quem não tem inscrição |
| `simulacao` | `null`, ou, com `VIGIA_SIMULACAO=1`, `{mensagens: {ibge: [...]}, fim, municipio_invalido, pausa_s}` para o `/simular` |

O `/status` é montado como `cabecalho + separador.join(blocos dos municípios inscritos) + rodape`.

Todo rótulo de botão (municípios, "Todos", grupos, "Todos da Região…", "Voltar") é único no arquivo: o Worker reconhece o botão pelo texto.

## Branch `estado`

Branch órfã (sem histórico em comum com a `main`) onde o pipeline guarda o que precisa sobreviver entre execuções do Actions:

| Arquivo | Conteúdo |
|---|---|
| `vigia.db` | Banco SQLite com `indices` e `notificacoes`, depois de um checkpoint do WAL (`scripts/preparar_estado.py`) |
| `bot.json` | O arquivo descrito acima |

Só o pipeline escreve nela, com o `GITHUB_TOKEN` do workflow, em um commit por execução quando algo mudou. O workflow a restaura no início e a cria se ainda não existir. Os inscritos não ficam aqui: estão no D1 do Worker.

## Publicação

- Caminhos: `frontend/public/data/historico.json` (publicado primeiro) e `frontend/public/data/indices.json`, no branch `main`.
- Token: o secret `TOKEN_DADOS`, um PAT *fine-grained* (`vigia_publicacao`) só deste repositório, com *Contents: Read and write* e data de expiração registrada.
- Falha no commit: o erro é registrado e o pipeline continua; os avisos do bot não dependem da publicação.
- Nenhum município calculado: a execução não publica; o `indices.json` anterior permanece e o aviso de dados desatualizados (12 h) cobre o caso.
- Pulo por sha: se o sha do arquivo no repositório for igual ao do novo conteúdo, não há commit. O `indices.json` sempre muda (`gerado_em`); o `historico.json` só muda quando vira o dia, o que dá um commit extra por dia (e um deploy).
- Falha ou exceção na publicação do `historico.json` é registrada e não impede o `indices.json` nem os avisos.
