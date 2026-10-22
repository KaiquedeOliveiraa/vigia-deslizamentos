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
    "VIGIA, limiar provisório de 100 mm definido pela equipe com base nos critérios "
    "de deslizamento da Defesa Civil de Blumenau (alerta a partir de 100 mm em 24 h)"
)
LIMIAR_PROVISORIO_MM = 100
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
            if ibge not in geometrias:
                raise ValueError(f"município {ibge}: sem contorno na malha {COMMIT_MALHA}")
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


def formatar(itens: list[dict]) -> str:
    """JSON igual ao formato do arquivo à mão: um campo por linha, `pontos` e `microrregiao` numa só."""
    def valor(chave, v):
        if chave in ("pontos", "microrregiao"):
            return json.dumps(v, ensure_ascii=False, separators=(", ", ": "))
        return json.dumps(v, ensure_ascii=False)

    blocos = [
        "  {\n"
        + ",\n".join(f"    {json.dumps(k)}: {valor(k, v)}" for k, v in item.items())
        + "\n  }"
        for item in itens
    ]
    return "[\n" + ",\n".join(blocos) + "\n]\n"


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
    Path(argumentos.saida).write_text(formatar(itens), encoding="utf-8", newline="\n")  # LF mesmo no Windows
    print(f"{len(itens)} município(s) gravado(s) em {argumentos.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
