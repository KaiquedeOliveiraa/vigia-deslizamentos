# Decisão — fontes, convenções e pesos do ensemble (Tarefa 0)

> Spike de pesquisa. Nenhuma linha de código de produção sai daqui. Esta tabela
> de pesos é **fixa, não calibrada e não validada pela equipe** — ela fecha a
> lacuna "modelos e pesos a definir" apenas o suficiente para destravar as
> Tarefas 5, 6 e 11, e deve ser revisada pela equipe antes de ir para produção.
> O README já assume essa limitação em "Simplificações assumidas pelo VIGIA" e
> em "Limitações conhecidas": sem base de ocorrências com cobertura suficiente,
> não há como reproduzir a calibração por matriz de confusão do GeoRisk.

Toda afirmação factual abaixo foi confirmada por uma chamada real às APIs
(não só pela documentação). As respostas brutas usadas como evidência estão em
`.superpowers/sdd/01-backend/evidencia-tarefa-0/` (pasta de trabalho, ignorada
pelo git, não versionada).

## 1. Endpoints escolhidos

### 1.1 Open-Meteo — chuva observada/antecedente

Endpoint padrão de previsão, sem parâmetro `models` (usa o blend automático
"best-match" da Open-Meteo, que mistura observação e modelo recente):

```
GET https://api.open-meteo.com/v1/forecast
    ?latitude=-27.05&longitude=-49.52
    &hourly=precipitation
    &timezone=UTC
    &past_days=7
    &forecast_days=1
```

- `past_days=7`: janela de 168 h anteriores (parâmetro aceita 0–92, confirmado
  na documentação oficial).
- `timezone=UTC`: evita qualquer conversão de fuso; todos os rótulos saem em
  UTC "ingênuo" (sem offset), que tratamos como UTC por convenção do projeto.
- Esse valor alimenta `DadosMunicipio.antecedente` (Tarefa 5): é uma série por
  ponto, uma chamada por ponto de cálculo.

Evidência: `evidencia-tarefa-0/forecast_hourly_vs_daily.json`.

### 1.2 Open-Meteo — rodadas anteriores dos modelos (*time-lagged ensemble*)

```
GET https://previous-runs-api.open-meteo.com/v1/forecast
    ?latitude=-27.05&longitude=-49.52
    &hourly=precipitation,precipitation_previous_day1
    &models=gfs_global
    &timezone=UTC
    &forecast_days=4
```

- `models`: um de `gfs_global`, `ecmwf_ifs025`, `icon_global` (ver §3).
- `precipitation`: rodada mais recente disponível no momento da chamada
  ("rodada atual", atraso baixo).
- `precipitation_previous_day1`: mesma série, mas usando a rodada que estava
  ativa 24 h antes de cada instante de validade (rodada mais antiga).
- `forecast_days=4`: cobre D0–D3.
- Uma chamada por (ponto × modelo) já traz as duas rodadas (atual e -24 h) de
  uma vez — não são duas chamadas.

Evidência: `evidencia-tarefa-0/previous_runs_gfs.json`,
`evidencia-tarefa-0/ecmwf_previous_runs_test.json`,
`evidencia-tarefa-0/icon_previous_runs_test.json`.

## 2. Convenção do rótulo horário da precipitação

> **Correção (rodada de revisão 1):** a versão anterior deste documento dizia
> que o rótulo marca o *início* da hora. Está **errado** — o rótulo marca o
> **fim** da hora (`backwards_sum`). A revisão independente mostrou que o
> teste usado para "confirmar" a versão anterior era circular (ver abaixo por
> quê), e a correção foi verificada por dois caminhos que não dependem desse
> teste: o código-fonte da Open-Meteo e um evento astronômico independente
> (nascer/pôr do sol).

**O rótulo `T` representa a chuva acumulada no intervalo `[T−1h, T)` — ou
seja, o rótulo marca o *fim* da hora.** Isso é consistente com o texto da
documentação ("sum of the preceding hour"), que a versão anterior deste
documento tinha lido ao contrário.

