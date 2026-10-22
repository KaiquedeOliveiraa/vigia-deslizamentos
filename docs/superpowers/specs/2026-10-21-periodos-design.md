# Períodos na tela Dados: 7 dias, 30 dias e Personalizado

Parte 4 do roteiro. Branch `feat/periodos`, sobre `feat/areas-de-risco`. Revisão 2 (após revisão por subagentes: código/dados e desenho).

## Objetivo

A tela Dados deixa de oferecer 5 / 7 / 15 dias e passa a oferecer **7 dias** (padrão), **30 dias** e **Personalizado** (de uma data a outra, dentro do último ano). Quem usa: Defesa Civil e público olhando como o índice se comportou nas semanas ou meses anteriores — por exemplo, antes de uma ocorrência registrada em Áreas de risco.

**Sucesso:** escolher 30 dias ou um intervalo de até um ano mostra a evolução do índice sem buracos causados pela idade do sistema; o que foi reconstruído nunca se confunde com o que o sistema publicou e vem com a ressalva honesta do que é; se o histórico longo não carregar, a tela continua funcionando com o histórico do `indices.json`.

## Decisões (aprovadas)

- O banco só tem cálculos desde 15/10/2026. Os dias anteriores são **reconstruídos** com chuva de reanálise ERA5 (arquivo histórico do Open-Meteo), uma única vez, e marcados como reconstruídos na tela (opção b).
- Janela de **1 ano** (365 dias antes do D0, mais o D0).
- **Abordagem 1:** dois arquivos novos, lidos só pela tela Dados. O `indices.json` e as outras telas não mudam.

## O que a reconstrução é (e não é)

O índice publicado é a média ponderada de várias rodadas de **previsão** para o dia-alvo. O reconstruído usa uma única série de chuva de **reanálise** (ERA5, grade de ~31 km) no lugar da previsão — é uma estimativa retroativa, sem ensemble e não validada. A reanálise suaviza chuvas intensas e localizadas, então **tende a subestimar picos**, justamente os dias de alerta. Por isso:

- texto da nota na tela, sempre que o eixo tiver dia reconstruído: "Dias antes de {D}: estimativa reconstruída com chuva de reanálise (ERA5, Open-Meteo) e os parâmetros atuais, sem ensemble. A reanálise suaviza chuvas fortes e localizadas e tende a subestimar picos. Não é o que o sistema publicou na época nem dado oficial. Dias de alerta podem não aparecer." (`{D}` = primeiro dia real, 15/10/2026);
- a mesma ressalva, curta ("estimativa reconstruída, tende a subestimar picos"), na dica do dia em foco e na tabela para leitor de tela;
- a ressalva entra também em `docs/contratos-de-dados.md` e em "Limitações conhecidas" do README.

## 1. Dados

### Formato comum (`historico.json` e `historico_reconstruido.json`)

```json
{
  "schema_version": 1,
  "fonte": "texto curto da origem",
  "municipios": {
    "4214805": { "inicio": "2025-10-15", "indices": [0.4213, 0.3981, null, 0.5124] }
  }
}
```

- `indices[i]` é o índice do dia-alvo `inicio + i` (dia civil UTC, como no resto do contrato). `null` é dia sem dado.
- Índice com **4 casas decimais** (o mesmo arredondamento que `sentido`/`formatarIndice` assumem; evita mudar de classe na borda). A classe não vai no arquivo: o site calcula com `classe()` de `classes.ts` (faixas idênticas às de `classes.py`).
- Município sem nenhum dia não aparece. `inicio` é o primeiro dia com dado; a lista não termina em `null`.
- **Sem data de geração no arquivo:** o conteúdo só muda quando muda um dia, o que permite pular a publicação quando nada mudou (ver 2).
- Serialização compacta (`separators=(",", ":")`, sem indentação, `ensure_ascii=False`): ~50 KB por arquivo.
- `schema_version` desconhecido, campo faltando, `inicio` inválido ou item que não seja número finito/`null`: o site trata o arquivo inteiro como falha de carregamento (nunca dados parciais).
- No reconstruído, cada município leva também `limiar_mm` e `mv_h` usados (`{"inicio", "indices", "limiar_mm", "mv_h"}`); um teste falha se divergirem de `config/municipios.json` — trocar o limiar exige regerar o arquivo (evita salto falso em 15/10).

### `frontend/public/data/historico_reconstruido.json` (gerado uma vez, versionado)

