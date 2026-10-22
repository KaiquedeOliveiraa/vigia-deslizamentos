# Períodos na tela Dados: 7 dias, 30 dias e Personalizado

Parte 4 do roteiro. Branch `feat/periodos`, sobre `feat/areas-de-risco`.

## Objetivo

A tela Dados deixa de oferecer 5 / 7 / 15 dias e passa a oferecer **7 dias** (padrão), **30 dias** e **Personalizado** (de uma data a outra, dentro do último ano). Quem usa: Defesa Civil e público olhando como o índice se comportou nas semanas ou meses anteriores — por exemplo, antes de uma ocorrência registrada em Áreas de risco.

**Sucesso:** escolher 30 dias ou um intervalo de até um ano mostra a evolução do índice sem buracos causados pela idade do sistema; o que foi reconstruído nunca se confunde com o que o sistema publicou; se o histórico longo não carregar, a tela continua funcionando com os 15 dias do `indices.json`.

## Decisões (aprovadas)

- O banco só tem cálculos desde 15/10/2026. Os dias anteriores são **reconstruídos** com chuva de reanálise (arquivo histórico do Open-Meteo), uma única vez, e marcados como reconstruídos na tela (opção b).
- Janela de **1 ano** (365 dias antes do D0, mais o D0).
- **Abordagem 1:** dois arquivos novos, lidos só pela tela Dados. O `indices.json` e as outras telas não mudam.

## 1. Dados

### Formato comum (`historico.json` e `historico_reconstruido.json`)

```json
{
  "schema_version": 1,
  "fonte": "texto curto da origem",
  "municipios": {
    "4214805": { "inicio": "2025-10-15", "indices": [0.421, 0.398, null, 0.512] }
  }
}
```

- `indices[i]` é o índice do dia-alvo `inicio + i` (dia civil UTC, como no resto do contrato). `null` é dia sem dado.
- Índice com 3 casas decimais. A classe não vai no arquivo: o site calcula com `classe()` de `classes.ts` (mesmas faixas do backend).
- Município sem nenhum dia não aparece. `inicio` é o primeiro dia com dado; a lista não termina em `null`.
- **Sem data de geração no arquivo:** o conteúdo só muda quando muda um dia, o que permite pular a publicação quando nada mudou (ver 2).
- `schema_version` desconhecido, campo faltando, `inicio` inválido ou item que não seja número/`null`: o site trata o arquivo inteiro como falha de carregamento (nunca dados parciais).

### `frontend/public/data/historico_reconstruido.json` (gerado uma vez, versionado)

- Script `backend/scripts/gerar_historico_reconstruido.py`, no padrão de `gerar_setores_risco.py`/`gerar_ocorrencias.py`: rede só no script, cálculo em funções puras testadas offline.
- Período: de `--fim` (padrão `2026-10-14`, véspera do primeiro cálculo real) para trás, `--dias` dias (padrão 365).
- Uma requisição ao `https://archive-api.open-meteo.com/v1/archive` com todos os pontos de `config/municipios.json` (`latitude`/`longitude` separados por vírgula, `hourly=precipitation`, `timezone=GMT`), de `inicio − 7 dias` a `fim`. A resposta é uma lista, um item por ponto, na ordem pedida.
- Índice do dia `D` para um ponto: `subindice(efr(chuva nos rótulos de rotulos_efr(D), mv_h), soma da chuva nos rótulos de rotulos_rtotal(D), limiar_mm)`, reaproveitando `app.calculo.agregacao.rotulos_efr`/`rotulos_rtotal`, `app.calculo.chuva_efetiva.efr` e `app.calculo.indice.subindice`. A série de EfR vai na ordem que `efr` espera (`t=0` primeiro). Índice do município: o **maior** entre os seus pontos. `limiar_mm` e `mv_h` atuais de cada município.
- Hora ausente (`null` ou rótulo faltando) em algum ponto: aquele ponto não conta naquele dia; se nenhum ponto do município tiver o dia completo, o dia vira `null`. Nunca vira zero.
- O script **falha sem gravar** se: a resposta não tiver um item por ponto; algum município ficar sem nenhum dia; mais de 5% dos dias de algum município forem `null`.
- `fonte`: `"Reconstruído pelo VIGIA com chuva horária de reanálise (Open-Meteo, arquivo histórico ERA5), limiar e meia-vida atuais"`.
- Tamanho esperado: ~27 × 365 números ≈ 50 KB.