### Por que o teste anterior não decidia a direção (e por que isso importa)

O teste anterior comparava a soma dos 24 rótulos com data-texto `D`
(`D T00:00` a `D T23:00`) contra o campo `daily.precipitation_sum` de `D`, e
batia exatamente. Isso **não** prova que o rótulo `D T00:00` cobre fisicamente
o início do dia `D`: prova só que a Open-Meteo **agrupa esse conjunto de
rótulos sob o texto da data `D`** ao calcular o total diário — o que é
verdade qualquer que seja a direção física do intervalo que cada rótulo
representa. Um teste que mede o agrupamento textual não pode decidir uma
pergunta sobre a física do intervalo; ele bate "sim" nas duas hipóteses
dependendo de como a soma é reagrupada, e eu só testei um reagrupamento
alternativo (não o conjunto de rótulos correto para a hipótese errada), o que
mascarou o problema.

### Evidência que de fato decide a direção

**1. Código-fonte da Open-Meteo** (open-meteo/open-meteo no GitHub, branch
`main`), que processa e serve os dados:

- `Sources/App/Gfs/GfsVariable.swift`, linha 153:
  `case .precipitation, .showers, .snowfall_water_equivalent: return .init(..., interpolation: .backwards_sum, ...)`
- `Sources/App/Ecmwf/EcmwfVariable.swift`, linha 798:
  `case .precipitation, .showers, .snowfall_water_equivalent, .runoff: return .backwards_sum`

`backwards_sum` soma os minutos/horas anteriores ao rótulo, terminando nele.
Evidência salva (arquivos baixados diretamente do GitHub, não resumidos):
`evidencia-tarefa-0/github_gfs_variable.swift`,
`evidencia-tarefa-0/github_ecmwf_variable.swift`.

**2. Cruzamento com um evento físico independente — nascer e pôr do sol.**
Esse teste **pode falhar** de verdade (ao contrário do teste de agrupamento):
se o rótulo marcasse o início do intervalo, o primeiro valor de radiação
não-nulo apareceria na hora cujo rótulo é igual ao horário do nascer do sol;
se marca o fim, o primeiro valor não-nulo aparece uma hora **depois**.
Chamada: `hourly=shortwave_radiation`, `daily=sunrise,sunset`,
`timezone=UTC`, para -27,05/-49,52 em 2026-10-01 (nascer do sol: `08:57Z`,
calculado pela própria Open-Meteo a partir de posição solar, independente de
qualquer convenção de acumulação de chuva):

| Rótulo | Radiação (W/m²) |
|---|---|
| 2026-10-01T08:00 | 0,0 |
| 2026-10-01T09:00 | 0,0 |
| 2026-10-01T10:00 | 10,0 |
| 2026-10-01T11:00 | 39,0 |

O nascer do sol (08:57Z) cai dentro do intervalo `[08:00,09:00)`. Com rótulo
= fim do intervalo, esse intervalo é rotulado `09:00` — e é exatamente onde
o valor ainda aparece como `0,0` (só 3 min de luz rasante, abaixo do limiar
de medição), virando `10,0` no rótulo seguinte (`10:00`, que cobre
`[09:00,10:00)`, a primeira hora inteira após o nascer do sol). Com rótulo =
início do intervalo, o rótulo `09:00` cobriria `[09:00,10:00)` — já a
primeira hora inteira de sol — e deveria ser o primeiro a subir, o que não
acontece. O mesmo padrão se repete no pôr do sol (21:18Z): rótulo `21:00`
ainda alto (59,0, intervalo `[20:00,21:00)`, todo antes do pôr do sol),
rótulo `22:00` caindo para quase zero (1,0, intervalo `[21:00,22:00)`,
a maior parte já escura), rótulo `23:00` em `0,0`. Evidência:
`evidencia-tarefa-0/radiation_sunrise_test.json`.

Os dois caminhos (código-fonte e evento astronômico) apontam na mesma
direção e não dependem um do outro nem do teste de agrupamento original, que
fica mantido acima só como registro do erro, não como evidência da convenção.

