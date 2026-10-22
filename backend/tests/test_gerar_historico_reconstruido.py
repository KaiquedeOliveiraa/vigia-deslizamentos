"""Testes do reconstrutor do histórico com chuva ERA5 (sem rede, exceto o marcado `rede`)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from app.calculo.agregacao import rotulos_efr, rotulos_rtotal
from app.calculo.chuva_efetiva import efr
from app.calculo.indice import subindice
from app.config import Municipio, Ponto, carregar_municipios
from app.modelos.banco import ItemHistorico
from scripts.gerar_historico_reconstruido import (
    FONTE, baixar, indice_do_ponto, montar_arquivo, reconstruir, serie_do_ponto, validar,
)

RAIZ = Path(__file__).resolve().parents[2]
D = date(2026, 10, 10)


def utc(dia: date, hora: int = 0) -> datetime:
    return datetime(dia.year, dia.month, dia.day, tzinfo=timezone.utc) + timedelta(hours=hora)


def serie_completa(**chuva) -> dict:
    """Todas as horas das janelas de D e D+1 em zero; `chuva` não usada, ver chamadas."""
    rotulos = rotulos_efr(D) + rotulos_rtotal(D) + rotulos_efr(D + timedelta(days=1)) + rotulos_rtotal(D + timedelta(days=1))
    return {r: 0.0 for r in rotulos}


def mun(ibge="1", n_pontos=1, limiar=150.0) -> Municipio:
    return Municipio(ibge=ibge, nome=f"M{ibge}", limiar_mm=limiar, fonte_limiar="x", mv_h=24.0,
                     pontos=tuple(Ponto(-27.0, -49.0) for _ in range(n_pontos)))


def test_indice_do_ponto_bate_com_calculo_manual():
    serie = serie_completa()
    serie[utc(D)] = 10.0          # t=0 do EfR
    serie[utc(D, 12)] = 20.0      # Rtotal
    esperado = subindice(efr([10.0] + [0.0] * 168, 24.0), 20.0, 150.0)
    assert esperado == pytest.approx((10 + 20) / 150)
    assert indice_do_ponto(serie, D, 150.0, 24.0) == pytest.approx(esperado)


def test_ultimo_rotulo_do_rtotal_e_meia_noite_do_dia_seguinte():
    serie = serie_completa()
    serie[utc(D, 24)] = 15.0
    assert indice_do_ponto(serie, D, 150.0, 24.0) == pytest.approx(15 / 150)


def test_hora_none_ou_ausente_invalida_o_dia():
    serie = serie_completa()
    serie[utc(D, 5)] = None
    assert indice_do_ponto(serie, D, 150.0, 24.0) is None
    del serie[utc(D, 5)]
    assert indice_do_ponto(serie, D, 150.0, 24.0) is None
    assert indice_do_ponto(serie_completa(), D, 150.0, 24.0) == 0.0


def test_serie_do_ponto_le_rotulos_como_utc():
    s = serie_do_ponto({"hourly": {"time": ["2026-10-08T00:00", "2026-10-08T01:00"], "precipitation": [1.5, None]}})
    assert s == {datetime(2026, 10, 8, tzinfo=timezone.utc): 1.5, datetime(2026, 10, 8, 1, tzinfo=timezone.utc): None}


def test_reconstruir_maior_ponto_vence_e_none_nao_conta():
    a, b = serie_completa(), serie_completa()
    a[utc(D)] = 30.0
    b[utc(D)] = 60.0
    b2 = dict(serie_completa())
    b2[utc(D, 3)] = None  # ponto incompleto em D (e em D+1 por causa do EfR)
    m = mun(n_pontos=2)
    h = reconstruir([m], [a, b], D, D)
    assert h["1"][0].indice == pytest.approx(60 / 150) and h["1"][0].classe >= 1
    h = reconstruir([m], [a, b2], D, D)
    assert h["1"][0].indice == pytest.approx(30 / 150)
    assert reconstruir([m], [b2, dict(b2)], D, D) == {"1": []}


def test_reconstruir_reparte_series_entre_municipios():
    a, b = serie_completa(), serie_completa()
    b[utc(D)] = 150.0
    h = reconstruir([mun("1"), mun("2")], [a, b], D, D)
    assert h["1"][0].indice == 0.0 and h["2"][0].indice == pytest.approx(1.0)


def itens(inicio: date, n: int) -> list[ItemHistorico]:
    return [ItemHistorico(inicio + timedelta(days=i), 0.5, 3) for i in range(n)]


def test_validar():
    ms = [mun("1")]
    validar({"1": itens(D, 20)}, ms, D, D + timedelta(days=19))
    validar({"1": itens(D, 19)}, ms, D, D + timedelta(days=19))  # 5% exato passa
    with pytest.raises(ValueError, match="nenhum dia"):
        validar({"1": []}, ms, D, D + timedelta(days=19))
    with pytest.raises(ValueError, match="nenhum dia"):
        validar({}, ms, D, D + timedelta(days=19))
    with pytest.raises(ValueError, match="sem dado"):
        validar({"1": itens(D, 18)}, ms, D, D + timedelta(days=19))


def test_montar_arquivo_leva_limiar_e_mv():
    ms = [mun("1", limiar=120.0), mun("2")]
    dados = montar_arquivo({"1": itens(D, 2), "2": []}, ms)
    assert dados["fonte"] == FONTE
    assert dados["municipios"]["1"]["limiar_mm"] == 120.0 and dados["municipios"]["1"]["mv_h"] == 24.0
    assert "2" not in dados["municipios"]


class _Resposta:
    status_code = 200
    text = ""

    def __init__(self, corpo):
        self._corpo = corpo

    def json(self):
        return self._corpo


class _Http:
    def __init__(self, corpo):
        self.corpo, self.chamadas = corpo, []

    def get(self, url, params, timeout):
        self.chamadas.append((url, params, timeout))
        return _Resposta(self.corpo)


def test_baixar_monta_uma_requisicao_e_confere_o_tamanho():
    pontos = [Ponto(-27.1, -49.1), Ponto(-27.2, -49.2)]
    http = _Http([{}, {}])
    assert baixar(pontos, D, D, http) == [{}, {}]
    (_, p, t), = http.chamadas
    assert p["latitude"] == "-27.1,-27.2" and p["longitude"] == "-49.1,-49.2" and t == 90
    assert p["start_date"] == "2026-10-03" and p["end_date"] == "2026-10-11" and p["models"] == "era5"
    assert baixar(pontos[:1], D, D, _Http({"a": 1})) == [{"a": 1}]
    with pytest.raises(ValueError):
        baixar(pontos, D, D, _Http([{}]))


def test_arquivo_versionado():
    dados = json.loads((RAIZ / "frontend" / "public" / "data" / "historico_reconstruido.json").read_text(encoding="utf-8"))
    ms = {m.ibge: m for m in carregar_municipios(RAIZ / "backend" / "config" / "municipios.json")}
    assert dados["schema_version"] == 1
    assert set(dados["municipios"]) == set(ms)
    for ibge, item in dados["municipios"].items():
        assert item["limiar_mm"] == ms[ibge].limiar_mm and item["mv_h"] == ms[ibge].mv_h
        assert all(v is None or v >= 0 for v in item["indices"])
        ultimo = date.fromisoformat(item["inicio"]) + timedelta(days=len(item["indices"]) - 1)
        assert ultimo == date(2026, 10, 14)


@pytest.mark.rede
def test_api_real_devolve_um_item_por_ponto():
    with requests.Session() as http:
        resposta = baixar([Ponto(-27.45, -49.82), Ponto(-27.33, -49.72)], date(2026, 10, 1), date(2026, 10, 3), http)
    assert len(resposta) == 2
