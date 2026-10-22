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
    formatar,
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


def test_mescla_falha_sem_geometria_com_o_codigo_na_mensagem():
    with pytest.raises(ValueError, match="4209003"):
        mesclar([], [(RIO_DO_SUL, [{"id": 4209003, "nome": "Lontras"}])], {})


def test_formatar_mantem_o_formato_do_arquivo():
    texto = formatar([dict(ATUAL, microrregiao={"codigo": "42011", "nome": "Rio do Sul"})])
    assert '    "pontos": [{"lat": -27.0181, "lon": -49.5286}],\n' in texto
    assert texto.endswith('    "microrregiao": {"codigo": "42011", "nome": "Rio do Sul"}\n  }\n]\n')
    assert json.loads(texto)[0]["ibge"] == "4206900"


def test_mescla_mantem_o_nome_atual_e_avisa(caplog):
    with caplog.at_level(logging.WARNING):
        resultado = mesclar([dict(ATUAL)], [(RIO_DO_SUL, [{"id": 4206900, "nome": "Ibirama (novo)"}])], {})
    assert resultado[0]["nome"] == "Ibirama"
    assert "Ibirama (novo)" in caplog.text


# Os 6 de antes da ampliação, campo a campo (sem `microrregiao`): não podem mudar.
SEIS_ORIGINAIS = {
    "4205100": ("Dona Emma", -26.9887, -49.7781),
    "4206900": ("Ibirama", -27.0181, -49.5286),
    "4209151": ("José Boiteux", -26.8595, -49.6463),
    "4214003": ("Presidente Getúlio", -27.0626, -49.7144),
    "4219358": ("Vitor Meireles", -26.8264, -49.8452),
    "4219408": ("Witmarsum", -26.9373, -49.8417),
}


def test_arquivo_versionado_tem_os_27_e_os_6_atuais_intactos():
    texto = (RAIZ / "backend" / "config" / "municipios.json").read_text(encoding="utf-8")
    dados = json.loads(texto)
    assert texto == formatar(dados)
    assert len(dados) == 27
    assert dados == sorted(dados, key=chave_de_ordem)
    por_ibge = {m["ibge"]: m for m in dados}
    assert {m["microrregiao"]["codigo"] for m in dados} == {"42011", "42014"}
    for ibge, (nome, lat, lon) in SEIS_ORIGINAIS.items():
        assert {k: v for k, v in por_ibge[ibge].items() if k != "microrregiao"} == {
            "ibge": ibge,
            "nome": nome,
            "limiar_mm": 150,
            "fonte_limiar": FONTE_LIMIAR_PROVISORIA,
            "mv_h": 24,
            "pontos": [{"lat": lat, "lon": lon}],
        }
