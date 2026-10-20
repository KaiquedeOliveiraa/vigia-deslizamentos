# Plano de implementação: ampliação para o Alto Vale do Itajaí

> **Para agentes:** use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar tarefa por tarefa. Os passos usam caixas `- [ ]` para acompanhamento.

**Objetivo:** levar o VIGIA de 6 para os 27 municípios das microrregiões IBGE 42011 e 42014, sem mudar o cálculo do índice e só com acréscimos opcionais nos contratos.

**Arquitetura:**
- **Lista:** um script offline gera `backend/config/municipios.json` a partir da API do IBGE e da malha fixada. Pipeline, bot e site já são dirigidos por essa lista.
- **Bot:** o backend escreve grupos no `bot.json`, e o Worker monta um teclado em dois passos, sem estado no servidor.
- **Site:** reaproveita a regra de zoom (`.longe`) para os rótulos, troca as 26 linhas cinza da Evolução por uma faixa mínimo–máximo e ajusta textos.

**Stack:**
- Python 3.12 (pytest `-W error`, python-telegram-bot 22.x);
- Cloudflare Worker em TypeScript (vitest-pool-workers, D1);
- Astro + React 19 + Leaflet (vitest, ambiente node).

**Especificação:** `docs/superpowers/specs/2026-10-19-ampliacao-alto-vale-design.md`

## Restrições globais

- **Área:** microrregiões IBGE `42011` (Rio do Sul) e `42014` (Ituporanga), nessa ordem. Total de 27 municípios.
- **Novos municípios:** `limiar_mm: 150`, `mv_h: 24`, um ponto (o centroide) e a `fonte_limiar` exatamente igual à atual: `"VIGIA, limiar provisório definido pela equipe (abaixo do hipotético de 250 mm do GeoRisk)"`.
- **Os 6 atuais** (4205100, 4206900, 4209151, 4214003, 4219358, 4219408) **não mudam** em nenhum campo.
- **Contratos:** nenhum campo renomeado ou removido; `schema_version` continua 1 no `bot.json`; `indices.json` sem mudança.
- **Textos de botão únicos** no `bot.json` inteiro, comparados pela normalização "NFD sem acentos, minúsculas, espaços colapsados" (a `normalizarNome` do Worker).
- **Rótulos:** os grupos se chamam "Região de Rio do Sul" e "Região de Ituporanga"; "Todos da Região de …"; "Voltar"; o "Todos" global continua igual.
- **Limite de mensagem do Telegram:** 4096 unidades UTF-16. Em Python, conta-se `len(texto.encode("utf-16-le")) // 2`.
- **Testes:** sem rede (`-m 'not rede'` já é o padrão). Backend com `python -m pytest -W error`; frontend e Worker com `npm test` e `npm run typecheck`.
- **Commits:** em português, sem linha de atribuição ao Claude.
- **Textos novos do site:** sempre em `frontend/src/i18n/es.json` **e** `en.json`. O teste de paridade exige as mesmas chaves nos dois.

## Pontos de atenção na revisão

1. **Inscrito "Todos" antigo:** um chat que escolheu "Todos" quando eram 6 continua com 6 linhas no D1. O `/status` dele lista só esses 6. É o comportamento decidido, coberto na Tarefa 6 pelo teste "inscrito antigo continua com os seus".
2. **Botão de um teclado antigo:** a pessoa toca num botão de grupo depois de o `bot.json` perder `grupos` (reversão). O Worker sem grupos não reconhece "Região de Rio do Sul" e responde `opcao_desconhecida` com o teclado de hoje, sem inscrever nada. Coberto na Tarefa 6.
3. **Nome digitado com acento ou caixa diferente** ("presidente getulio"): deve inscrever. Coberto na Tarefa 6.
4. **`/status` de quem assina os 27:** nenhuma parte acima do limite e nenhum bloco cortado. Coberto nas Tarefas 4 e 6, com um limite pequeno que força a divisão.
5. **Telegram limitando envios (429) num evento regional:** a mensagem chega na segunda tentativa, e a classe só é gravada quando alguém recebeu. Coberto na Tarefa 5.

---

### Tarefa 1: `Municipio.microrregiao` no carregador

**Arquivos:**
- Modificar: `backend/app/config.py`, nas classes `Municipio` e `_municipio_a_partir_de`
- Teste: `backend/tests/test_config.py`

**Interfaces:**
- Produz:
  - `@dataclass(frozen=True) class Microrregiao: codigo: str; nome: str`
  - `Municipio.microrregiao: Microrregiao | None = None`, o último campo, com valor padrão

- [ ] **Passo 1: escrever os testes que falham**

Acrescente ao fim de `backend/tests/test_config.py`:

```python
import json as _json

from app.config import Microrregiao


def _um_municipio(**extra):
    base = {
        "ibge": "4206900",
        "nome": "Ibirama",
        "limiar_mm": 150,
        "fonte_limiar": "x",
        "mv_h": 24,
        "pontos": [{"lat": -27.0, "lon": -49.5}],
    }
    base.update(extra)
    return base


def test_microrregiao_e_opcional(tmp_path):
    caminho = tmp_path / "m.json"
    caminho.write_text(_json.dumps([_um_municipio()]), encoding="utf-8")
    assert carregar_municipios(caminho)[0].microrregiao is None


def test_microrregiao_lida_quando_presente(tmp_path):
    caminho = tmp_path / "m.json"
    caminho.write_text(
        _json.dumps([_um_municipio(microrregiao={"codigo": "42011", "nome": "Rio do Sul"})]),
        encoding="utf-8",
    )
    assert carregar_municipios(caminho)[0].microrregiao == Microrregiao("42011", "Rio do Sul")


@pytest.mark.parametrize(
    "valor",
    [{"codigo": "4201", "nome": "Rio do Sul"}, {"codigo": "42011", "nome": ""}, "42011"],
)
def test_microrregiao_invalida(tmp_path, valor):
    caminho = tmp_path / "m.json"
    caminho.write_text(_json.dumps([_um_municipio(microrregiao=valor)]), encoding="utf-8")
    with pytest.raises(ConfiguracaoInvalidaError, match="microrregiao"):
        carregar_municipios(caminho)
```

Confira se `pytest` e `ConfiguracaoInvalidaError` já estão importados no topo do arquivo; se não, acrescente `import pytest` e `from app.config import ConfiguracaoInvalidaError`.

- [ ] **Passo 2: rodar e ver falhar**

Rode `cd backend && python -m pytest -W error tests/test_config.py -q`. Deve falhar com `ImportError: cannot import name 'Microrregiao'`.

- [ ] **Passo 3: implementar**

Em `backend/app/config.py`, acima de `class Municipio`:

```python
@dataclass(frozen=True)
class Microrregiao:
    """Microrregião IBGE do município: agrupa o teclado do bot (opcional no JSON)."""

    codigo: str
    nome: str
```

Em `class Municipio`, depois de `pontos`:

```python
    microrregiao: Microrregiao | None = None
```

Em `_municipio_a_partir_de`, antes do `return Municipio(`:

```python
    microrregiao = None
    if "microrregiao" in item:
        bruta = item["microrregiao"]
        codigo = bruta.get("codigo") if isinstance(bruta, dict) else None
        nome_micro = bruta.get("nome") if isinstance(bruta, dict) else None
        if not (isinstance(codigo, str) and len(codigo) == 5 and codigo.isdigit()
                and isinstance(nome_micro, str) and nome_micro.strip()):
            raise ConfiguracaoInvalidaError(
                f"município '{ibge}': 'microrregiao' deve ser "
                f"{{codigo: 5 dígitos, nome}}, recebido: {bruta!r}"
            )
        microrregiao = Microrregiao(codigo=codigo, nome=nome_micro)
```

E passe `microrregiao=microrregiao,` na chamada `Municipio(...)`.

- [ ] **Passo 4: rodar e ver passar**

Rode `cd backend && python -m pytest -W error -q`. Os testes novos passam e nada mais quebra.