### Quais 169 rótulos formam a janela do EfR de um dia-alvo D

O brief da Tarefa 6 fixa o limite: "t=0 é a hora que **termina** na meia-noite
UTC de D". Com rótulo = fim do intervalo, a hora que termina em `D 00:00Z`
é, ela mesma, o rótulo `D T00:00Z`. Daí:

```
rotulo(t) = meia_noite_utc(D) − t horas,   para t = 0, 1, ..., 168
```

- `t=0` → rótulo `D T00:00Z` (peso 1, sem decaimento) — cobre fisicamente
  `[(D−1)T23:00Z, D T00:00Z)`.
- `t=168` → rótulo `(D−7)T00:00Z` (peso mínimo, `0,5^(168/24) = 0,5^7 ≈ 0,0078`).

Os 169 rótulos vão de `(D−7)T00:00Z` até `D T00:00Z`, inclusive, hora a hora.

**`rtotal` do dia-alvo (Tarefa 6):** soma dos 24 rótulos `D T01:00Z` até
`(D+1)T00:00Z` — cada um desses rótulos cobre uma hora cujo intervalo físico
está inteiramente dentro do dia civil `D` (`[D 00:00, D 01:00)` até
`[D 23:00, (D+1) 00:00)`).

**As duas janelas encaixam sem sobra nem buraco:** o EfR termina no rótulo
`D T00:00` (cobre até o instante físico `D 00:00`); o `Rtotal` começa no
rótulo `D T01:00` (cobre a partir do instante físico `D 00:00`). Nenhuma hora
física é contada duas vezes, nenhuma fica de fora.

**Atenção para quem implementar a Tarefa 6:** o `Rtotal` **não pode** ser
obtido do campo `daily.precipitation_sum` da API. Esse campo agrupa pelo
texto da data do rótulo (`D T00:00` a `D T23:00`), mas, como acabamos de
estabelecer, o rótulo `D T00:00` cobre fisicamente a última hora de `D−1`
(`[(D−1)23:00, D 00:00)`) — ou seja, o "dia" do campo diário está deslocado
uma hora para trás em relação ao dia civil UTC real. `Rtotal` tem de somar
os 24 rótulos corretos (`D T01:00` a `(D+1)T00:00`) a partir da série
horária, não usar o total diário pronto.

## 3. Modelos escolhidos

| Modelo | `models=` | Resolução | Cobertura confirmada | Atualização | Horizonte | Atraso de disponibilização (medido) |
|---|---|---|---|---|---|---|
| GFS (NCEP) | `gfs_global` | 0,11–0,13° (~13 km) | Global; testado em -27,05/-49,52 com retorno numérico válido | a cada 6 h (00/06/12/18 UTC) | 16 dias | **~5,6–5,8 h** |
| ECMWF IFS | `ecmwf_ifs025` | 9 km nativo / 0,25° de saída | Global; testado na mesma coordenada | a cada 6 h | 15 dias (horário até ~90 h, depois 3 h/3 h) | **~8,0 h** |
| ICON Global (DWD) | `icon_global` | 0,1° (~11 km) | Global — **testado empiricamente e confirmado para o Brasil**, apesar de a documentação textual da Open-Meteo não destacar a América do Sul como região prioritária | a cada 6 h | **~168 h (medido, ver abaixo)** | **~3,6 h** |

**ICON-EU e ICON-D2 foram descartados**: cobrem só Europa/Alemanha-Suíça-Áustria
(confirmado na documentação), não alcançam SC.

**Correção (rodada de revisão 1):** a versão anterior citava 180 h (7,5 dias)
de horizonte para o ICON Global a partir do texto da documentação, sem
chamada real que confirmasse — e a página de documentação do ICON nem chega
a mencionar explicitamente um horizonte separado para a variante "Global"
(ela mistura números do ICON-EU/D2). Medido agora com `forecast_days=16`
(`models=icon_global`, mesma coordenada): o último rótulo com valor
não-nulo é `2026-10-08T00:00`, índice 168 da série (hora 168 a partir do
início da chamada, em 2026-10-01T00:00) — ou seja, horizonte real de
**~168 h**, não 180 h. A partir do índice 169 todos os valores vêm `None`.
Evidência: `evidencia-tarefa-0/icon_global_horizon_check.json`.

