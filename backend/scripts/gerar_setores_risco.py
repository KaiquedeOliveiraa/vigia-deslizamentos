"""Gera `frontend/public/data/setores_risco.geojson`: setores de risco geológico do SGB.

Roda sob demanda, não no pipeline; o arquivo é versionado. Fonte: serviço
público do SGB (setorização de riscos geológicos):

    python -m scripts.gerar_setores_risco

Só setores de movimento de massa (em qualquer tipologia tipolo_g1..g5) nos
municípios de backend/config/municipios.json. Os textos (local, descrição,
recomendação) são do SGB, em português, e públicos; o script avisa se algum
parecer dado pessoal (telefone, CPF).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
if str(RAIZ_BACKEND) not in sys.path:
    sys.path.insert(0, str(RAIZ_BACKEND))

from app.config import carregar_municipios  # noqa: E402
from scripts.gerar_municipios import centroide, dentro  # noqa: E402

URL_SGB = "https://geoportal.sgb.gov.br/server/rest/services/gestaoterritorial/risco/MapServer/0/query"
SAIDA = RAIZ_BACKEND.parent / "frontend" / "public" / "data" / "setores_risco.geojson"
FONTE = "Serviço Geológico do Brasil (SGB), setorização de riscos geológicos"
TIPOS = {"Deslizamento": "deslizamento", "Rastejo": "rastejo", "Corrida de massa": "corrida_massa",
         "Queda": "queda", "Tombamento": "queda", "Rolamento": "queda"}
GRAUS = {"Alto": "alto", "Muito alto": "muito_alto"}
TIMEOUT_S = 60
_PESSOAL = re.compile(r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}|\d{3}\.\d{3}\.\d{3}-\d{2}")

_log = logging.getLogger(__name__)


def limpar_texto(valor) -> str | None:
    if not isinstance(valor, str):
        return None
    texto = re.sub(r"[ \t]+", " ", " · ".join(p.strip() for p in valor.strip().splitlines() if p.strip()))
    return texto or None


def numero_de(valor) -> int | None:
    try:
        return int(float(valor))
    except (TypeError, ValueError, OverflowError):
        return None


def data_de(epoch_ms) -> str | None:
    if not isinstance(epoch_ms, (int, float)):
        return None
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def tipo_de(props: dict) -> str | None:
    for i in range(1, 6):
        valor = props.get(f"tipolo_g{i}")
        rotulo = valor.strip() if isinstance(valor, str) else ""
        if rotulo in TIPOS:
            return TIPOS[rotulo]
    return None


def _maior_anel(geometria: dict) -> list:
    if geometria["type"] == "Polygon":
        return geometria["coordinates"][0]
    poligonos = geometria["coordinates"]
    return max(poligonos, key=lambda p: abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(p[0], p[0][1:]))))[0]


def centro_do_setor(geometria: dict) -> list[float]:
    """Ponto garantido dentro do polígono: centroide, ou o meio do maior trecho interno da horizontal dele."""
    anel = _maior_anel(geometria)
    lon, lat = centroide(anel)
    if not dentro(anel, lon, lat):
        cortes = sorted(
            x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            for (x1, y1), (x2, y2) in zip(anel, anel[1:]) if (y1 > lat) != (y2 > lat)
        )
        trechos = list(zip(cortes[0::2], cortes[1::2]))
        a, b = max(trechos, key=lambda t: t[1] - t[0])
        lon = (a + b) / 2
    return [round(lon, 5), round(lat, 5)]


def feicao_de(bruta: dict) -> dict | None:
    p = bruta.get("properties") or {}
    if not isinstance(p.get("num_setor"), str) or not isinstance(p.get("cd_geocmu"), str) or not bruta.get("geometry"):
        _log.warning("feição do SGB sem num_setor, cd_geocmu ou geometria, descartada")
        return None
    tipo = tipo_de(p)
    if tipo is None:
        return None
    grau_bruto = p.get("grau_risco")
    grau = GRAUS.get(grau_bruto.strip() if isinstance(grau_bruto, str) else "")
    if grau is None:
        _log.warning("setor %s: grau desconhecido %r, descartado", p.get("num_setor"), p.get("grau_risco"))
        return None
    props = {
        "id": p["num_setor"], "ibge": p["cd_geocmu"], "centro": centro_do_setor(bruta["geometry"]),
        "local": limpar_texto(p.get("local")), "tipo": tipo, "grau": grau,
        "descricao": limpar_texto(p.get("descricao")), "recomendacao": limpar_texto(p.get("sug_interv")),
        "pessoas": numero_de(p.get("num_pess")), "moradias": numero_de(p.get("num_domi")),
        "data": data_de(p.get("data_setor")),
    }
    for campo in ("local", "descricao", "recomendacao"):
        if props[campo] and _PESSOAL.search(props[campo]):
            _log.warning("setor %s: %s parece ter telefone ou CPF; confira antes de publicar", props["id"], campo)
    return {"type": "Feature", "geometry": bruta["geometry"], "properties": props}


def gerar(brutas: list[dict], ibges: set[str]) -> list[dict]:
    feicoes = [f for b in brutas if b["properties"].get("cd_geocmu") in ibges if (f := feicao_de(b))]
    vistos: set[str] = set()
    for f in feicoes:
        if f["properties"]["id"] in vistos:
            raise ValueError(f"id de setor repetido: {f['properties']['id']}")
        vistos.add(f["properties"]["id"])
    return sorted(feicoes, key=lambda f: (f["properties"]["ibge"], f["properties"]["id"]))


def _consultar(http: requests.Session, onde: str, **extra) -> dict:
    params = {"where": onde, "outFields": "*", "returnGeometry": "true", "outSR": "4326",
              "geometryPrecision": "5", "f": "geojson", **extra}
    r = http.get(URL_SGB, params=params, timeout=TIMEOUT_S)
    if r.status_code != 200:
        raise RuntimeError(f"SGB: HTTP {r.status_code}")
    dados = r.json()
    if "error" in dados:
        raise RuntimeError(f"SGB: {dados['error']}")
    return dados


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(prog="python -m scripts.gerar_setores_risco", description=__doc__)
    analisador.add_argument("--saida", default=str(SAIDA))
    args = analisador.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    ibges = {m.ibge for m in carregar_municipios(RAIZ_BACKEND / "config" / "municipios.json")}
    onde = "cd_geocmu IN (" + ",".join(f"'{i}'" for i in sorted(ibges)) + ")"
    with requests.Session() as http:
        total = _consultar(http, onde, returnCountOnly="true", f="json")["count"]
        brutas = _consultar(http, onde)["features"]
    if len(brutas) != total:
        raise RuntimeError(f"SGB devolveu {len(brutas)} de {total} setores; consulta incompleta")
    feicoes = gerar(brutas, ibges)
    saida = {"type": "FeatureCollection", "fonte": FONTE,
             "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "features": feicoes}
    Path(args.saida).write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")) + "\n",
                                encoding="utf-8", newline="\n")
    print(f"{len(feicoes)} setor(es) de {total} gravado(s) em {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