- Script `backend/scripts/gerar_historico_reconstruido.py`, no padrão de `gerar_setores_risco.py`/`gerar_ocorrencias.py`: rede só no script, cálculo em funções puras testadas offline.
- Período dos dias-alvo: de `--fim` (padrão `2026-10-14`, véspera do primeiro cálculo real) para trás, `--dias` dias (padrão 365), ou seja `inicio = fim − (dias − 1)`.
- Uma requisição ao `https://archive-api.open-meteo.com/v1/archive` com todos os pontos de `config/municipios.json` (`latitude`/`longitude` separados por vírgula), `hourly=precipitation`, `models=era5`, `timezone=GMT`, `start_date = inicio − 7 dias`, **`end_date = fim + 1 dia`** (o Rtotal de `D` termina no rótulo `(D+1) T00:00Z`). Timeout de 90 s, **sem retentativa** (a chamada pesa ~700 chamadas ponderadas no limite por minuto do Open-Meteo). A resposta é uma lista, um item por ponto, na ordem pedida (verificado: 27 pontos, 200, ~6 MB, ~22 s).
- Índice do dia `D` para um ponto: `subindice(efr([chuva no rótulo r for r in rotulos_efr(D)], mv_h), sum(chuva no rótulo r for r in rotulos_rtotal(D)), limiar_mm)`, reaproveitando `app.calculo.agregacao.rotulos_efr`/`rotulos_rtotal` (já na ordem `t=0` primeiro que `efr` espera), `app.calculo.chuva_efetiva.efr` e `app.calculo.indice.subindice`. Índice do município: o **maior** entre os seus pontos. `limiar_mm` e `mv_h` atuais de cada município.
- Hora ausente (`null` ou rótulo faltando) em algum ponto: aquele ponto não conta naquele dia; se nenhum ponto do município tiver o dia completo, o dia vira `null`. Nunca vira zero.
- O script **falha sem gravar** se: a resposta não tiver um item por ponto; algum município ficar sem nenhum dia; mais de 5% dos dias de algum município forem `null`.
- `fonte`: `"Estimativa reconstruída pelo VIGIA com chuva horária de reanálise ERA5 (Open-Meteo, arquivo histórico), sem ensemble; tende a subestimar picos"`.

### `frontend/public/data/historico.json` (publicado pelo pipeline)

- Montado de `banco.historico(conexao, ibge, dia_alvo_d0, limiar_mm, dias=365)` para **todos os municípios de `config/municipios.json`** (com o `limiar_mm` da configuração), não só os calculados na execução — assim um município que falha numa execução não some do arquivo nem gera commit extra. Mesmas regras do `historico` atual (último cálculo de cada dia-alvo, conversão de limiar, D0 fora).
- `fonte`: `"Calculado pelo VIGIA a cada execução (índice publicado do dia)"`.
- Município sem histórico fica de fora. Nenhum município com histórico: `municipios: {}` (válido).
- O `historico` de 15 dias dentro do `indices.json` continua igual.

## 2. Backend

- `app/exportacao/exportar.py`: `montar_historico(historicos: dict[str, list[ItemHistorico]], fonte: str) -> dict` (formato acima, sem os campos extras do reconstruído; o script acrescenta `limiar_mm`/`mv_h`) e `serializar_compacto(dados) -> bytes`.
- `app/exportacao/publicar.py`: `publicar(conteudo, config, http, caminho=CAMINHO_NO_REPOSITORIO)`. `_url`, a mensagem de commit e os logs passam a usar `caminho`. Antes do `PUT`, se o `sha` lido for igual ao sha de blob do git do novo conteúdo (`hashlib.sha1(b"blob %d\0" % len(conteudo) + conteudo)`), não envia, registra "sem mudança" e devolve `True`. O `indices.json` não muda de comportamento (sempre muda, pelo `gerado_em`).
- `app/pipeline.py`: o tipo do callable injetado passa a `Callable[[bytes, Config, object, str], bool]` (chamado com `caminho` posicional ou nomeado, decidido no plano, igual em todos os lugares). Depois do cálculo, publica primeiro o `historico.json` e depois o `indices.json`. Falha ou exceção no `historico.json` é registrada e não altera `publicado` nem impede o `indices.json` ou os avisos.
- `scripts/rodar_local.py`: `_gravar` grava em `frontend/public/data/<nome do caminho>`; os dubles de teste (`test_main.py`, `test_pipeline.py`) passam a aceitar `caminho`.
- Cada PUT que muda algo é um commit em `main` e um deploy (Pages + testes); como o `historico.json` só muda quando vira o dia, é um commit extra por dia. O 409 da segunda escrita é coberto pela retentativa única existente.