**Cobertura do horizonte (atraso máximo de 36 h → fim do D3):** o pior caso é
uma rodada com 36 h de atraso, chamada no instante inicial de D0, que precisa
alcançar o fim de D3 — até 36 h (atraso) + 96 h (D0 a fim de D3) = **132 h**
de horizonte a partir da inicialização da rodada. Os três modelos (384 h, 360 h
e ~168 h) cobrem essa exigência; o ICON, o mais curto, sobra **~36 h** de
margem (não ~50 h, como a versão anterior dizia).

**Limitação observada:** para o ECMWF, a partir de ~90 h de horizonte a API
devolve valores repetidos em blocos de 3 horas (evidência:
`evidencia-tarefa-0/ecmwf_horizon_check.json`, índices 94–99: `2,6 / 2,6 / 2,6`
depois `0,3 / 0,3 / 0,3`), confirmando a degradação de resolução de 1 h para
3 h documentada oficialmente. Isso só afeta as últimas horas de D3 quando a
rodada usada é antiga; o `rtotal` desse dia fica um pouco menos granular, mas
o valor ainda existe e a soma de 24 h continua calculável.

Evidência: `evidencia-tarefa-0/icon_global_test.json`,
`evidencia-tarefa-0/meta_ecmwf_ifs025.json`,
`evidencia-tarefa-0/meta_ncep_gfs013.json`,
`evidencia-tarefa-0/meta_ncep_gfs025.json`,
`evidencia-tarefa-0/meta_dwd_icon.json`,
`evidencia-tarefa-0/ecmwf_horizon_check.json`,
`evidencia-tarefa-0/icon_global_horizon_check.json`.

## 4. Granularidade real do *time-lagged ensemble* — contradição com o brief

O brief previa rodadas a cada 6 h de atraso (0, 6, 12, 18, 24, 30, 36 h). A
**Previous Runs API só oferece offsets de 24 em 24 horas**
(`precipitation_previous_day1`, `..._day2`, ... `..._day7` — não existe
`_previous_hour6` nem equivalente). Confirmado de duas formas independentes:

1. Buscando no HTML bruto da página de documentação por padrões de nome de
   variável: só aparecem sufixos `_previous_day0` a `_previous_day7`
   (`evidencia-tarefa-0/previous_runs_docs_raw.html`).
2. Chamando a API real com `precipitation,precipitation_previous_day1,
   precipitation_previous_day2,precipitation_previous_day3` — os quatro
   campos vêm preenchidos e diferem entre si (não são duplicatas), mas não há
   parâmetro para pedir um offset de 6, 12 ou 18 h
   (`evidencia-tarefa-0/previous_runs_gfs.json`,
   `evidencia-tarefa-0/ecmwf_previous_runs_test.json`).

**Decisão:** como os modelos rodam a cada 6 h, `previous_day1` cai sempre no
mesmo horário sinótico que a rodada "atual" (ex.: se a mais recente é 12 UTC,
`previous_day1` é o 12 UTC do dia anterior) — ou seja, com esta API só são
alcançáveis **dois atrasos por modelo: ≈0 h (rodada atual) e ≈24 h
(`previous_day1`)**. `previous_day2` (≈48 h) já ultrapassa o corte de 36 h do
README e não é usado. Isso é consistente com o que o próprio brief autoriza
("ajustar a tabela de pesos ao que existir").

Em vez de reduzir a tabela de pesos a só dois pontos (o que quebraria o
contrato de `peso(rodada, agora_utc)` da Tarefa 6, que precisa funcionar para
qualquer `datetime` de rodada), a função de peso abaixo é **contínua em função
do atraso** — ela cobre os sete marcos pedidos no brief (0…36 h, de 6 em 6) e
qualquer valor intermediário, mas, na prática, o coletor da Tarefa 5 só
alimenta os atrasos ≈0 h e ≈24 h (ver §5). Os marcos intermediários (6, 12, 18,
30 h) ficam definidos para o caso de uma fonte mais granular ser incorporada
no futuro (ex.: cache das execuções do próprio pipeline a cada 6 h — hoje fora
de escopo, porque o projeto não persiste séries horárias entre execuções).