- [ ] **Passo 5: commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(backend): microrregião opcional no municipios.json"
```

---

### Tarefa 2: script `gerar_municipios` e a lista dos 27

**Arquivos:**
- Criar: `backend/scripts/gerar_municipios.py`
- Criar: `backend/tests/test_gerar_municipios.py`
- Modificar: `backend/config/municipios.json`, gerado pelo script
- Modificar:
  - `backend/tests/test_config.py`, nas contagens de 6;
  - `backend/tests/test_bot_json.py`, no teste das 63 combinações e em `len(MUNICIPIOS) == 6`.

**Interfaces:**
- Consome: `Microrregiao` (Tarefa 1).
- Produz, em `scripts.gerar_municipios`:
  - `MICRORREGIOES: tuple[str, ...] = ("42011", "42014")`
  - `COMMIT_MALHA: str`, o mesmo hash de `frontend/scripts/gerar-geojson.mjs`
  - `FONTE_LIMIAR_PROVISORIA: str`
  - `centroide(anel: list[list[float]]) -> tuple[float, float]`, devolvendo `(lon, lat)`
  - `dentro(anel: list[list[float]], lon: float, lat: float) -> bool`
  - `ponto_do_municipio(ibge: str, geometria: dict) -> dict`, devolvendo `{"lat": float, "lon": float}`
  - `chave_de_ordem(item: dict) -> tuple[str, str]`
  - `mesclar(atuais: list[dict], ibge_por_micro: list[tuple[dict, list[dict]]], geometrias: dict[str, dict]) -> list[dict]`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Passo 1: escrever os testes que falham**

Crie `backend/tests/test_gerar_municipios.py`:

```python
"""Testes do gerador da lista de municípios (sem rede: respostas fixas)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from scripts.gerar_municipios import (
    COMMIT_MALHA,
    FONTE_LIMIAR_PROVISORIA,
    centroide,
    chave_de_ordem,
    dentro,
    mesclar,
    ponto_do_municipio,
)

RAIZ = Path(__file__).resolve().parents[2]
QUADRADO = [[-49.6, -27.1], [-49.4, -27.1], [-49.4, -26.9], [-49.6, -26.9], [-49.6, -27.1]]


def poligono(anel):
    return {"type": "Polygon", "coordinates": [anel]}


def test_commit_da_malha_igual_ao_do_mapa():
    script = (RAIZ / "frontend" / "scripts" / "gerar-geojson.mjs").read_text(encoding="utf-8")
    assert f'const COMMIT = "{COMMIT_MALHA}";' in script


def test_centroide_do_quadrado():
    lon, lat = centroide(QUADRADO)
    assert lon == pytest.approx(-49.5)
    assert lat == pytest.approx(-27.0)


def test_dentro_e_fora():
    assert dentro(QUADRADO, -49.5, -27.0)
    assert not dentro(QUADRADO, -49.7, -27.0)


def test_ponto_do_municipio_arredonda_a_4_casas_e_fica_dentro():
    assert ponto_do_municipio("4206900", poligono(QUADRADO)) == {"lat": -27.0, "lon": -49.5}


def test_ponto_falha_em_multipolygon_e_em_furos():
    with pytest.raises(ValueError, match="4206900"):
        ponto_do_municipio("4206900", {"type": "MultiPolygon", "coordinates": [[QUADRADO]]})
    with pytest.raises(ValueError, match="4206900"):
        ponto_do_municipio("4206900", {"type": "Polygon", "coordinates": [QUADRADO, QUADRADO]})


def test_ponto_falha_quando_o_centroide_cai_fora():
    # "U": o centroide fica no vão entre as pernas.
    u = [[0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3], [0, 0]]
    with pytest.raises(ValueError, match="fora"):
        ponto_do_municipio("4200000", poligono(u))


def test_ordem_sem_acento_e_desempate_pelo_ibge():
    itens = [{"nome": "Ítaca", "ibge": "2"}, {"nome": "Ibirama", "ibge": "1"}, {"nome": "Agrolândia", "ibge": "3"}]
    assert [i["nome"] for i in sorted(itens, key=chave_de_ordem)] == ["Agrolândia", "Ibirama", "Ítaca"]


ATUAL = {
    "ibge": "4206900",
    "nome": "Ibirama",
    "limiar_mm": 150,
    "fonte_limiar": FONTE_LIMIAR_PROVISORIA,
    "mv_h": 24,
    "pontos": [{"lat": -27.0181, "lon": -49.5286}],
}
RIO_DO_SUL = {"id": 42011, "nome": "Rio do Sul"}


def test_mescla_preserva_o_atual_e_acrescenta_o_novo():
    resultado = mesclar(
        [dict(ATUAL)],
        [(RIO_DO_SUL, [{"id": 4206900, "nome": "Ibirama"}, {"id": 4209003, "nome": "Lontras"}])],
        {"4209003": poligono(QUADRADO)},
    )
    assert [m["ibge"] for m in resultado] == ["4206900", "4209003"]
    ibirama, lontras = resultado
    assert {k: v for k, v in ibirama.items() if k != "microrregiao"} == ATUAL
    assert ibirama["microrregiao"] == {"codigo": "42011", "nome": "Rio do Sul"}
    assert lontras == {
        "ibge": "4209003",
        "nome": "Lontras",
        "limiar_mm": 150,
        "fonte_limiar": FONTE_LIMIAR_PROVISORIA,
        "mv_h": 24,
        "pontos": [{"lat": -27.0, "lon": -49.5}],
        "microrregiao": {"codigo": "42011", "nome": "Rio do Sul"},
    }


def test_mescla_falha_se_um_atual_sumir_do_ibge():
    with pytest.raises(ValueError, match="4206900"):
        mesclar([dict(ATUAL)], [(RIO_DO_SUL, [{"id": 4209003, "nome": "Lontras"}])], {"4209003": poligono(QUADRADO)})


def test_mescla_falha_com_microrregiao_vazia():
    with pytest.raises(ValueError, match="42011"):
        mesclar([], [(RIO_DO_SUL, [])], {})


def test_mescla_mantem_o_nome_atual_e_avisa(caplog):
    with caplog.at_level(logging.WARNING):
        resultado = mesclar([dict(ATUAL)], [(RIO_DO_SUL, [{"id": 4206900, "nome": "Ibirama (novo)"}])], {})
    assert resultado[0]["nome"] == "Ibirama"
    assert "Ibirama (novo)" in caplog.text


def test_arquivo_versionado_tem_os_27_e_os_6_atuais_intactos():
    dados = json.loads((RAIZ / "backend" / "config" / "municipios.json").read_text(encoding="utf-8"))
    assert len(dados) == 27
    assert dados == sorted(dados, key=chave_de_ordem)
    por_ibge = {m["ibge"]: m for m in dados}
    assert {m["microrregiao"]["codigo"] for m in dados} == {"42011", "42014"}
    seis = {"4205100", "4206900", "4209151", "4214003", "4219358", "4219408"}
    assert seis <= set(por_ibge)
    for ibge in seis:
        assert por_ibge[ibge]["fonte_limiar"] == FONTE_LIMIAR_PROVISORIA
```

- [ ] **Passo 2: rodar e ver falhar**

Rode `cd backend && python -m pytest -W error tests/test_gerar_municipios.py -q`. Deve falhar com `ModuleNotFoundError: scripts.gerar_municipios`.

- [ ] **Passo 3: implementar o script**

Crie `backend/scripts/gerar_municipios.py`:

```python
"""Gera `backend/config/municipios.json` com os municípios do Alto Vale do Itajaí.

Roda uma vez (e de novo se a área mudar), não no pipeline: o arquivo é
versionado, como o `estacoes.json`.

    python -m scripts.gerar_municipios

Fontes: a API de localidades do IBGE (microrregiões 42011 Rio do Sul e 42014
Ituporanga, divisão de 1989 — substituída pelas regiões imediatas em 2017, mas
estável e suficiente para uma lista gerada uma vez) e a malha municipal do
`tbrugz/geodata-br` no mesmo commit que o mapa do site usa.

Os municípios que já estão no arquivo **não mudam** (ponto, limiar, fonte,
`mv_h` e nome): o histórico gravado no banco depende deles. Um município do
arquivo que suma do IBGE interrompe o script em vez de ser removido.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import unicodedata
from pathlib import Path

import requests

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
CAMINHO_MUNICIPIOS = RAIZ_BACKEND / "config" / "municipios.json"

MICRORREGIOES = ("42011", "42014")
URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/microrregioes/{codigo}/municipios"
#: Mesmo commit de `frontend/scripts/gerar-geojson.mjs` (um teste confere).
COMMIT_MALHA = "c39dfb040bfd466fe2a476bafed00749c5c42f16"
URL_MALHA = f"https://raw.githubusercontent.com/tbrugz/geodata-br/{COMMIT_MALHA}/geojson/geojs-42-mun.json"

FONTE_LIMIAR_PROVISORIA = (
    "VIGIA, limiar provisório definido pela equipe "
    "(abaixo do hipotético de 250 mm do GeoRisk)"
)
LIMIAR_PROVISORIO_MM = 150
MV_H = 24
TIMEOUT_S = 30

_log = logging.getLogger(__name__)


def centroide(anel: list[list[float]]) -> tuple[float, float]:
    """Centroide ponderado pela área de um anel fechado (lon, lat)."""
    area2 = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(anel, anel[1:]):
        cruz = x1 * y2 - x2 * y1
        area2 += cruz
        cx += (x1 + x2) * cruz
        cy += (y1 + y2) * cruz
    if area2 == 0:
        raise ValueError("anel sem área")
    return cx / (3 * area2), cy / (3 * area2)


def dentro(anel: list[list[float]], lon: float, lat: float) -> bool:
    """Teste par-ímpar, com a borda de cima/baixo semiaberta."""
    resposta = False
    for (x1, y1), (x2, y2) in zip(anel, anel[1:]):
        if (y1 > lat) != (y2 > lat):
            x_corte = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x_corte:
                resposta = not resposta
    return resposta


def ponto_do_municipio(ibge: str, geometria: dict) -> dict:
    """O centroide arredondado a 4 casas; erro se não for um Polygon de um anel ou cair fora."""
    if geometria.get("type") != "Polygon" or len(geometria.get("coordinates", [])) != 1:
        raise ValueError(f"município {ibge}: geometria precisa ser Polygon de um anel só")
    anel = geometria["coordinates"][0]
    lon, lat = centroide(anel)
    lon, lat = round(lon, 4), round(lat, 4)
    if not dentro(anel, lon, lat):
        raise ValueError(f"município {ibge}: centroide ({lat}, {lon}) caiu fora do polígono")
    return {"lat": lat, "lon": lon}


def _normalizado(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sem_acento.casefold().split())


def chave_de_ordem(item: dict) -> tuple[str, str]:
    return _normalizado(item["nome"]), item["ibge"]


def mesclar(
    atuais: list[dict],
    ibge_por_micro: list[tuple[dict, list[dict]]],
    geometrias: dict[str, dict],
) -> list[dict]:
    """Junta o arquivo atual com a resposta do IBGE. Ver a docstring do módulo."""
    por_ibge = {m["ibge"]: dict(m) for m in atuais}
    vistos: set[str] = set()
    for micro, lista in ibge_por_micro:
        codigo = str(micro["id"])
        if not lista:
            raise ValueError(f"microrregião {codigo} veio vazia do IBGE")
        microrregiao = {"codigo": codigo, "nome": micro["nome"]}
        for bruto in lista:
            ibge = str(bruto["id"]).zfill(7)
            vistos.add(ibge)
            if ibge in por_ibge:
                if por_ibge[ibge]["nome"] != bruto["nome"]:
                    _log.warning(
                        "município %s: IBGE chama de %r; mantido %r",
                        ibge, bruto["nome"], por_ibge[ibge]["nome"],
                    )
                por_ibge[ibge]["microrregiao"] = microrregiao
                continue
            por_ibge[ibge] = {
                "ibge": ibge,
                "nome": bruto["nome"],
                "limiar_mm": LIMIAR_PROVISORIO_MM,
                "fonte_limiar": FONTE_LIMIAR_PROVISORIA,
                "mv_h": MV_H,
                "pontos": [ponto_do_municipio(ibge, geometrias[ibge])],
                "microrregiao": microrregiao,
            }
    faltando = sorted(set(por_ibge) - vistos)
    if faltando:
        raise ValueError(f"município(s) do arquivo fora da resposta do IBGE: {faltando}")
    return sorted(por_ibge.values(), key=chave_de_ordem)