## 3. Frontend

### Leitura e combinação — `frontend/src/lib/historico.ts`

- `lerHistorico(json): Resultado<ArquivoHistorico>` — validação descrita em 1.
- `combinarHistorico(m: Municipio, real?: ArquivoHistorico, reconstruido?: ArquivoHistorico): Municipio` — devolve o município com `historico` trocado pela união, do mais antigo ao mais recente, sem o D0 e sem dias futuros a ele: o `historico` do `indices.json` vence o `historico.json`, que vence o reconstruído. Itens reconstruídos ganham `reconstruido: true` (campo opcional novo em `HistoricoItem`). A classe de itens vindos dos arquivos é `classe(indice)`.
- `serieMunicipio` passa a preservar `reconstruido` (hoje copia só `{dia_alvo, indice, classe}`).
- **Desempenho:** `serieMunicipio`, `coordenadas` e `faixaDosDemais` passam a usar `Set`/`Map` por dia em vez de `includes`/`indexOf`/`filter` por dia; em Dados, a combinação e as séries ficam em `useMemo` (dependem de `indices`, arquivos e eixo). Meta: trocar de município ou mover o foco com 366 dias sem travar no celular.

### Período — `frontend/src/lib/periodo.ts`

- `type Periodo = { tipo: 7 | 30 } | { tipo: "personalizado"; de: string; ate: string }`.
- Todas as datas são `AAAA-MM-DD` calculadas a partir de `dia_alvo_d0` com aritmética em UTC (como `diasEixo`), nunca com `new Date()`/horário local.
- `eixoDoPeriodo(p, dia_alvo_d0): string[]` — 7/30 terminam no D0 (`diasEixo`); personalizado vai de `de` a `ate`.
- `limitesPersonalizado(d0) = { min: d0 − 365, max: d0 }`.
- `ajustarPersonalizado(de, ate, d0): { de, ate, ajustado: boolean } | null` — `null` se alguma data não for válida; senão limita as duas datas à janela e troca a ordem se `de > ate`; `ajustado` diz se algo mudou.
- URL: `?periodo=30`, ou `?de=AAAA-MM-DD&ate=AAAA-MM-DD`; ausente ou inválido → 7 dias. `lerPeriodo(search, d0): { periodo, ajustado }` usa `ajustarPersonalizado` (link antigo cujo `de` saiu da janela, ou `indices.json` atrasado com `ate > D0`, vira o intervalo mais próximo, com a nota "O período do link foi ajustado ao último ano disponível."). `escreverPeriodo(p)` com `history.replaceState`, preservando os outros parâmetros (padrão de `lib/setores.ts`).

### Tela Dados

- Carrega `indices.json` como hoje e mostra a tela logo. Em paralelo, carrega `historico.json` e `historico_reconstruido.json`; quando chegam, recombina.
- **Avisos (um só por vez, nesta ordem de prioridade):**
  1. enquanto algum arquivo de histórico ainda carrega e o eixo vai além do histórico do `indices.json`: nenhum aviso (evita piscar);
  2. algum arquivo falhou e o eixo vai além do histórico do `indices.json`: "Parte do histórico não carregou; esses dias aparecem vazios." (no período de 7 dias, que não precisa dos arquivos, não aparece);
  3. caso contrário, o aviso existente "Por enquanto há histórico de N dias para {M}…" quando o destaque tem menos dias que o eixo.
  Falha ao carregar o `historico_reconstruido.json` (arquivo versionado) também vai para `console.error`.
- Seletor: botões **7 dias**, **30 dias**, **Personalizado** (`aria-pressed`). Personalizado mostra dois `<input type="date">` nativos ("De", "Até"). `min`/`max` de cada campo vêm da janela e do outro campo; aplicar acontece no `change`/`blur` com data completa; se "De" passar de "Até" (ou o contrário), o outro campo acompanha. Não há estado de erro por digitação; a confirmação do período vai num `aria-live="polite"`. Os campos começam com os últimos 30 dias. Abaixo de 400 px, os campos empilham.
- Texto do topo: "…nos últimos {N} dias." para 7/30; "…de {A} a {B}." para personalizado.
- Os indicadores (monitorados, em alerta, chuva efetiva, pico da semana) não dependem do período e não mudam.
- **Tabela por município:** o minigráfico continua sempre com os **últimos 7 dias** (cabeçalho "Últimos 7 dias"), independente do período — mantém a célula legível e barata.