## 5. Tabela de pesos fixos

**Fórmula** (implementável em `peso(rodada: datetime, agora_utc: datetime) -> float`):

```
atraso_h = (agora_utc - rodada).total_seconds() / 3600

peso_recencia = max(0, 1 - atraso_h / 36)      # 0 em atraso_h >= 36; 1 em atraso_h = 0

tipo = "principal"   se rodada.hour (UTC) in {0, 12}
tipo = "secundaria"  se rodada.hour (UTC) in {6, 18}

multiplicador_tipo = 1,0  se tipo == "principal"
multiplicador_tipo = 0,8  se tipo == "secundaria"

peso = peso_recencia * multiplicador_tipo
```

`rodada.hour` é sempre um dos quatro horários sinóticos (0/6/12/18 UTC) pelos
três modelos escolhidos — confirmado nos metadados (§3: todos atualizam a
cada 6 h, nos mesmos horários). O decaimento é linear (não é o mesmo
decaimento exponencial do EfR — este é um fator de confiança do ensemble, não
de água no solo; não há exigência metodológica de ser exponencial, e linear é
a forma mais simples e auditável de zerar exatamente em 36 h).

Essa divisão em dois fatores (recência × tipo de rodada, sem fator por
modelo) corresponde à simplificação já declarada no README ("Pesos do
ensemble: pesos fixos por recência e horário de assimilação, sem
calibração" — a "destreza histórica de cada modelo" do GeoRisk, recalibrada
por matriz de confusão, fica de fora por falta de base de ocorrências).

**Tabela de referência** (valores calculados pela fórmula acima, para os sete
marcos pedidos no brief):

| Atraso da rodada | Peso — rodada 00/12 UTC (`principal`) | Peso — rodada 06/18 UTC (`secundaria`) | Alcançável pelo coletor da Tarefa 5? |
|---|---|---|---|
| 0 h | 1,000 | 0,800 | **Sim** (rodada atual) |
| 6 h | 0,833 | 0,667 | Não (ver §4) |
| 12 h | 0,667 | 0,533 | Não |
| 18 h | 0,500 | 0,400 | Não |
| 24 h | 0,333 | 0,267 | **Sim** (`previous_day1`) |
| 30 h | 0,167 | 0,133 | Não |
| 36 h | 0,000 | 0,000 | Não (atraso exatamente no corte) |
| > 36 h | — (membro descartado) | — (membro descartado) | — |

**Regra explícita para a Tarefa 6, sem ambiguidade:** todo membro cujo
`peso(rodada, agora_utc)` dê `0` (atraso ≥ 36 h, inclusive exatamente 36 h)
é **removido do cálculo por completo** — não entra no somatório ponderado do
numerador (onde não faria diferença, por ter peso 0) **nem na contagem de
`n_membros`** usada para comparar com `n_min`. Em outras palavras,
`n_membros` conta só membros com peso `> 0`; um membro de peso 0 é
equivalente a um membro ausente, não a um membro presente que não influencia
a média. Isso evita que uma rodada já irrelevante (atraso ≥ 36 h) infle
artificialmente `n_membros` e esconda que, na prática, poucos membros úteis
contribuíram para aquele dia-alvo.

## 6. `n_min`

Com os três modelos escolhidos e os dois atrasos realmente alcançáveis por
modelo (0 h e 24 h — §4), o número máximo de membros por dia-alvo é
`3 modelos × 2 rodadas = 6`.