def _buscar(http: requests.Session, url: str):
    resposta = http.get(url, timeout=TIMEOUT_S)
    if resposta.status_code != 200:
        raise RuntimeError(f"HTTP {resposta.status_code} em {url}")
    return resposta.json()


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(prog="python -m scripts.gerar_municipios", description=__doc__)
    analisador.add_argument("--saida", default=str(CAMINHO_MUNICIPIOS))
    argumentos = analisador.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    atuais = json.loads(CAMINHO_MUNICIPIOS.read_text(encoding="utf-8"))
    with requests.Session() as http:
        malha = _buscar(http, URL_MALHA)
        ibge_por_micro = []
        for codigo in MICRORREGIOES:
            lista = _buscar(http, URL_IBGE.format(codigo=codigo))
            micro = lista[0]["microrregiao"] if lista else {"id": codigo, "nome": ""}
            ibge_por_micro.append(({"id": micro["id"], "nome": micro["nome"]}, lista))

    geometrias = {f["properties"]["id"]: f["geometry"] for f in malha["features"]}
    itens = mesclar(atuais, ibge_por_micro, geometrias)
    Path(argumentos.saida).write_text(
        json.dumps(itens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{len(itens)} município(s) gravado(s) em {argumentos.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Antes de seguir, confira que `scripts/gerar_estacoes.py` acrescenta `RAIZ_BACKEND` ao `sys.path`. Este script não importa nada de `app`, então não precisa disso.

- [ ] **Passo 4: rodar os testes de função pura**

Rode `cd backend && python -m pytest -W error tests/test_gerar_municipios.py -q -k "not arquivo_versionado"`. Tudo passa.

- [ ] **Passo 5: gerar o arquivo (com rede, uma vez)**

Rode `cd backend && python -m scripts.gerar_municipios`. A saída esperada é `27 município(s) gravado(s) em .../municipios.json`.

Confira com `git diff backend/config/municipios.json`. Os 6 atuais só podem ganhar a linha `microrregiao` e mudar de posição; ponto, limiar e fonte ficam iguais.

- [ ] **Passo 6: corrigir os testes que contavam 6**

Em `backend/tests/test_config.py`, troque as duas linhas `== 6` de `test_carregar_municipios_retorna_todos_os_municipios_configurados` por `== 27`.

Em `backend/tests/test_bot_json.py`:
- troque `assert len(MUNICIPIOS) == 6` por `assert len(MUNICIPIOS) == 27`;
- troque o teste das combinações por:

```python
def test_status_bate_com_texto_do_status_em_todas_as_combinacoes_de_6():
    # Combinações dos 6 primeiros: 2^27 com a lista toda nunca terminaria.
    seis = MUNICIPIOS[:6]
    atuais = atuais_de_teste()
    status = montar(atuais=atuais)["status"]
    total = 0

    for tamanho in range(1, len(seis) + 1):
        for subconjunto in combinations(seis, tamanho):
            total += 1
            situacoes = [(m.nome, atuais[m.ibge]) for m in subconjunto]
            montado = (
                status["cabecalho"]
                + status["separador"].join(status["blocos"][m.ibge] for m in subconjunto)
                + status["rodape"]
            )
            assert montado == texto_do_status(situacoes, SITE)

    assert total == 63
```

Se `atuais_de_teste()` criar valores só para alguns municípios, confira que ele cobre a lista toda. Ele lê `MUNICIPIOS`, então deve cobrir.

- [ ] **Passo 7: rodar a suíte inteira**

Rode `cd backend && python -m pytest -W error -q`. Tudo passa, inclusive `test_arquivo_versionado_tem_os_27_e_os_6_atuais_intactos`. O teste de fixture do Worker pode falhar porque o `bot.json` agora tem 27 municípios; se falhar, regenere com `VIGIA_REGERAR_FIXTURES=1 python -m pytest tests/test_bot_json.py -q` e rode a suíte de novo.

- [ ] **Passo 8: commit**

```bash
git add backend/scripts/gerar_municipios.py backend/tests/test_gerar_municipios.py backend/config/municipios.json backend/tests/test_config.py backend/tests/test_bot_json.py bot-worker/test/fixtures/bot.exemplo.json
git commit -m "feat(backend): 27 municípios do Alto Vale gerados da API do IBGE"
```

---

### Tarefa 3: grupos no `bot.json`

**Arquivos:**
- Modificar:
  - `backend/app/bot/mensagens.py`: novas constantes e funções de texto
  - `backend/app/exportacao/bot_json.py`: chaves `grupos`, `textos.opcao_voltar` e `textos.boas_vindas_grupos`
  - `docs/contratos-de-dados.md`: tabela do `bot.json` e do `municipios.json`
- Teste: `backend/tests/test_bot_json.py`
- Regerar: `bot-worker/test/fixtures/bot.exemplo.json`

**Interfaces:**
- Consome: `Municipio.microrregiao` (Tarefa 1).
- Produz, em `app.bot.mensagens`:
  - `OPCAO_VOLTAR = "Voltar"`
  - `rotulo_do_grupo(nome_micro: str) -> str`, que devolve `"Região de " + nome_micro`
  - `opcao_todos_do_grupo(nome_micro: str) -> str`, que devolve `"Todos da Região de " + nome_micro`
  - `texto_escolha_do_grupo(nome_micro: str) -> str`
  - `texto_boas_vindas_grupos() -> str`
- Produz no JSON:
  - `grupos: [{nome, municipios: [ibge], opcao_todos, escolha, confirmacao}]`, presente só quando todos os municípios têm `microrregiao`;
  - `textos.opcao_voltar` e `textos.boas_vindas_grupos`, nas mesmas condições.

- [ ] **Passo 1: escrever os testes que falham**

Acrescente a `backend/tests/test_bot_json.py`:

```python
import unicodedata

from app.bot.mensagens import OPCAO_VOLTAR, texto_boas_vindas_grupos


def _norm(texto: str) -> str:
    sem = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(sem.lower().split())


def test_grupos_na_ordem_do_codigo_da_microrregiao():
    dados = montar()
    grupos = dados["grupos"]
    assert [g["nome"] for g in grupos] == ["Região de Rio do Sul", "Região de Ituporanga"]
    assert sum(len(g["municipios"]) for g in grupos) == 27
    ordem = [m["ibge"] for m in dados["municipios"]]
    for g in grupos:
        assert g["municipios"] == [i for i in ordem if i in set(g["municipios"])]
        assert g["opcao_todos"] == f"Todos da {g['nome']}"


def test_textos_de_grupo():
    dados = montar()
    assert dados["textos"]["opcao_voltar"] == OPCAO_VOLTAR
    assert dados["textos"]["boas_vindas_grupos"] == texto_boas_vindas_grupos()
    ituporanga = dados["grupos"][1]
    nomes = {m["ibge"]: m["nome"] for m in dados["municipios"]}
    assert ituporanga["confirmacao"] == texto_inscricao_confirmada([nomes[i] for i in ituporanga["municipios"]])


def test_rotulos_de_botao_unicos_no_bot_json_inteiro():
    dados = montar()
    rotulos = [m["nome"] for m in dados["municipios"]]
    rotulos += [dados["textos"]["opcao_todos"], dados["textos"]["opcao_voltar"]]
    for g in dados["grupos"]:
        rotulos += [g["nome"], g["opcao_todos"]]
    normalizados = [_norm(r) for r in rotulos]
    assert len(normalizados) == len(set(normalizados))


def test_sem_microrregiao_nao_ha_grupos():
    sem = [dataclasses.replace(m, microrregiao=None) for m in MUNICIPIOS]
    dados = montar_bot_json(sem, {m.ibge: None for m in sem}, SITE, False, GERADO_EM)
    assert "grupos" not in dados
    assert "opcao_voltar" not in dados["textos"]
    assert "boas_vindas_grupos" not in dados["textos"]
```

Acrescente `import dataclasses` no topo, se não houver. Confira o nome real das constantes do arquivo (`SITE`, `GERADO_EM`, `montar`, `texto_inscricao_confirmada`) e ajuste os imports. Se `GERADO_EM` tiver outro nome, use o `datetime` com fuso que `montar()` já usa.

Atualize `test_campos_da_raiz_e_ordem_dos_municipios`: o conjunto de chaves esperado passa a incluir `"grupos"`.

- [ ] **Passo 2: rodar e ver falhar**

Rode `cd backend && python -m pytest -W error tests/test_bot_json.py -q`. Deve falhar com `ImportError: OPCAO_VOLTAR`.

- [ ] **Passo 3: implementar os textos**

Em `backend/app/bot/mensagens.py`, perto de `texto_boas_vindas`:

```python
#: Botão que volta do teclado de uma região para o das regiões.
OPCAO_VOLTAR = "Voltar"


def rotulo_do_grupo(nome_micro: str) -> str:
    """Botão da região. "Região de" evita colidir com o município homônimo (Rio do Sul)."""
    return f"Região de {nome_micro}"


def opcao_todos_do_grupo(nome_micro: str) -> str:
    return f"Todos da {rotulo_do_grupo(nome_micro)}"


def texto_escolha_do_grupo(nome_micro: str) -> str:
    rotulo = html.escape(rotulo_do_grupo(nome_micro))
    return (
        f"Municípios da {rotulo}. Toque em um deles, em "
        f"\"{html.escape(opcao_todos_do_grupo(nome_micro))}\" ou em \"{OPCAO_VOLTAR}\"."
    )


def texto_boas_vindas_grupos() -> str:
    """`/start` sem município quando o teclado é por região."""
    return (
        "Olá! Escolha a sua região para ver os municípios, "
        f"ou toque em \"{OPCAO_TODOS}\" para acompanhar todos.\n\n"
        "Use /status para ver a situação e /parar para cancelar."
    )
```

- [ ] **Passo 4: implementar no `bot_json.py`**

Importe `OPCAO_VOLTAR`, `opcao_todos_do_grupo`, `rotulo_do_grupo`, `texto_boas_vindas_grupos` e `texto_escolha_do_grupo`. Acrescente:

```python
def _grupos_em_json(municipios: list[Municipio]) -> list[dict] | None:
    """Um grupo por microrregião, na ordem do código; `None` se faltar microrregião."""
    if not municipios or any(m.microrregiao is None for m in municipios):
        return None
    codigos = sorted({m.microrregiao.codigo for m in municipios})
    grupos = []
    for codigo in codigos:
        membros = [m for m in municipios if m.microrregiao.codigo == codigo]
        nome = membros[0].microrregiao.nome
        grupos.append(
            {
                "nome": rotulo_do_grupo(nome),
                "municipios": [m.ibge for m in membros],
                "opcao_todos": opcao_todos_do_grupo(nome),
                "escolha": texto_escolha_do_grupo(nome),
                "confirmacao": texto_inscricao_confirmada([m.nome for m in membros]),
            }
        )
    return grupos
```

Em `montar_bot_json`, monte o dicionário numa variável `dados`. Antes do `return dados`:

```python
    grupos = _grupos_em_json(municipios)
    if grupos is not None:
        dados["grupos"] = grupos
        dados["textos"]["opcao_voltar"] = OPCAO_VOLTAR
        dados["textos"]["boas_vindas_grupos"] = texto_boas_vindas_grupos()
    return dados
```

- [ ] **Passo 5: regenerar a fixture e rodar**

```bash
cd backend && VIGIA_REGERAR_FIXTURES=1 python -m pytest -W error tests/test_bot_json.py -q
python -m pytest -W error -q
```

Tudo passa.

- [ ] **Passo 6: contrato**

Em `docs/contratos-de-dados.md`:
- na tabela do `municipios.json`, acrescente a linha `| microrregiao | objeto, opcional | {"codigo": 5 dígitos, "nome"}: microrregião IBGE; agrupa o teclado do bot |`;
- na tabela do `bot.json`, acrescente:
  - `| grupos | opcional: [{nome, municipios: [ibge], opcao_todos, escolha, confirmacao}] por microrregião, na ordem do código. Sem ele, o Worker mostra um botão por município |`
  - `| textos.opcao_voltar | opcional: botão que volta às regiões |`
  - `| textos.boas_vindas_grupos | opcional: /start sem município quando há grupos |`
- acrescente a frase "Todo rótulo de botão (municípios, "Todos", grupos, "Todos da Região…", "Voltar") é único no arquivo: o Worker reconhece o botão pelo texto."

- [ ] **Passo 7: commit**

```bash
git add backend/app/bot/mensagens.py backend/app/exportacao/bot_json.py backend/tests/test_bot_json.py bot-worker/test/fixtures/bot.exemplo.json docs/contratos-de-dados.md
git commit -m "feat(bot): grupos por microrregião no bot.json, com rótulos únicos"
```

---

### Tarefa 4: `/status` dividido no bot em Python

**Arquivos:**
- Modificar: `backend/app/bot/mensagens.py` (nova função) e `backend/app/bot/bot.py` (o handler do `/status`, perto da linha 131)
- Teste: `backend/tests/test_mensagens.py`

**Interfaces:**
- Produz:
  - `LIMITE_MENSAGEM_TELEGRAM = 4096`
  - `partes_do_status(situacoes, site_url, limite=LIMITE_MENSAGEM_TELEGRAM) -> list[str]`. Com uma parte só, o resultado é igual a `[texto_do_status(...)]`.

- [ ] **Passo 1: escrever os testes que falham**

Em `backend/tests/test_mensagens.py`:

```python
from app.bot.mensagens import LIMITE_MENSAGEM_TELEGRAM, partes_do_status


def _utf16(texto: str) -> int:
    return len(texto.encode("utf-16-le")) // 2


def test_partes_do_status_curto_e_igual_ao_texto():
    situacoes = [("Ibirama", None), ("Witmarsum", None)]
    assert partes_do_status(situacoes, "https://x") == [texto_do_status(situacoes, "https://x")]


def test_partes_do_status_sem_inscricao():
    assert partes_do_status([], "https://x") == [TEXTO_SEM_INSCRICAO]


def test_partes_do_status_divide_entre_blocos():
    situacoes = [(f"Município {i}", None) for i in range(27)]
    partes = partes_do_status(situacoes, "https://x", limite=200)
    assert len(partes) > 1
    assert all(_utf16(p) <= 200 for p in partes)
    blocos = [bloco_do_status(nome, None) for nome, _ in situacoes]
    juntas = "".join(partes)
    assert [juntas.find(b) for b in blocos] == sorted(juntas.find(b) for b in blocos)
    assert partes[0].startswith(CABECALHO_DO_STATUS)
    assert partes[-1].endswith(rodape_do_status("https://x"))
    assert LIMITE_MENSAGEM_TELEGRAM == 4096
```

Importe também `texto_do_status`, `TEXTO_SEM_INSCRICAO`, `bloco_do_status`, `CABECALHO_DO_STATUS` e `rodape_do_status`, se ainda não estiverem importados.

- [ ] **Passo 2: rodar e ver falhar**

Rode `cd backend && python -m pytest -W error tests/test_mensagens.py -q`. Deve falhar com `ImportError: partes_do_status`.

- [ ] **Passo 3: implementar**

Em `mensagens.py`, depois de `texto_do_status`:

```python
#: Limite do Telegram, em unidades UTF-16 (emoji conta 2).
LIMITE_MENSAGEM_TELEGRAM = 4096


def _tamanho(texto: str) -> int:
    return len(texto.encode("utf-16-le")) // 2


def partes_do_status(
    situacoes: list[tuple[str, IndiceAtual | None]],
    site_url: str,
    limite: int = LIMITE_MENSAGEM_TELEGRAM,
) -> list[str]:
    """`texto_do_status` em mensagens de até `limite`, cortando só entre blocos.

    Conta o HTML bruto, o que superestima (as tags somem no Telegram), ou seja,
    é seguro. O cabeçalho vai na primeira parte e o rodapé na última.
    """
    if not situacoes:
        return [TEXTO_SEM_INSCRICAO]
    cabecalho = CABECALHO_DO_STATUS + SEPARADOR_DO_STATUS
    rodape = SEPARADOR_DO_STATUS + rodape_do_status(site_url)
    partes: list[str] = []
    atual, vazia = cabecalho, True
    for nome, situacao in situacoes:
        bloco = bloco_do_status(nome, situacao)
        junto = atual + bloco if vazia else atual + SEPARADOR_DO_STATUS + bloco
        if not vazia and _tamanho(junto) + _tamanho(rodape) > limite:
            partes.append(atual)
            atual = bloco
        else:
            atual = junto
        vazia = False
    partes.append(atual + rodape)
    return partes
```

Em `bot.py`, no handler do `/status`, troque o `reply_text(texto_do_status(...))` por:

```python
    for parte in partes_do_status(situacoes, config.site_url):
        await update.message.reply_text(parte, parse_mode=ParseMode.HTML)
```

Ajuste o import de `texto_do_status` para `partes_do_status`. Se `texto_do_status` ficar sem uso em `bot.py`, remova o import de lá.

- [ ] **Passo 4: rodar**

Rode `cd backend && python -m pytest -W error -q`. Tudo passa. Se `test_bot.py` conferir uma resposta única ao `/status`, ela continua igual, porque com poucos municípios sai uma parte só.

- [ ] **Passo 5: commit**

```bash
git add backend/app/bot/mensagens.py backend/app/bot/bot.py backend/tests/test_mensagens.py
git commit -m "feat(bot): /status em mais de uma mensagem quando passa do limite do Telegram"
```

---

### Tarefa 5: avisos que esperam o Telegram (429) em vez de se perder

**Arquivos:**
- Modificar: `backend/app/bot/avisos.py`
- Teste: `backend/tests/test_avisos.py`

**Interfaces:**
- Produz, em `app.bot.avisos`:
  - `PAUSA_ENTRE_ENVIOS_S = 0.05`
  - `ESPERA_MAXIMA_S = 60`
  - `_dormir`, uma referência para `asyncio.sleep` que os testes trocam

- [ ] **Passo 1: escrever o teste que falha**

Em `backend/tests/test_avisos.py`:

```python
import warnings
from datetime import timedelta

from telegram.error import RetryAfter
from telegram.warnings import PTBDeprecationWarning

from app.bot import avisos as modulo_avisos


def _retry_after(segundos: int) -> RetryAfter:
    # A 22.x avisa que retry_after vai virar timedelta; com -W error isso viraria erro.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PTBDeprecationWarning)
        return RetryAfter(timedelta(seconds=segundos))


class BotQueLimitaUmaVez(BotFalso):
    def __init__(self):
        super().__init__()
        self.limitou = False

    async def send_message(self, chat_id, text, parse_mode=None, **_):
        if not self.limitou:
            self.limitou = True
            raise _retry_after(3)
        await super().send_message(chat_id, text, parse_mode)


def test_retry_after_espera_e_reenvia(monkeypatch):
    esperas: list[float] = []

    async def dormir(segundos):
        esperas.append(segundos)

    monkeypatch.setattr(modulo_avisos, "_dormir", dormir)
    conn = conexao()
    inscritos = InscritosSqlite(conn)
    inscritos.inscrever(10, "4206900", AGORA)
    bot = BotQueLimitaUmaVez()

    asyncio.run(enviar_avisos(bot, conn, inscritos, [aviso()], AGORA, SITE_URL))

    assert [c for c, _ in bot.enviados] == [10]
    assert 3 in esperas
    assert banco.ultima_classe_notificada(conn, "4206900") == 4
```

Confira os nomes reais da API de `InscritosSqlite` (método de inscrição) e da leitura da última classe notificada em `app.modelos.banco`, olhando os testes vizinhos do arquivo, e ajuste as duas chamadas para os mesmos nomes que eles usam.

- [ ] **Passo 2: rodar e ver falhar**

Rode `cd backend && python -m pytest -W error tests/test_avisos.py -q`. Deve falhar com `AttributeError: _dormir`, ou porque o chat 10 não recebeu.

- [ ] **Passo 3: implementar**

Em `avisos.py`:

```python
import asyncio
import warnings
from datetime import timedelta

from telegram.error import Forbidden, RetryAfter, TelegramError
from telegram.warnings import PTBDeprecationWarning

#: Espaço mínimo entre dois envios: o Telegram aceita ~30 msg/s no total.
PAUSA_ENTRE_ENVIOS_S = 0.05
#: Teto da espera pedida pelo Telegram num 429.
ESPERA_MAXIMA_S = 60

_dormir = asyncio.sleep


def _segundos_de_espera(erro: RetryAfter) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PTBDeprecationWarning)
        espera = erro.retry_after
    segundos = espera.total_seconds() if isinstance(espera, timedelta) else float(espera)
    return min(max(segundos, 0.0), ESPERA_MAXIMA_S)


async def _enviar(bot, chat_id: int, texto: str) -> None:
    """Envia; num 429 espera o que o Telegram pediu e tenta uma vez mais."""
    try:
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode=ParseMode.HTML)
    except RetryAfter as erro:
        await _dormir(_segundos_de_espera(erro))
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode=ParseMode.HTML)
```

Em `_enviar_para_um_municipio`:
- troque `await bot.send_message(...)` por `await _enviar(bot, chat_id, texto)`;
- no início do corpo do `for`, antes do `try`, acrescente `await _dormir(PAUSA_ENTRE_ENVIOS_S)`.

O `except TelegramError` que já existe continua pegando a segunda falha, porque `RetryAfter` herda de `TelegramError`, e a registra como transitória.

- [ ] **Passo 4: deixar os testes antigos rápidos**

No topo de `test_avisos.py`, depois dos imports:

```python
@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    async def nada(_segundos):
        return None

    monkeypatch.setattr(modulo_avisos, "_dormir", nada)
```

O teste novo sobrescreve com o próprio `dormir`, porque o `monkeypatch.setattr` dentro do teste roda depois da fixture.

- [ ] **Passo 5: rodar**

Rode `cd backend && python -m pytest -W error -q`. Tudo passa.

- [ ] **Passo 6: commit**

```bash
git add backend/app/bot/avisos.py backend/tests/test_avisos.py
git commit -m "fix(bot): aviso espera o limite do Telegram (429) e tenta de novo em vez de se perder"
```

---

### Tarefa 6: Worker com teclado por região e `/status` dividido

**Arquivos:**
- Modificar:
  - `bot-worker/src/tipos.ts`: campos opcionais
  - `bot-worker/src/telegram.ts`: tipo `Teclado`, `enviarMensagem` e `partesDoStatus`
  - `bot-worker/src/comandos.ts`: fluxo
- Criar: `bot-worker/src/teclados.ts`
- Teste:
  - `bot-worker/test/apoio.ts`: nova função `botJsonComGrupos()`
  - `bot-worker/test/telegram.test.ts`

**Interfaces:**
- Consome, do `bot.json` (Tarefa 3): `grupos`, `textos.opcao_voltar` e `textos.boas_vindas_grupos`.
- Produz:
  - `type Grupo = { nome: string; municipios: string[]; opcao_todos: string; escolha: string; confirmacao: string }`
  - `type Teclado = "municipios" | "remover" | "nenhum" | { linhas: string[][] }`
  - `tecladoInicial(bot: BotJson, sugerido?: string): string[][]`
  - `tecladoDoGrupo(bot: BotJson, grupo: Grupo): string[][]`
  - `partesDoStatus(bot: BotJson, ibges: string[], limite?: number): string[]`

- [ ] **Passo 1: tipos**

Em `tipos.ts`, acrescente acima de `BotJson`:

```ts
export type Grupo = {
  nome: string;
  municipios: string[];
  opcao_todos: string;
  escolha: string;
  confirmacao: string;
};
```

Dentro de `BotJson`:
- acrescente `grupos?: Grupo[];` depois de `municipios`;
- em `textos`, acrescente `opcao_voltar?: string;` e `boas_vindas_grupos?: string;`.

- [ ] **Passo 2: escrever os testes que falham**

Em `test/apoio.ts`:

```ts
export function botJsonComGrupos(): BotJson {
  const bot = botJsonDeTeste();
  bot.municipios.push({ ibge: "4208500", nome: "Ituporanga" });
  bot.textos.inscricao_confirmada["4208500"] = "Inscrito em Ituporanga.";
  bot.textos.boas_vindas_sugerido["4208500"] = "Bem-vindo ao VIGIA. Quer Ituporanga?";
  bot.status.blocos["4208500"] = "Ituporanga: baixo";
  bot.textos.opcao_voltar = "Voltar";
  bot.textos.boas_vindas_grupos = "Escolha a região.";
  bot.grupos = [
    { nome: "Região de Rio do Sul", municipios: ["4208203", "4128104"], opcao_todos: "Todos da Região de Rio do Sul", escolha: "Municípios de Rio do Sul.", confirmacao: "Inscrito na região de Rio do Sul." },
    { nome: "Região de Ituporanga", municipios: ["4208500"], opcao_todos: "Todos da Região de Ituporanga", escolha: "Municípios de Ituporanga.", confirmacao: "Inscrito na região de Ituporanga." },
  ];
  return bot;
}
```

Em `test/telegram.test.ts`, importe `botJsonComGrupos` e `partesDoStatus` e acrescente:

```ts
const teclado = (linhas: string[][]) => ({
  keyboard: linhas.map((l) => l.map((text) => ({ text }))),
  resize_keyboard: true,
  one_time_keyboard: true,
});

describe("com grupos", () => {
  beforeEach(() => {
    botJson = botJsonComGrupos();
  });

  it("/start mostra as regiões e Todos", async () => {
    await enviar(mensagem("/start"));
    expect(envios[0]!.text).toBe("Escolha a região.");
    expect(envios[0]!.reply_markup).toEqual(teclado([["Região de Rio do Sul"], ["Região de Ituporanga"], ["Todos"]]));
  });

  it("/start com sugerido põe o município na primeira linha", async () => {
    await enviar(mensagem("/start 4208500"));
    expect(envios[0]!.text).toBe("Bem-vindo ao VIGIA. Quer Ituporanga?");
    expect(envios[0]!.reply_markup).toEqual(
      teclado([["Ituporanga"], ["Região de Rio do Sul"], ["Região de Ituporanga"], ["Todos"]]),
    );
  });

  it("região mostra os municípios em duas colunas, Todos da região e Voltar", async () => {
    await enviar(mensagem("Região de Rio do Sul"));
    expect(envios[0]!.text).toBe("Municípios de Rio do Sul.");
    expect(envios[0]!.reply_markup).toEqual(
      teclado([["Ibirama", "Witmarsum"], ["Todos da Região de Rio do Sul"], ["Voltar"]]),
    );
    expect(await ibgesDoChat(env.DB, CHAT)).toEqual([]);
  });

  it("Todos da região inscreve só nela", async () => {
    await enviar(mensagem("Todos da Região de Rio do Sul"));
    expect(envios[0]!.text).toBe("Inscrito na região de Rio do Sul.");
    expect((await ibgesDoChat(env.DB, CHAT)).sort()).toEqual(["4128104", "4208203"]);
  });

  it("Todos inscreve nos três", async () => {
    await enviar(mensagem("Todos"));
    expect((await ibgesDoChat(env.DB, CHAT)).sort()).toEqual(["4128104", "4208203", "4208500"]);
  });

  it("Voltar e opção desconhecida mostram as regiões", async () => {
    await enviar(mensagem("Voltar"));
    await enviar(mensagem("qualquer coisa"));
    for (const e of envios) {
      expect(e.reply_markup).toEqual(teclado([["Região de Rio do Sul"], ["Região de Ituporanga"], ["Todos"]]));
    }
  });

  it("nome digitado sem acento e em minúsculas inscreve", async () => {
    await enviar(mensagem("  ituporanga "));
    expect(await ibgesDoChat(env.DB, CHAT)).toEqual(["4208500"]);
  });

  it("inscrito antigo continua com os seus", async () => {
    await inscrever(env.DB, CHAT, ["4208203"], new Date());
    await enviar(mensagem("/status"));
    expect(envios[0]!.text).toContain("Ibirama: baixo");
    expect(envios[0]!.text).not.toContain("Ituporanga");
  });
});

it("sem grupos, um botão de região antigo cai em opcao_desconhecida sem inscrever", async () => {
  await enviar(mensagem("Região de Rio do Sul"));
  expect(envios[0]!.text).toBe("Não entendi.");
  expect(envios[0]!.reply_markup).toEqual(TECLADO_MUNICIPIOS);
  expect(await ibgesDoChat(env.DB, CHAT)).toEqual([]);
});

it("partesDoStatus corta só entre blocos e respeita o limite", () => {
  const bot = botJsonDeTeste();
  const ibges: string[] = [];
  for (let i = 0; i < 27; i++) {
    const ibge = String(4200000 + i);
    bot.municipios.push({ ibge, nome: `M${i}` });
    bot.status.blocos[ibge] = `Bloco ${i} ${"x".repeat(40)}`;
    ibges.push(ibge);
  }
  const partes = partesDoStatus(bot, ibges, 200);
  expect(partes.length).toBeGreaterThan(1);
  expect(partes.every((p) => p.length <= 200)).toBe(true);
  expect(partes[0]!.startsWith(bot.status.cabecalho)).toBe(true);
  expect(partes.at(-1)!.endsWith(bot.status.rodape)).toBe(true);
  for (let i = 0; i < 27; i++) expect(partes.join("")).toContain(`Bloco ${i} `);
});
```

- [ ] **Passo 3: rodar e ver falhar**

Rode `cd bot-worker && npm test`. Os testes novos falham.

- [ ] **Passo 4: implementar os teclados**

Crie `bot-worker/src/teclados.ts`:

```ts
import type { BotJson, Grupo } from "./tipos";

/** Primeiro teclado: com grupos, as regiões (e o sugerido na frente); sem grupos, um botão por município. */
export function tecladoInicial(bot: BotJson, sugerido?: string): string[][] {
  const todos = [bot.textos.opcao_todos];
  if (!bot.grupos?.length) return [...bot.municipios.map((m) => [m.nome]), todos];
  const nome = sugerido ? bot.municipios.find((m) => m.ibge === sugerido)?.nome : undefined;
  return [...(nome ? [[nome]] : []), ...bot.grupos.map((g) => [g.nome]), todos];
}

/** Municípios do grupo em duas colunas, "Todos da Região…" e "Voltar". */
export function tecladoDoGrupo(bot: BotJson, grupo: Grupo): string[][] {
  const nomes = grupo.municipios.flatMap((i) => bot.municipios.find((m) => m.ibge === i)?.nome ?? []);
  const linhas: string[][] = [];
  for (let i = 0; i < nomes.length; i += 2) linhas.push(nomes.slice(i, i + 2));
  return [...linhas, [grupo.opcao_todos], [bot.textos.opcao_voltar ?? "Voltar"]];
}
```

Em `telegram.ts`:
- troque o tipo para `export type Teclado = "municipios" | "remover" | "nenhum" | { linhas: string[][] };`;
- em `enviarMensagem`, troque o bloco do teclado por:

```ts
  const linhas = typeof teclado === "object" ? teclado.linhas : teclado === "municipios" && bot ? tecladoInicial(bot) : null;
  if (linhas) {
    corpo.reply_markup = {
      keyboard: linhas.map((l) => l.map((text) => ({ text }))),
      resize_keyboard: true,
      one_time_keyboard: true,
    };
  } else if (teclado === "remover") {
    corpo.reply_markup = { remove_keyboard: true };
  }
```

Importe `tecladoInicial` de `./teclados`. Depois de `textoDoStatus`, acrescente:

```ts
export const LIMITE_MENSAGEM_TELEGRAM = 4096;

/** `/status` em mensagens de até `limite` (comprimento JS do HTML bruto: superestima, é seguro). */
export function partesDoStatus(bot: BotJson, ibges: string[], limite = LIMITE_MENSAGEM_TELEGRAM): string[] {
  const inscritos = new Set(ibges);
  const blocos = bot.municipios
    .filter((m) => inscritos.has(m.ibge) && bot.status.blocos[m.ibge] !== undefined)
    .map((m) => bot.status.blocos[m.ibge]!);
  if (blocos.length === 0) return [bot.status.sem_inscricao];
  const { cabecalho, separador, rodape } = bot.status;
  const partes: string[] = [];
  let atual = cabecalho;
  let vazia = true;
  for (const bloco of blocos) {
    const junto = vazia ? atual + bloco : atual + separador + bloco;
    if (!vazia && junto.length + rodape.length > limite) {
      partes.push(atual);
      atual = bloco;
    } else {
      atual = junto;
    }
    vazia = false;
  }
  partes.push(atual + rodape);
  return partes;
}
```

- [ ] **Passo 5: implementar o fluxo**

Em `comandos.ts`, importe `tecladoDoGrupo` e `tecladoInicial` de `./teclados` e `partesDoStatus` de `./telegram`. Troque o bloco `if (comando === null) { ... }` por:

```ts
  if (comando === null) {
    const nome = normalizarNome(texto);
    if (nome === normalizarNome(t.opcao_todos)) {
      await inscrever(env.DB, chatId, bot.municipios.map((m) => m.ibge), new Date());
      await enviarMensagem(env, chatId, t.inscricao_confirmada_todos, "remover");
      return;
    }
    const grupos = bot.grupos ?? [];
    const grupo = grupos.find((g) => normalizarNome(g.nome) === nome);
    if (grupo) {
      await enviarMensagem(env, chatId, grupo.escolha, { linhas: tecladoDoGrupo(bot, grupo) });
      return;
    }
    const todosDoGrupo = grupos.find((g) => normalizarNome(g.opcao_todos) === nome);
    if (todosDoGrupo) {
      await inscrever(env.DB, chatId, todosDoGrupo.municipios, new Date());
      await enviarMensagem(env, chatId, todosDoGrupo.confirmacao, "remover");
      return;
    }
    if (grupos.length && t.opcao_voltar && nome === normalizarNome(t.opcao_voltar)) {
      await enviarMensagem(env, chatId, t.boas_vindas_grupos ?? t.boas_vindas, "municipios", bot);
      return;
    }
    const municipio = bot.municipios.find((m) => normalizarNome(m.nome) === nome);
    if (municipio) {
      await inscrever(env.DB, chatId, [municipio.ibge], new Date());
      await enviarMensagem(env, chatId, t.inscricao_confirmada[municipio.ibge] ?? "", "remover");
      return;
    }
  } else if (comando.comando === "start") {
```

E troque o corpo do `start` por:

```ts
    const codigo = comando.args[0] ?? "";
    const sugerido = Object.hasOwn(t.boas_vindas_sugerido, codigo) ? t.boas_vindas_sugerido[codigo] : undefined;
    const semSugerido = bot.grupos?.length ? (t.boas_vindas_grupos ?? t.boas_vindas) : t.boas_vindas;
    await enviarMensagem(env, chatId, sugerido ?? semSugerido, { linhas: tecladoInicial(bot, sugerido ? codigo : undefined) });
    return;
```

E o do `status` por:

```ts
    const ibges = await ibgesDoChat(env.DB, chatId);
    for (const parte of partesDoStatus(bot, ibges)) await enviarMensagem(env, chatId, parte, "nenhum");
    return;
```

- [ ] **Passo 6: rodar**

Rode `cd bot-worker && npm test && npm run typecheck`. Tudo passa, inclusive os testes antigos sem grupos. O teste do teclado `TECLADO_MUNICIPIOS` continua igual, porque `tecladoInicial` sem grupos produz o teclado de hoje.

- [ ] **Passo 7: commit**

```bash
git add bot-worker/src bot-worker/test
git commit -m "feat(worker): teclado por região, nomes normalizados e /status dividido"
```

---

### Tarefa 7: GeoJSON dos 27 lido da configuração

**Arquivos:**
- Modificar: `frontend/scripts/gerar-geojson.mjs`
- Modificar: `frontend/src/data/municipios.geojson`, gerado
- Teste: `frontend/src/lib/mapa.test.ts`

**Interfaces:**
- Consome: `backend/config/municipios.json` (Tarefa 2).
- Produz: o GeoJSON com 27 municípios monitorados mais os vizinhos, todos `Polygon`.

- [ ] **Passo 1: escrever os testes que falham**

Em `frontend/src/lib/mapa.test.ts`, troque o teste "os 6 municípios monitorados do GeoJSON ficam no Alto Vale" por:

```ts
it("os 27 municípios monitorados do GeoJSON enquadram o Alto Vale", () => {
  const fs = FEICOES;
  expect(fs.filter((f) => f.properties.monitorado)).toHaveLength(27);
  const [[s, o], [n, l]] = limites(fs);
  expect(s).toBeCloseTo(-27.66, 1);
  expect(o).toBeCloseTo(-50.35, 1);
  expect(l).toBeCloseTo(-49.19, 1);
  expect(n).toBeLessThan(-26.4);
});

it("o GeoJSON não passa de 150 KB e só tem Polygon", () => {
  expect(geojsonBruto.length).toBeLessThan(150_000);
  expect(FEICOES.every((f) => (f as { geometry: { type: string } }).geometry.type === "Polygon")).toBe(true);
});
```

Acrescente `import geojsonBruto from "../data/municipios.geojson?raw";` no topo. No teste de `municipiosMonitorados`, troque `toHaveLength(6)` por `toHaveLength(27)` e o primeiro item esperado por `{ ibge: "4200200", nome: "Agrolândia" }`. Confira o código IBGE no `municipios.json` gerado.

- [ ] **Passo 2: rodar e ver falhar**

Rode `cd frontend && npx vitest run src/lib/mapa.test.ts`. Deve falhar com 6 em vez de 27.

- [ ] **Passo 3: implementar**

Em `frontend/scripts/gerar-geojson.mjs`:
- troque o comentário da linha 1 por `// Gera src/data/municipios.geojson: os municípios de backend/config/municipios.json e os vizinhos que encostam neles,`;
- troque a linha `const MONITORADOS = [...]` por:

```js
import { readFileSync } from "node:fs";
const CONFIG = new URL("../../backend/config/municipios.json", import.meta.url);
const MONITORADOS = JSON.parse(readFileSync(CONFIG, "utf-8")).map((m) => m.ibge);
```

Junte o `readFileSync` ao `import { writeFileSync }` que já existe. Depois de `if (nucleo.length !== MONITORADOS.length) throw ...`, acrescente:

```js
const multi = nucleo.filter((f) => f.geometry.type !== "Polygon").map((f) => f.properties.id);
if (multi.length) throw new Error(`Monitorado sem Polygon simples (o mapa não trata MultiPolygon): ${multi.join(", ")}`);
```

- [ ] **Passo 4: gerar (com rede) e rodar**

```bash
cd frontend && npm run gerar:geojson
npx vitest run && npm run typecheck
```

Os 27 aparecem marcados com `*` na saída, e os testes passam. Anote o tamanho do arquivo (`wc -c src/data/municipios.geojson`) para a descrição do PR.

- [ ] **Passo 5: commit**

```bash
git add frontend/scripts/gerar-geojson.mjs frontend/src/data/municipios.geojson frontend/src/lib/mapa.test.ts
git commit -m "feat(frontend): GeoJSON dos 27 municípios lido da configuração do backend"
```

---

### Tarefa 8: rótulos do mapa por zoom (selecionado e em alerta)

**Arquivos:**
- Modificar: `frontend/src/lib/mapa.ts` (nova função), `frontend/src/components/MapaLeaflet.tsx` (efeito de `Municipio`) e `frontend/src/styles/mapa.css`
- Teste: `frontend/src/lib/mapa.test.ts`

**Interfaces:**
- Produz: `classesDoRotulo(selecionado: boolean, valor: Valor): { sel: boolean; alerta: boolean }`

- [ ] **Passo 1: escrever o teste que falha**

```ts
import { classesDoRotulo } from "./mapa";

describe("classesDoRotulo", () => {
  it("selecionado e alerta (índice ≥ 1)", () => {
    expect(classesDoRotulo(true, { indice: 0.2, classe: 1 })).toEqual({ sel: true, alerta: false });
    expect(classesDoRotulo(false, { indice: 1.0, classe: 4 })).toEqual({ sel: false, alerta: true });
    expect(classesDoRotulo(false, null)).toEqual({ sel: false, alerta: false });
    expect(classesDoRotulo(false, undefined)).toEqual({ sel: false, alerta: false });
  });
});
```

- [ ] **Passo 2: rodar e ver falhar**

Rode `cd frontend && npx vitest run src/lib/mapa.test.ts`. Deve falhar porque a função não existe.

- [ ] **Passo 3: implementar**

Em `lib/mapa.ts`, importe `emAlerta` de `./classes` e acrescente:

```ts
/** Classes do rótulo: de longe (zoom < 8,5) só aparecem o selecionado e os em alerta (mapa.css). */
export const classesDoRotulo = (selecionado: boolean, valor: Valor): { sel: boolean; alerta: boolean } => ({
  sel: selecionado,
  alerta: valor ? emAlerta(valor.indice) : false,
});
```

Em `MapaLeaflet.tsx`, importe `classesDoRotulo`. No segundo `useEffect` de `Municipio`, logo depois de `el.classList.toggle("sel", selecionado);`:

```tsx
    const rotulo = fundo.current?.getTooltip()?.getElement();
    const classes = classesDoRotulo(selecionado, valor);
    rotulo?.classList.toggle("sel", classes.sel);
    rotulo?.classList.toggle("alerta", classes.alerta);
```

Em `mapa.css`, perto das regras de `.leaflet-tooltip.mlabel`:

```css
/* De longe (zoom < 8,5) os 27 nomes se sobrepõem: ficam o selecionado e os em alerta. */
.mapa.longe .leaflet-tooltip.mlabel:not(.sel):not(.alerta),
.mapa.longe .leaflet-tooltip.ctxl {
  display: none;
}
```

- [ ] **Passo 4: rodar**

Rode `cd frontend && npm test && npm run typecheck`. Tudo passa.

- [ ] **Passo 5: conferir no navegador**

Rode `cd frontend && npx astro dev --port 4330` e confira `/`, `/simulacao/` e `/estacoes/` em 320×568, 390×844 e 1366×768:
- de longe, aparecem só o selecionado e os em alerta;
- ao aproximar (botão +), aparecem todos;
- não há rolagem horizontal.

Se no desktop o zoom inicial ficar acima de 8,5 e os 27 rótulos se sobrepuserem, suba o limiar em `MapaLeaflet.tsx` (`mapa.getZoom() < 8.5`) e no comentário de `estacoes.css` para o menor valor em que não há sobreposição, e registre o valor no commit.

- [ ] **Passo 6: commit**

```bash
git add frontend/src/lib/mapa.ts frontend/src/lib/mapa.test.ts frontend/src/components/MapaLeaflet.tsx frontend/src/styles/mapa.css
git commit -m "feat(frontend): de longe, só os rótulos do selecionado e dos em alerta"
```

---

### Tarefa 9: Evolução com faixa dos demais e seletor de município

**Arquivos:**
- Modificar: `frontend/src/lib/graficos.ts`, `frontend/src/lib/graficos.test.ts`, `frontend/src/components/Graficos.tsx` e `frontend/src/styles/dados.css`
- Modificar: `frontend/src/i18n/es.json` e `en.json`

**Interfaces:**
- Produz:
  - `faixaDosDemais(municipios: Municipio[], destaque: string, eixo: readonly string[]): ({ min: number; max: number } | null)[]`, com um item por dia do eixo
- Remove `vizinhoCiclico`, que só era usado pelas abas.

- [ ] **Passo 1: escrever o teste que falha**

Em `graficos.test.ts`:

```ts
import { faixaDosDemais } from "./graficos";

describe("faixaDosDemais", () => {
  it("mínimo e máximo por dia só com quem tem dado; menos de 2 vira null", () => {
    const eixo = ["2026-10-01", "2026-10-02"];
    const mk = (ibge: string, hist: [string, number][]) =>
      ({ ibge, nome: ibge, historico: hist.map(([dia_alvo, indice]) => ({ dia_alvo, indice, classe: 1 })), dias: [] }) as unknown as Municipio;
    const ms = [
      mk("A", [["2026-10-01", 0.5], ["2026-10-02", 0.9]]),
      mk("B", [["2026-10-01", 0.2], ["2026-10-02", 0.4]]),
      mk("C", [["2026-10-01", 0.7]]),
    ];
    expect(faixaDosDemais(ms, "A", eixo)).toEqual([{ min: 0.2, max: 0.7 }, null]);
  });
});
```

Importe o tipo `Municipio` de `./tipos`, se o arquivo ainda não importa.

- [ ] **Passo 2: rodar e ver falhar**

Rode `cd frontend && npx vitest run src/lib/graficos.test.ts`.

- [ ] **Passo 3: implementar a função e remover `vizinhoCiclico`**

Em `graficos.ts`, apague `vizinhoCiclico` e o teste dele em `graficos.test.ts`. Acrescente:

```ts
/** Faixa dos demais municípios por dia do eixo (mín–máx de quem tem dado); `null` com menos de 2. */
export function faixaDosDemais(municipios: Municipio[], destaque: string, eixo: readonly string[]): ({ min: number; max: number } | null)[] {
  const series = municipios.filter((m) => m.ibge !== destaque).map((m) => serieMunicipio(m, eixo));
  return eixo.map((dia) => {
    const valores = series.flatMap((s) => s.filter((p) => p.dia_alvo === dia).map((p) => p.indice));
    return valores.length < 2 ? null : { min: Math.min(...valores), max: Math.max(...valores) };
  });
}
```

- [ ] **Passo 4: usar no componente**

Em `Graficos.tsx`:

1. Tire `vizinhoCiclico` dos imports e acrescente `faixaDosDemais`. Apague o `useRef` `chips` e a função `teclado`.
2. Troque o `<div className="pick" role="tablist" ...>…</div>` por:

```tsx
      <label className="pick">
        <span className="sr-only">{t("Município")}</span>
        <select value={ibge} onChange={(e) => aoSelecionar(e.target.value)}>
          {municipios.map((m) => (
            <option key={m.ibge} value={m.ibge}>
              {m.nome}
            </option>
          ))}
        </select>
      </label>
```

3. No `<div ref={painel} className="evo-svg" ...>`, apague `id="evo-painel"`, `role="tabpanel"` e `aria-labelledby={...}`, e acrescente `aria-label={rotulo}`.
4. Depois de `const faixas = faixasClasse(max);`, acrescente:

```tsx
  const faixa = faixaDosDemais(municipios, ibge, eixo);
  // Trechos contínuos de dias com faixa: um polígono por trecho (contorno de cima, depois o de baixo de volta).
  const trechos: number[][] = [];
  faixa.forEach((f, i) => {
    if (!f) return;
    const ultimo = trechos.at(-1);
    if (ultimo && ultimo.at(-1) === i - 1) ultimo.push(i);
    else trechos.push([i]);
  });
```

5. Troque o bloco `{series.filter((s) => s.m.ibge !== ibge).map(... className="other" ...)}` por:

```tsx
          {trechos.map((tr) => (
            <polygon
              key={tr[0]}
              className="faixa"
              points={[...tr.map((i) => `${xs[i]},${y(faixa[i]!.max)}`), ...[...tr].reverse().map((i) => `${xs[i]},${y(faixa[i]!.min)}`)].join(" ")}
            />
          ))}
```

Um trecho de um dia só vira um polígono degenerado, uma linha vertical. Isso é aceitável e mostra o intervalo daquele dia.

6. Troque o cálculo de `leitura` e a lista da `.dica`. Mantenha o item do destaque (`li.eu`) e, no lugar dos outros `li`, acrescente:

```tsx
              {foco !== null && faixa[foco] && (
                <li>
                  <i aria-hidden="true" />
                  <b className="num">
                    {formatarIndice(faixa[foco]!.min)}–{formatarIndice(faixa[foco]!.max)}
                  </b>
                  <span>{t("demais municípios")}</span>
                </li>
              )}
```

O `leitura` passa a ter só o destaque: `series.filter(({ m }) => m.ibge === ibge)` em vez de todos. Ajuste o `sort`, que deixa de ser necessário.

7. Logo antes da `<div className="sr-only">` da tabela, acrescente o comentário `{/* Só o município em destaque: a faixa dos demais é visual (ver a legenda). */}`.
8. Atualize o comentário do componente: "Evolução do índice (RF06): faixas das classes, linha de alerta, faixa mínimo–máximo dos demais municípios e o destaque."

Em `dados.css`, troque a regra `.evo .other { … }` por:

```css
.evo .faixa {
  fill: var(--muted);
  opacity: 0.18;
  stroke: none;
}
```

Troque as regras de `.evo .pick button` (perto das linhas 188, 198 e 719) por regras para o `select`:

```css
.evo .pick select {
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-md);
  background: var(--surface-000);
  color: var(--ink);
  font-size: 14px;
}
```

Apague `.evo .pick button[aria-selected="true"]`. Confira se a legenda do gráfico está em `Dados.tsx` ou no próprio componente (procure `"↑/↓ mudança de classe"`) e acrescente lá um item com `t("faixa: mínimo e máximo dos demais municípios")`.

9. Em `es.json` e `en.json`, acrescente:
   - `"demais municípios": "demás municipios"` (ES) e `"other municipalities"` (EN)
   - `"faixa: mínimo e máximo dos demais municípios": "franja: mínimo y máximo de los demás municipios"` (ES) e `"band: minimum and maximum of the other municipalities"` (EN)

- [ ] **Passo 5: rodar**

Rode `cd frontend && npm test && npm run typecheck && npm run build`. Tudo passa, inclusive o teste de que toda frase `t("…")` existe no `es.json`.

- [ ] **Passo 6: commit**

```bash
git add frontend/src/lib/graficos.ts frontend/src/lib/graficos.test.ts frontend/src/components/Graficos.tsx frontend/src/styles/dados.css frontend/src/i18n/es.json frontend/src/i18n/en.json
git commit -m "feat(frontend): Evolução com faixa dos demais municípios e seletor no lugar das abas"
```

---

### Tarefa 10: textos do site (histórico por município, cabeçalho, janela do Telegram e Estações)

**Arquivos:**
- Modificar:
  - `frontend/src/components/Dados.tsx` (linhas 63 e 81)
  - `frontend/src/components/Cabecalho.tsx` (linha 56)
  - `frontend/src/components/JanelaTelegram.tsx` (linhas 91 a 95)
  - `frontend/src/components/Estacoes.tsx` (linha 56)
  - `frontend/src/i18n/es.json` e `en.json`
- Teste: `frontend/src/lib/graficos.test.ts`, se `diasComDados` deixar de ser usada

- [ ] **Passo 1: histórico por município**

Em `Dados.tsx`:
- troque `const comHistorico = diasComDados(indices, eixo);` por `const comHistorico = serieMunicipio(destaque, eixo).length;`. Confirme que `destaque` já está definido antes dessa linha; se não estiver, mova a linha para depois dele;
- troque o parágrafo por:

```tsx
{comHistorico < periodo && <p>{t("Por enquanto há histórico de {N} dias para {M}; os demais aparecem vazios.", { N: String(comHistorico), M: destaque.nome })}</p>}
```

Se `diasComDados` ficar sem uso, apague a função de `graficos.ts`, o teste dela e o import em `Dados.tsx`.

- [ ] **Passo 2: cabeçalho, janela do Telegram e Estações**

- Em `Cabecalho.tsx`, troque `t("Vale Norte — Alto Vale do Itajaí, SC")` por `t("Alto Vale do Itajaí, SC")`.
- Em `JanelaTelegram.tsx`, troque o `.tgm-kb` por:

```tsx
          <div className="tgm-kb">
            <span>{t("Região de Rio do Sul")}</span>
            <span>{t("Região de Ituporanga")}</span>
            <span className="all">{t("Todos")}</span>
          </div>
```

  Se a prop `municipios` ficar sem uso, remova-a do componente e de quem o chama (procure por `<JanelaTelegram`).
- Em `Estacoes.tsx`, troque o texto da linha 56 por: `"Estações automáticas do INMET na região e em volta dela. Cada uma mostra a distância até o centro do município de referência; algumas ficam dentro dos municípios monitorados. Toque num pin ou na lista para localizar."`

- [ ] **Passo 3: dicionários**

Em `es.json` e `en.json`:

| Ação | Chave |
|---|---|
| remover | `"Vale Norte — Alto Vale do Itajaí, SC"` |
| remover | `"Por enquanto há histórico de {N} dias; os demais aparecem vazios."` |
| remover | o texto antigo de Estações, "…Nenhuma fica dentro deles…" |
| acrescentar | as traduções abaixo |

Traduções:
- `"Alto Vale do Itajaí, SC"` → ES e EN `"Alto Vale do Itajaí, SC"`
- `"Por enquanto há histórico de {N} dias para {M}; os demais aparecem vazios."` → ES `"Por ahora hay historial de {N} días para {M}; los demás aparecen vacíos."`, EN `"For now there are {N} days of history for {M}; the other days are empty."`
- `"Região de Rio do Sul"` → ES `"Región de Rio do Sul"`, EN `"Rio do Sul region"`
- `"Região de Ituporanga"` → ES `"Región de Ituporanga"`, EN `"Ituporanga region"`
- o texto novo de Estações → ES `"Estaciones automáticas del INMET en la región y alrededor. Cada una muestra la distancia al centro del municipio de referencia; algunas están dentro de los municipios monitoreados. Toque un pin o la lista para ubicarla."`, EN `"INMET automatic stations in and around the region. Each one shows the distance to the center of its reference municipality; some are inside the monitored municipalities. Tap a pin or the list to locate one."`

- [ ] **Passo 4: rodar**

Rode `cd frontend && npm test && npm run typecheck && npm run build`. Tudo passa.

- [ ] **Passo 5: commit**

```bash
git add frontend/src
git commit -m "feat(frontend): textos do Alto Vale, histórico por município e teclado de regiões na janela do Telegram"
```

---

### Tarefa 11: estações, pipeline e documentação

**Arquivos:**
- Modificar:
  - `frontend/public/data/estacoes.json`, gerado
  - `backend/app/coleta/inmet.py`, em `RAIO_DE_CORTE_KM` (só se preciso) e no docstring
  - `backend/scripts/gerar_estacoes.py`, no docstring
  - `.github/workflows/pipeline.yml`, linha 22
  - `README.md`, `backend/README.md`, `docs/contratos-de-dados.md`, `docs/decisoes/ensemble.md` (§8 e §9) e `docs/pendencias.md`
  - os docstrings de `backend/app/pipeline.py` (linhas 73 e 113) e `backend/app/coleta/open_meteo.py` (linha 321)

- [ ] **Passo 1: regenerar as estações (com rede)**

Rode `cd backend && python -m scripts.gerar_estacoes`. Anote o número de estações. Se passar de 12:
- troque `RAIO_DE_CORTE_KM = 100.0` por `50.0` em `inmet.py`;
- rode de novo;
- confira que os testes de `test_inmet.py` que usam o raio continuam passando (`python -m pytest -W error tests/test_inmet.py -q`).

- [ ] **Passo 2: timeout do pipeline**

Em `.github/workflows/pipeline.yml`, troque `timeout-minutes: 30` por `timeout-minutes: 60` e acrescente acima o comentário `# 27 municípios × 4 chamadas sequenciais; com o Open-Meteo lento, 30 min não bastava (pendencias.md).`

- [ ] **Passo 3: textos que deixam de ser verdade**

Procure com `grep -rn "seis municípios\|6 municípios\|Vale Norte\|Nenhuma fica dentro\|nenhuma estação" README.md backend/README.md docs backend/app backend/scripts frontend/scripts` e corrija cada ocorrência para os 27 municípios do Alto Vale do Itajaí (microrregiões IBGE de Rio do Sul e de Ituporanga):

| Arquivo | O que muda |
|---|---|
| `README.md` | Escopo, tabelas, a seção do bot (teclado por região) e um parágrafo novo: "Quem se inscreveu em 'Todos' quando eram 6 municípios continua com esses 6; para receber os 27, toque em 'Todos' de novo no /start." |
| `backend/README.md` | Linha 3, a linha 249 (estações) e uma nota: "O bot local em Python mostra um botão por município, sem as regiões; o teclado por região é do Worker." |
| `docs/contratos-de-dados.md` | Linha 89 (estações) e linha 16: "pontos: no mínimo o centroide" continua valendo. |
| `docs/decisoes/ensemble.md` §9 | A conta com 27 municípios e 1 ponto: 27 × 4 = 108, mais 3 `meta.json`, dá 111 por execução, 444 por dia e cerca de 13.300 por mês. Tudo dentro dos limites (600 por minuto, 10.000 por dia e 300.000 por mês). |
| `docs/decisoes/ensemble.md` §8 | As estações dentro da região: A863 Ituporanga e A861 Rio do Campo. |
| `pipeline.py`, `open_meteo.py`, `inmet.py`, `gerar_estacoes.py` | Docstrings que citam "seis" ou "nenhuma dentro". |

- [ ] **Passo 4: pendências**

Em `docs/pendencias.md`, acrescente:
- ⚪ **Limiar dos 27 municípios:** todos com 150 mm provisório; validar com o time, por município ou por região.
- ⚪ **Contatos dos 21 municípios novos:** levantar e confirmar com cada prefeitura (RN09).
- ⚪ **Prazo total de coleta:** com o Open-Meteo degradado, 111 chamadas × até 92 s podem passar do `timeout-minutes: 60`; limitar o tempo total da coleta e marcar os restantes como sem dados.
- ⚪ **Avisos agrupados por chat:** se quem segue os 27 receber mensagens demais num evento regional, juntar os avisos de uma execução numa só mensagem.

- [ ] **Passo 5: rodar tudo**

```bash
cd backend && python -m pytest -W error -q
cd ../frontend && npm test && npm run typecheck && npm run build
cd ../bot-worker && npm test && npm run typecheck
```

Tudo passa.

- [ ] **Passo 6: commit**

```bash
git add -A frontend/public/data/estacoes.json backend .github/workflows/pipeline.yml README.md docs
git commit -m "docs: Alto Vale com 27 municípios, estações regeneradas e prazo do pipeline"
```

---

### Tarefa 12: validação final e PR

**Arquivos:** nenhum código novo.

- [ ] **Passo 1: execução local medida**

Rode `cd backend && time python -m scripts.rodar_local`. Leia antes o `backend/README.md`, seção "Execução local, sem bot e sem publicar", para os parâmetros. Confira que saem 27 municípios em `indices.json`, ou a lista em `municipios_sem_dados`. Anote o tempo; o critério é menos de 10 minutos.

- [ ] **Passo 2: navegador**

Com `npx astro dev --port 4330` e o `indices.json` local gerado, confira em PT, ES e EN, a 320×568, 390×844 e 1366×768:

| Tela | O que conferir |
|---|---|
| Monitoramento | rótulos por zoom; resumo "X de 27"; busca com 27 |
| Simulação | select com 27; chuva regional |
| Dados | Evolução com faixa e select; aviso de histórico por município; tabela com 27 linhas |
| Estações | texto novo |
| Janela do Telegram | as duas regiões e "Todos" |

Nenhuma tela pode ter rolagem horizontal.

- [ ] **Passo 3: revisão por subagente**

Peça a um subagente revisor a revisão do branch inteiro contra a especificação. Corrija o que ele encontrar e repita os testes.

- [ ] **Passo 4: PR**

```bash
git push -u origin feat/alto-vale
gh pr create --base main --title "Alto Vale do Itajaí: 27 municípios, bot por região e mapa legível" --body-file <arquivo com o resumo>
```

O corpo do PR traz:
- o resumo por tarefa;
- o tempo da execução local;
- o número de estações;
- o tamanho do GeoJSON;
- os passos pós-merge.

Sem atribuição ao Claude.

- [ ] **Passo 5: pós-merge (com o time)**

1. Disparar o pipeline à mão logo depois do merge (`gh workflow run pipeline.yml`), para o `indices.json` passar a 27 sem esperar até 6 h.
2. Fazer o deploy do Worker: `cd bot-worker && npm run deploy`.
3. No Telegram:
   - `/start` mostra as regiões;
   - escolher uma região mostra os municípios em duas colunas;
   - "Todos da Região de Ituporanga" inscreve 7;
   - `/status` responde.