### Gráfico de evolução com muitos dias

- Até 31 dias: rótulos de dia (`dd/mm`), no máximo 10 visíveis (`passo = ceil(n / 10)`, contando a partir do último, que sempre aparece); pontos e marcas de mudança de classe como hoje.
- Acima de 31 dias: rótulos no primeiro dia de cada mês ("out/25", com o ano); sem círculos por dia e sem marcas de mudança de classe (só linha e área); o ponto em foco e o último continuam com círculo.
- **Dias reconstruídos:** a linha continua sólida (a tracejada é do alerta). O trecho reconstruído ganha um **fundo sombreado** (`.rec`, com token de tema claro/escuro) e uma **linha vertical no primeiro dia real** com o rótulo "início do sistema". Item correspondente na legenda e a nota de "O que a reconstrução é", só quando o eixo contém dias reconstruídos.
- Dica do dia em foco e tabela para leitor de tela: dia reconstruído leva a ressalva curta depois da classe.
- Teclado: ←/→ como hoje; **Home/End** vão ao primeiro e ao último dia.
- `min-width: 560px` e a rolagem horizontal no celular continuam; o painel abre no fim (D0 ou `ate`).

### i18n

Toda frase nova em PT/ES/EN, com o teste de paridade de chaves. Chaves que deixarem de ser usadas saem dos três arquivos.

## 4. Erros e casos-limite

- Arquivo de histórico ausente (antes da primeira execução do pipeline) ou inválido: tratado como falha daquele arquivo (aviso acima), nunca como índice zero.
- Município presente no `indices.json` e ausente nos arquivos: usa só o que tiver.
- Personalizado cobrindo só dias sem dado: eixo vazio e o aviso "Por enquanto há histórico de 0 dias…" (texto de N com N=0).
- Personalizado de 1 dia (`de = ate`): eixo de um dia, ponto único, sem linha.
- Troca de município, de período e recarga com `?de=&ate=` mantêm o período.
- Reconstruído e real nunca se sobrepõem por construção; se se sobrepuserem, o real vence.
- Fuso: entre 21h e 24h em Brasília o dia UTC já virou; como tudo parte de `dia_alvo_d0`, não há deslocamento (teste dedicado).

## 5. Testes

- **Backend (pytest `-W error`, sem rede):** `montar_historico` (buracos viram `null`, 4 casas, município vazio fora) e `serializar_compacto`; cálculo do reconstruído com série sintética (EfR e Rtotal batendo com cálculo manual, último dia usando o rótulo `(D+1) T00`, maior ponto vence, hora `null` invalida o ponto no dia, falhas de validação do script); arquivo versionado com `limiar_mm`/`mv_h` iguais aos da configuração e cobrindo os 27 municípios; `publicar` com `caminho` e pulo quando o sha é igual; pipeline publica os dois, `historico.json` com todos os municípios da configuração, falha do `historico.json` não afeta `publicado`. Um teste marcado `rede` para a consulta real ao arquivo histórico.
- **Frontend (vitest):** `lerHistorico` (válido, `schema_version` errado, item inválido, `NaN`); `combinarHistorico` (precedência, `reconstruido`, D0 fora, classe calculada); `serieMunicipio` preservando `reconstruido`; `eixoDoPeriodo`, `ajustarPersonalizado` (janela, ordem, inválido), `lerPeriodo`/`escreverPeriodo`, sem dependência do relógio local; rótulos do eixo com 7, 30 e 366 dias (meses com ano); paridade de i18n.
- **Navegador:** 7/30/Personalizado em PT/ES/EN, 320/390/1366 px, tema claro e escuro, histórico ausente (arquivo renomeado), link com `?de=` fora da janela, teclado no gráfico (setas, Home/End), troca de município com 366 dias sem travar.

## Fora do escopo

- Marcar ocorrências do Atlas no gráfico (sugestão para depois).
- Histórico além de 1 ano, ou reconstruir dias depois de 15/10/2026.
- Mudar o `indices.json`, o bot ou as outras telas.