**`n_min = 3`** (metade do máximo). Raciocínio: tolera a perda completa de um
modelo inteiro (sobram 4 membros, ≥ 3) sem descartar o município, mas não
tolera a perda de dois dos três modelos ao mesmo tempo (sobrariam só 2,
< `n_min` → o dia-alvo cai em `municipios_sem_dados`). Isso evita publicar um
índice baseado só nas duas rodadas de um único modelo (o que amplificaria o
viés específico daquele modelo em vez de combinar fontes independentes) e
ainda assim é tolerante a uma falha transitória isolada de API. O valor vive
como constante de módulo em `app/calculo/agregacao.py`, não em configuração.

## 7. Horário de disponibilização e agendador

Medido via a API de metadados da Open-Meteo
(`https://api.open-meteo.com/data/<modelo>/static/meta.json`, campos
`last_run_initialisation_time` e `last_run_availability_time`):

| Modelo | Rodada medida | Inicialização | Disponível em | Atraso medido |
|---|---|---|---|---|
| ECMWF IFS 0,25° | 2026-09-30 12 UTC | 12:00:00 UTC | 19:59:41 UTC | 7,99 h |
| GFS 0,13° (ncep_gfs013) | 2026-09-30 18 UTC | 18:00:00 UTC | 23:33:07 UTC | 5,55 h |
| GFS 0,25° (ncep_gfs025) | 2026-09-30 18 UTC | 18:00:00 UTC | 23:45:22 UTC | 5,76 h |
| ICON Global (dwd_icon) | 2026-09-30 18 UTC | 18:00:00 UTC | 21:38:00 UTC | 3,63 h |

Evidência: `evidencia-tarefa-0/meta_ecmwf_ifs025.json`,
`evidencia-tarefa-0/meta_ncep_gfs013.json`,
`evidencia-tarefa-0/meta_ncep_gfs025.json`, `evidencia-tarefa-0/meta_dwd_icon.json`.

O gargalo é o ECMWF (~8 h). Com 1 h de margem de segurança, o pipeline deve
rodar **9 h depois de cada rodada sinótica**:

| Rodada (UTC) | Cron (UTC) | Cron (Brasília, UTC-3) |
|---|---|---|
| 00 | **09:00** | 06:00 |
| 06 | **15:00** | 12:00 |
| 12 | **21:00** | 18:00 |
| 18 | **03:00** (dia seguinte) | 00:00 |

Os quatro horários ficam 6 h entre si, como pede o README. A Tarefa 11 já
soma `misfire_grace_time=3600` (1 h) de folga adicional sobre esses horários.

## 8. INMET

- **Lista de estações automáticas** (sem token):
  `GET https://apitempo.inmet.gov.br/estacoes/T` → 200 OK, 672 estações,
  campos por estação: `CD_ESTACAO`, `DC_NOME`, `SG_ESTADO`, `VL_LATITUDE`,
  `VL_LONGITUDE`, `VL_ALTITUDE`, `CD_SITUACAO` ("Operante"/"Pane"),
  `TP_ESTACAO`, `DT_INICIO_OPERACAO`/`DT_FIM_OPERACAO`. Evidência:
  `evidencia-tarefa-0/inmet_estacoes_T.json`.
- **Nenhum campo identifica o município por código IBGE.** Só há
  `DC_NOME` (nome livre da estação, nem sempre igual ao nome do município) e
  coordenadas. **Estratégia (para a Tarefa 12):** associar pela estação
  `CD_SITUACAO == "Operante"` mais próxima do centróide do município por
  distância (haversine), dentro de um raio de corte — não por casamento de
  nome, porque os nomes das estações não batem com os seis municípios do
  projeto (ver limitação abaixo).