### `frontend/public/data/historico.json` (publicado pelo pipeline)

- Montado de `banco.historico(conexao, ibge, dia_alvo_d0, limiar_mm, dias=365)` para cada município calculado na execução — as mesmas regras do `historico` atual (último cálculo de cada dia-alvo, conversão de limiar, D0 fora).
- `fonte`: `"Calculado pelo VIGIA a cada execução (índice publicado do dia)"`.
- Município sem histórico fica de fora. Nenhum município com histórico: o arquivo sai com `municipios: {}` (válido).
- O `historico` de 15 dias dentro do `indices.json` continua igual.

Os dois formatos e as regras de leitura entram em `docs/contratos-de-dados.md`.

## 2. Backend

- `app/exportacao/exportar.py`: `montar_historico(historicos: dict[str, list[ItemHistorico]], fonte: str) -> dict` (formato acima; usado pelo pipeline e pelo script) — dias consecutivos a partir do primeiro, `null` nos buracos, 3 casas.
- `app/exportacao/publicar.py`: `publicar(conteudo, config, http, caminho=CAMINHO_NO_REPOSITORIO)`. Antes do `PUT`, se o `sha` lido do arquivo atual for igual ao sha de blob do git do novo conteúdo (`sha1(b"blob %d\0" % len + conteudo)`), não envia, registra "sem mudança" e devolve `True`. Mensagens de log passam a citar o `caminho`. O comportamento atual do `indices.json` não muda (ele sempre muda, pelo `gerado_em`).
- `app/pipeline.py`: depois do cálculo, publica primeiro o `historico.json` e depois o `indices.json` (a última publicação dispara o deploy que já contém os dois). Falha ou exceção no `historico.json` é registrada e não altera `publicado` nem impede o `indices.json` ou os avisos.
- `scripts/rodar_local.py`: grava os dois arquivos em `frontend/public/data/`.
- Cada PUT é um commit em `main` e um deploy; como o `historico.json` só muda uma vez por dia, na prática há um commit extra por dia.

## 3. Frontend

### Leitura e combinação — `frontend/src/lib/historico.ts`

- `lerHistorico(json): Resultado<ArquivoHistorico>` — validação descrita em 1.
- `combinarHistorico(m: Municipio, real?: ArquivoHistorico, reconstruido?: ArquivoHistorico): Municipio` — devolve o município com `historico` trocado pela união, do mais antigo ao mais recente, sem o D0 e sem dias futuros a ele: o `historico` do `indices.json` vence o `historico.json`, que vence o reconstruído. Itens reconstruídos ganham `reconstruido: true` (campo opcional novo em `HistoricoItem`). A classe de itens vindos dos arquivos é `classe(indice)`.
- Como o resto da tela (`serieMunicipio`, `faixaDosDemais`, `Minigrafico`, `tendencia`) já lê `m.historico`, os componentes recebem os municípios combinados e não mudam de assinatura.

### Período — `frontend/src/lib/periodo.ts`

- `type Periodo = { tipo: 7 | 30 } | { tipo: "personalizado"; de: string; ate: string }`.
- `eixoDoPeriodo(p, dia_alvo_d0): string[]` — 7/30 terminam no D0 (`diasEixo`); personalizado vai de `de` a `ate`.
- `validarPersonalizado(de, ate, dia_alvo_d0): string | null` — mensagem de erro (chave de i18n) ou `null`. Regras: datas válidas; `de ≤ ate`; `ate ≤ D0`; `de ≥ D0 − 365`.
- URL: `?periodo=30`, ou `?de=AAAA-MM-DD&ate=AAAA-MM-DD`; ausente ou inválido → 7 dias. `lerPeriodo(search, d0)` e `escreverPeriodo(p)` com `history.replaceState`, preservando os outros parâmetros (mesmo padrão de `lib/setores.ts`).

### Tela Dados

