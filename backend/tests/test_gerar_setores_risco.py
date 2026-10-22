"""Testes do gerador de setores de risco do SGB (sem rede: respostas fixas)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.gerar_setores_risco import (
    centro_do_setor, data_de, feicao_de, gerar, limpar_texto, numero_de, tipo_de,
)

RAIZ = Path(__file__).resolve().parents[2]
QUAD = [[-49.6, -27.1], [-49.4, -27.1], [-49.4, -26.9], [-49.6, -26.9], [-49.6, -27.1]]


def bruta(**props):
    base = {
        "num_setor": "SC_X_SR_001_CPRM", "cd_geocmu": "4206900", "local": " Rua A ",
        "tipolo_g1": "Deslizamento", "tipolo_g2": " ", "tipolo_g3": " ", "tipolo_g4": " ", "tipolo_g5": " ",
        "grau_risco": "Alto", "descricao": "Encosta\nexposta", "sug_interv": "1 - Remoção\n2 - Drenagem",
        "num_pess": 16.0, "num_domi": 4.0, "data_setor": 1540425600000,
    }
    base.update(props)
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [QUAD]}, "properties": base}


def test_tipo_primeiro_movimento_de_massa_em_qualquer_tipologia():
    assert tipo_de({"tipolo_g1": "Inundação", "tipolo_g2": "Rastejo", "tipolo_g3": " "}) == "rastejo"
    assert tipo_de({"tipolo_g1": "Tombamento"}) == "queda"
    assert tipo_de({"tipolo_g1": "Inundação", "tipolo_g2": "Erosão"}) is None


def test_limpar_texto():
    assert limpar_texto("  a\n b   c ") == "a · b c"
    assert limpar_texto(" ") is None
    assert limpar_texto(None) is None


def test_numero_e_data():
    assert numero_de(16.0) == 16 and numero_de(0) == 0 and numero_de(" ") is None and numero_de(None) is None
    assert data_de(1540425600000) == "2018-10-25" and data_de(None) is None


def test_centro_dentro_de_poligono_concavo():
    u = [[0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3], [0, 0]]
    lon, lat = centro_do_setor({"type": "Polygon", "coordinates": [u]})
    from scripts.gerar_municipios import dentro
    assert dentro(u, lon, lat)


def test_feicao_de_mapeia_e_limpa():
    f = feicao_de(bruta())
    p = f["properties"]
    assert p["id"] == "SC_X_SR_001_CPRM" and p["ibge"] == "4206900" and p["tipo"] == "deslizamento"
    assert p["grau"] == "alto" and p["local"] == "Rua A" and p["descricao"] == "Encosta · exposta"
    assert p["recomendacao"] == "1 - Remoção · 2 - Drenagem" and p["pessoas"] == 16 and p["moradias"] == 4
    assert p["data"] == "2018-10-25" and len(p["centro"]) == 2


def test_feicao_de_descarta_fora_e_grau_desconhecido():
    assert feicao_de(bruta(tipolo_g1="Inundação")) is None
    assert feicao_de(bruta(grau_risco="Médio")) is None


def test_gerar_ordena_e_recusa_id_repetido():
    a = bruta(num_setor="B", cd_geocmu="4206900")
    b = bruta(num_setor="A", cd_geocmu="4206900")
    assert [f["properties"]["id"] for f in gerar([a, b], {"4206900"})] == ["A", "B"]
    with pytest.raises(ValueError, match="repetido"):
        gerar([a, a], {"4206900"})
    assert gerar([bruta(cd_geocmu="9999999")], {"4206900"}) == []


def test_aviso_de_telefone(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        feicao_de(bruta(local="Rua A, tel (47) 99999-1234"))
    assert "telefone ou CPF" in caplog.text


def test_feicao_sem_campos_obrigatorios_e_descartada():
    sem = bruta()
    del sem["properties"]["num_setor"]
    assert feicao_de(sem) is None
    assert tipo_de({"tipolo_g1": None, "tipolo_g2": 3}) is None


class _Resposta:
    def __init__(self, status, dados):
        self.status_code, self._dados = status, dados

    def json(self):
        return self._dados


class _Sessao:
    def __init__(self, respostas):
        self.respostas = list(respostas)

    def get(self, *_a, **_k):
        return self.respostas.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_main_falha_com_contagem_diferente(monkeypatch, tmp_path):
    import scripts.gerar_setores_risco as g
    monkeypatch.setattr(g.requests, "Session", lambda: _Sessao([_Resposta(200, {"count": 2}), _Resposta(200, {"type": "FeatureCollection", "features": [bruta()]})]))
    with pytest.raises(RuntimeError, match="incompleta"):
        g.main(["--saida", str(tmp_path / "x.geojson")])


def test_main_falha_com_http_e_com_error(monkeypatch, tmp_path):
    import scripts.gerar_setores_risco as g
    monkeypatch.setattr(g.requests, "Session", lambda: _Sessao([_Resposta(500, {})]))
    with pytest.raises(RuntimeError, match="HTTP 500"):
        g.main(["--saida", str(tmp_path / "x.geojson")])
    monkeypatch.setattr(g.requests, "Session", lambda: _Sessao([_Resposta(200, {"error": {"code": 400}})]))
    with pytest.raises(RuntimeError, match="SGB"):
        g.main(["--saida", str(tmp_path / "x.geojson")])


def test_arquivo_versionado():
    d = json.loads((RAIZ / "frontend" / "public" / "data" / "setores_risco.geojson").read_text(encoding="utf-8"))
    ibges = {m["ibge"] for m in json.loads((RAIZ / "backend" / "config" / "municipios.json").read_text(encoding="utf-8"))}
    fs = d["features"]
    assert d["type"] == "FeatureCollection" and d["fonte"].startswith("Serviço Geológico do Brasil") and len(fs) > 80
    ids = [f["properties"]["id"] for f in fs]
    assert len(ids) == len(set(ids))
    for f in fs:
        p = f["properties"]
        assert p["ibge"] in ibges
        assert p["tipo"] in {"deslizamento", "rastejo", "corrida_massa", "queda"}
        assert p["grau"] in {"alto", "muito_alto"}
        assert f["geometry"]["type"] in {"Polygon", "MultiPolygon"}