- **Chuva horária por estação — contradição com o brief/README:** o endpoint
  `GET https://apitempo.inmet.gov.br/estacao/{inicio}/{fim}/{codigo}`,
  citado por fontes de terceiros como não exigindo token, **devolveu 204 (sem
  conteúdo) em toda combinação testada** — datas de 2024, 2025 e 2026,
  estações válidas (A001, A861, A863) e até um código de estação inválido
  (mesmo comportamento, o que indica rota efetivamente desativada/sem dado, e
  não um problema de parâmetro). Investigando a rota alternativa
  `GET https://apitempo.inmet.gov.br/token/estacao/{inicio}/{fim}/{codigo}/{token}`,
  a API respondeu `200 OK` com o corpo `"CHAVE INVÁLIDA!"` — confirmando que
  **esta rota exige um token válido**, obtido por e-mail a
  `cadastro.act@inmet.gov.br` (achado cruzado com busca na web e validado
  pela resposta real da API). **Isso contradiz a suposição do brief/README de
  que a chuva horária do INMET não exige token.** Decisão: documentar a
  contradição e não forçar — a obtenção do token é um passo manual fora desta
  sessão; a Tarefa 12 depende de alguém da equipe solicitar esse token antes
  de implementar a comparação de chuva de 24 h. Sem o token, a Tarefa 12 pode
  ainda gerar `estacoes.json` (que não precisa de token), mas não pode
  implementar a comparação de chuva medida.
- **Fuso horário:** os campos de data/hora retornados por essa API são em
  UTC (confirmado por fontes de terceiros, já que não consegui obter uma
  resposta real com dados — ver limitações). Mesmo convertido, isso é
  consistente com o restante do sistema (tudo em UTC).
- Evidência: `evidencia-tarefa-0/inmet_dados_A001.json`,
  `inmet_dados_A861.json`, `inmet_dados_A861_ago.json`, `inmet_dados_A863.json`,
  `inmet_dados_A001_cookie.json`, `inmet_token_necessario.json`.

### Achado adicional: nenhuma estação fica dentro dos seis municípios

**Correção (rodada de revisão 1):** as distâncias da versão anterior vinham
de uma aproximação equiretangular ingênua (`hypot(Δlat, Δlon) × 111 km`), que
não corrige a longitude pelo cosseno da latitude — a ~27° de latitude sul
essa correção vale `cos(27°) ≈ 0,89`, e o erro acumulado chegava a ~10%.
Recalculado com haversine de verdade (`R=6371 km`), a partir do mesmo arquivo
`inmet_estacoes_T.json` e do mesmo ponto de referência (lat -26,8 / lon
-49,55):

| Estação | Situação | Distância (haversine) |
|---|---|---|
| A817 Indaial | **Pane** | 30,7 km |
| A861 Rio do Campo | Operante | 61,0 km |
| A862 Rio Negrinho | **Pane** | 61,4 km |
| A863 Ituporanga | Operante | 69,4 km |

A conclusão qualitativa não muda: a estação mais próxima (Indaial) está fora
de operação, e as duas mais próximas **operantes** ficam a ~61–69 km — mas
Rio do Campo (61,0 km) e Rio Negrinho (61,4 km, em pane) ficam praticamente
empatadas, o que a aproximação anterior não mostrava. Nenhuma das seis
estações cai dentro de Dona Emma, Ibirama, José Boiteux, Presidente Getúlio,
Vitor Meireles ou Witmarsum. Isso é compatível com o papel regional que o
README já atribui ao INMET ("comparação e validação... na região", não por
município), mas significa, na prática, que a condicional "quando houver
estação no município" da Tarefa 12 dificilmente será satisfeita de forma
literal — recomenda-se um raio de corte generoso (ex.: 80–100 km) ou aceitar
que a comparação fica desabilitada para os seis municípios até que a rede de
estações mude. Evidência: `evidencia-tarefa-0/inmet_estacoes_T.json` (mesmo
arquivo, filtrado por `SG_ESTADO == "SC"`, com haversine correto).

## 9. Limite de chamadas × volume previsto

Confirmado no HTML bruto da página de preços (`evidencia-tarefa-0/pricing_raw.html`):

| Limite | Valor |
|---|---|
| Por minuto | 600 chamadas |
| Por hora | 5.000 chamadas |
| Por dia | 10.000 chamadas |
| Por mês | 300.000 chamadas |