- Carrega `indices.json` como hoje e mostra a tela logo. Em paralelo, carrega `historico.json` e `historico_reconstruido.json`; quando chegam, recombina. Falha de um deles: a tela segue com o que tem e mostra, abaixo do seletor, "Não foi possível carregar o histórico completo; mostrando os últimos 15 dias disponíveis." O aviso existente "Por enquanto há histórico de N dias…" continua valendo.
- Seletor: botões **7 dias**, **30 dias**, **Personalizado** (`aria-pressed`). Personalizado mostra dois `<input type="date">` nativos ("De", "Até", com `min`/`max`) e aplica ao mudar; data inválida mostra a mensagem em `role="alert"` junto dos campos e mantém o último período válido. Os campos começam com os últimos 30 dias.
- Texto do topo: "…nos últimos {N} dias." para 7/30; "…de {A} a {B}." para personalizado.
- Os indicadores (monitorados, em alerta, chuva efetiva, pico da semana) não dependem do período e não mudam.

### Gráfico de evolução com muitos dias

- Rótulos do eixo X: no máximo 10 visíveis (`passo = ceil(n / 10)`, contando a partir do último, que sempre aparece).
- Até 31 dias: pontos e marcas de mudança de classe como hoje. Acima de 31: sem círculos por dia e sem marcas de mudança de classe (só linha e área); o ponto em foco e o último continuam com círculo.
- Trechos reconstruídos: linha pontilhada mais fina e área mais clara (classe `.rec`), com o mesmo comportamento de cores de tema. A linha tracejada continua reservada ao alerta.
- Legenda e aviso só quando o eixo contém dias reconstruídos: item "pontilhado: reconstruído" na legenda e a nota "Dias antes de {D} foram reconstruídos com chuva de reanálise (ERA5, Open-Meteo) e os parâmetros atuais; não são o que o sistema publicou na época." (`{D}` = dia seguinte ao último reconstruído).
- Dica do dia em foco e tabela para leitor de tela: dia reconstruído leva "(reconstruído)" depois da classe.
- Teclado: ←/→ como hoje; **PageUp/PageDown** andam 7 dias; **Home/End** vão ao primeiro e ao último dia.
- `min-width: 560px` e a rolagem horizontal no celular continuam; o painel abre no fim (D0 ou `ate`).

### i18n

Toda frase nova em PT/ES/EN, com o teste de paridade de chaves. As chaves "{N} dias" e as de período antigo que deixarem de ser usadas saem dos três arquivos.

## 4. Erros e casos-limite

- Arquivo de histórico ausente (antes da primeira execução do pipeline) ou inválido: tratado como falha daquele arquivo (aviso acima), nunca como índice zero.
- Município presente no `indices.json` e ausente nos arquivos: usa só o que tiver.
- Personalizado cobrindo só dias sem dado: o gráfico mostra o eixo vazio e o aviso "Por enquanto há histórico de 0 dias…" já existente cobre (com o texto de 0 dias tratado como o de N).
- Personalizado de 1 dia (`de = ate`): eixo de um dia, ponto único, sem linha.
- Troca de município, de período e recarga com `?de=&ate=` mantêm o período.
- Reconstruído e real nunca se sobrepõem por construção (reconstruído termina em 14/10/2026); se se sobrepuserem, o real vence.

## 5. Testes

- **Backend (pytest `-W error`, sem rede):** `montar_historico` (buracos viram `null`, arredondamento, município vazio fora); cálculo do reconstruído com série sintética (EfR e Rtotal batendo com cálculo manual, maior ponto vence, hora `null` invalida o ponto no dia, falhas de validação do script); `publicar` com `caminho` e pulo quando o sha é igual; pipeline publica os dois, falha do `historico.json` não afeta `publicado`. Um teste marcado `rede` para a consulta real ao arquivo histórico.
- **Frontend (vitest):** `lerHistorico` (válido, `schema_version` errado, item inválido); `combinarHistorico` (precedência, `reconstruido`, D0 fora, classe calculada); `eixoDoPeriodo`, `validarPersonalizado`, `lerPeriodo`/`escreverPeriodo`; rótulos do eixo com 7, 30 e 366 dias; paridade de i18n.
- **Navegador:** 7/30/Personalizado em PT/ES/EN, 320/390/1366 px, tema claro e escuro, histórico ausente (arquivo renomeado), intervalo inválido, teclado no gráfico, link com `?de=&ate=`.

## Fora do escopo

- Marcar ocorrências do Atlas no gráfico (fica como sugestão para depois).
- Histórico além de 1 ano, ou reconstruir dias depois de 15/10/2026.
- Mudar o `indices.json`, o bot ou as outras telas.
