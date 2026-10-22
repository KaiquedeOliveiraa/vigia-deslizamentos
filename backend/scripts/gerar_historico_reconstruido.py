"""Gera `frontend/public/data/historico_reconstruido.json`: o índice do último ano reconstruído.

Roda sob demanda, não no pipeline; o arquivo é versionado. Usa a chuva horária
de reanálise ERA5 (arquivo histórico do Open-Meteo) no lugar da previsão:

    python -m scripts.gerar_historico_reconstruido [--fim 2026-10-14] [--dias 365]

É uma estimativa retroativa, sem ensemble e não validada; a reanálise suaviza
chuvas fortes e localizadas e tende a subestimar picos (ver
`docs/contratos-de-dados.md`). Uma única requisição, sem retentativa.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
if str(RAIZ_BACKEND) not in sys.path:
    sys.path.insert(0, str(RAIZ_BACKEND))

from app.calculo.agregacao import rotulos_efr, rotulos_rtotal  # noqa: E402
from app.calculo.chuva_efetiva import efr  # noqa: E402
from app.calculo.indice import subindice  # noqa: E402
from app.classificacao.classes import classe  # noqa: E402
from app.config import carregar_municipios  # noqa: E402
from app.exportacao.exportar import montar_historico, serializar_compacto  # noqa: E402
from app.modelos.banco import ItemHistorico  # noqa: E402

URL_ARQUIVO = "https://archive-api.open-meteo.com/v1/archive"
SAIDA = RAIZ_BACKEND.parent / "frontend" / "public" / "data" / "historico_reconstruido.json"
FONTE = ("Estimativa reconstruída pelo VIGIA com chuva horária de reanálise ERA5 "
         "(Open-Meteo, arquivo histórico), sem ensemble; tende a subestimar picos")
TIMEOUT_S = 90
FIM_PADRAO = "2026-10-14"
DIAS_PADRAO = 365
MAX_FALTANTES = 0.05

_log = logging.getLogger(__name__)


def serie_do_ponto(item_resposta: dict) -> dict[datetime, float | None]:
    """Rótulo (UTC, com fuso) → chuva em mm; os rótulos da API vêm sem fuso."""
    horas = item_resposta["hourly"]
    return {
        datetime.fromisoformat(t).replace(tzinfo=timezone.utc): v
        for t, v in zip(horas["time"], horas["precipitation"])
    }


def indice_do_ponto(serie: dict[datetime, float | None], dia: date, limiar_mm: float, mv_h: float) -> float | None:
    """Índice do dia-alvo num ponto; `None` se faltar alguma hora das janelas (nunca vira zero)."""
    efr_horas = [serie.get(r) for r in rotulos_efr(dia)]
    rtotal_horas = [serie.get(r) for r in rotulos_rtotal(dia)]
    if any(v is None for v in efr_horas + rtotal_horas):
        return None
    return subindice(efr(efr_horas, mv_h), sum(rtotal_horas), limiar_mm)


def reconstruir(municipios, series_por_ponto: list[dict], inicio: date, fim: date) -> dict[str, list[ItemHistorico]]:
    """Maior índice entre os pontos do município em cada dia; `series_por_ponto` na ordem dos pontos."""
    historicos: dict[str, list[ItemHistorico]] = {}
    seguinte = 0
    for m in municipios:
        series = series_por_ponto[seguinte:seguinte + len(m.pontos)]
        seguinte += len(m.pontos)
        itens = []
        for i in range((fim - inicio).days + 1):
            dia = inicio + timedelta(days=i)
            valores = [v for s in series if (v := indice_do_ponto(s, dia, m.limiar_mm, m.mv_h)) is not None]
            if valores:
                itens.append(ItemHistorico(dia_alvo=dia, indice=max(valores), classe=classe(max(valores))))
        historicos[m.ibge] = itens
    return historicos


def validar(historicos, municipios, inicio: date, fim: date) -> None:
    total = (fim - inicio).days + 1
    for m in municipios:
        n = len(historicos.get(m.ibge) or [])
        if n == 0:
            raise ValueError(f"{m.nome} ({m.ibge}): nenhum dia reconstruído")
        if (total - n) / total > MAX_FALTANTES:
            raise ValueError(f"{m.nome} ({m.ibge}): {total - n} de {total} dias sem dado (máximo {MAX_FALTANTES:.0%})")


def montar_arquivo(historicos, municipios) -> dict:
    dados = montar_historico(historicos, FONTE)
    for m in municipios:
        if m.ibge in dados["municipios"]:
            dados["municipios"][m.ibge].update(limiar_mm=m.limiar_mm, mv_h=m.mv_h)
    return dados


def baixar(pontos, inicio: date, fim: date, http: requests.Session) -> list[dict]:
    params = {
        "latitude": ",".join(str(p.lat) for p in pontos), "longitude": ",".join(str(p.lon) for p in pontos),
        "hourly": "precipitation", "models": "era5", "timezone": "GMT",
        "start_date": (inicio - timedelta(days=7)).isoformat(), "end_date": (fim + timedelta(days=1)).isoformat(),
    }
    r = http.get(URL_ARQUIVO, params=params, timeout=TIMEOUT_S)
    if r.status_code != 200:
        raise RuntimeError(f"Open-Meteo: HTTP {r.status_code}: {r.text[:200]}")
    dados = r.json()
    if isinstance(dados, dict):
        dados = [dados]
    if len(dados) != len(pontos):
        raise ValueError(f"Open-Meteo devolveu {len(dados)} itens para {len(pontos)} pontos")
    return dados


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(prog="python -m scripts.gerar_historico_reconstruido", description=__doc__)
    analisador.add_argument("--saida", default=str(SAIDA))
    analisador.add_argument("--fim", type=date.fromisoformat, default=date.fromisoformat(FIM_PADRAO))
    analisador.add_argument("--dias", type=int, default=DIAS_PADRAO)
    args = analisador.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    fim = args.fim
    inicio = fim - timedelta(days=args.dias - 1)
    municipios = carregar_municipios(RAIZ_BACKEND / "config" / "municipios.json")
    pontos = [p for m in municipios for p in m.pontos]
    with requests.Session() as http:
        respostas = baixar(pontos, inicio, fim, http)
    historicos = reconstruir(municipios, [serie_do_ponto(r) for r in respostas], inicio, fim)
    validar(historicos, municipios, inicio, fim)
    corpo = serializar_compacto(montar_arquivo(historicos, municipios))
    Path(args.saida).write_bytes(corpo)
    _log.info("%d município(s), %d bytes, %s a %s, gravado em %s",
              len(historicos), len(corpo), inicio, fim, args.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