"Uma chamada HTTP = uma chamada de API", exceto quando a requisição pede mais
de 10 variáveis meteorológicas ou mais de 2 semanas de dados para um único
ponto — nenhum dos nossos pedidos faz isso (no máximo 2 variáveis,
`past_days=7`). Não há confirmação oficial de quantas chamadas conta uma
requisição com várias coordenadas na mesma URL (testado e funciona — devolve
uma lista de respostas —, mas o próprio texto da página diz que o
comportamento de cobrança para "múltiplas localizações simultâneas" é um
"recurso futuro", ou seja, **não documentado hoje**). Por isso, a conta abaixo
assume o cenário mais caro: **uma chamada por ponto** (sem agrupar
coordenadas).

**Volume por execução** = `pontos_total × (modelos + 1)`
(`+1` é a chamada de `antecedente`, que não depende de modelo).

Com 6 municípios e até 3 pontos cada (centróide + 2 adicionais — o contrato
de `municipios.json` exige só "no mínimo o centróide"; 3 é um teto
conservador para a extensão territorial destes municípios pequenos):

- `pontos_total` = 6 × 3 = 18
- chamadas/execução = 18 × (3 modelos + 1) = **72**
- chamadas/dia (4 execuções) = 72 × 4 = **288**
- chamadas/mês (30 dias) = 288 × 30 = **8.640**

Comparando com os limites: 288/dia ≪ 10.000/dia; 72 chamadas concentradas no
início de uma execução ≪ 5.000/hora e ≪ 600/min; 8.640/mês ≪ 300.000/mês.
**Mesmo no cenário pessimista de cobrança (1 chamada por ponto, sem
agrupamento), a folga é de mais de 30× em todos os limites.** Não há
necessidade de reduzir nenhum parâmetro (pontos, modelos ou execuções/dia)
para caber no plano gratuito, na escala atual do projeto (6 municípios). Se o
projeto crescer a dezenas de municípios ou dezenas de pontos por município, o
agrupamento de coordenadas numa única chamada (demonstrado em
`evidencia-tarefa-0/multi_coord_test.json`) é o parâmetro a usar para conter o
volume — mas isso não é necessário agora.

## 10. Limitações — o que não foi possível confirmar

- **Chuva horária do INMET**: não foi possível obter uma resposta real com
  dados, porque a rota correta exige um token que não está disponível nesta
  sessão (processo de solicitação por e-mail, fora do alcance desta tarefa).
  O fuso horário "UTC" e os nomes de campo (`DT_MEDICAO`, `HR_MEDICAO`,
  `CHUVA`) vêm de fontes de terceiros (buscas na web), não de uma chamada
  própria — ficam como suposição a confirmar na Tarefa 12, quando o token
  estiver disponível.
- **Cobrança de chamadas com múltiplas coordenadas**: testado e funcional,
  mas a própria Open-Meteo descreve o comportamento de cobrança para
  múltiplas localizações como não definido ainda ("recurso futuro"). A conta
  do item 9 assumiu o pior caso para não depender disso.
- **Atraso de disponibilização**: medido uma única vez (uma amostra por
  modelo, em 2026-09-30/10-01), não uma série histórica. Pode variar
  ligeiramente entre rodadas; os 9 h de margem sobre o pior caso medido (~8 h
  do ECMWF) devem absorver essa variação, mas não foi testado ao longo de
  vários dias.
- **Granularidade do atraso do ensemble**: confirmada como 24 h via a
  Previous Runs API pública. Não foi investigado se um plano pago ou uma
  fonte diferente (ex.: arquivo histórico de rodadas, download direto do
  NOMADS/ECMWF open-data) ofereceria 6 h — ficou fora do escopo deste spike
  por já haver uma solução funcional dentro do plano gratuito.
- **Associação estação↔IBGE**: a estratégia proposta (estação operante mais
  próxima por distância) não foi testada com os centróides reais dos
  municípios (que só existirão depois da Tarefa 1/do carregamento das malhas
  do IBGE); as distâncias do item 8 usam um ponto aproximado do centro da
  microrregião, informado no brief desta tarefa, não os centróides oficiais.
- **Pesos fixos (§5)**: são uma construção deste spike para destravar as
  Tarefas 5/6/11, não um resultado calibrado. Precisam de validação da equipe
  antes de produção, como o brief já exige.
