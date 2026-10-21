import json
import re
from pathlib import Path

from scripts.gerar_ocorrencias import (
    converter_data,
    gerar,
    ocorrencia_de,
    resumo_danos,
)

RAIZ = Path(__file__).resolve().parents[2]
TIPOS_PUBLICADOS = {
    "Movimento de massa",
    "Enxurrada",
    "Inundação",
    "Alagamento",
    "Chuva intensa",
}


def linha(**campos):
    base = {
        "Cod_IBGE_Mun": "4202909",
        "descricao_tipologia": "Enxurradas",
        "Data_Evento": "10/05/2020",
        "Protocolo_S2iD": "SC-1",
        "Status": "Registro",
    }
    base.update(campos)
    return base


def test_converter_data():
    assert converter_data("31/12/1991") == "1991-12-31"
    for ruim in ("", "31-12-1991", "32/01/2000"):
        assert converter_data(ruim) is None


def test_resumo_danos_sem_danos():
    assert resumo_danos(linha()) == (
        "Registrado no S2iD · sem danos humanos ou materiais registrados"
    )


def test_resumo_danos_com_numeros():
    resumo = resumo_danos(
        linha(
            Status="Reconhecido",
            DH_MORTOS="1",
            DH_DESALOJADOS="30",
            **{"DM_Uni Habita Danificadas": "2"},
        )
    )
    assert resumo == (
        "Reconhecido pela União · 1 morto · 30 desalojados · 2 casas danificadas"
    )


def test_resumo_danos_aceita_decimal():
    assert "1 morto" in resumo_danos(linha(DH_MORTOS="1.0"))
    assert "1 desabrigado" in resumo_danos(linha(DH_DESABRIGADOS="1,0"))


def test_ocorrencia_de():
    assert ocorrencia_de(linha(descricao_tipologia="Estiagem e Seca")) is None
    assert ocorrencia_de(linha(Data_Evento="x")) is None
    o = ocorrencia_de(linha(descricao_tipologia="Chuvas Intensas"))
    assert o["tipo"] == "Chuva intensa"
    assert o["ibge"] == "4202909"
    assert o["data"] == "2020-05-10"
    assert o["fonte"] == "Atlas Digital de Desastres (MIDR/Sedec) · S2iD SC-1"


def test_gerar_filtra_e_ordena():
    saida = gerar(
        [
            linha(Data_Evento="01/01/2000"),
            linha(Cod_IBGE_Mun="1111111"),
            linha(Data_Evento="01/01/2010"),
        ],
        {"4202909"},
    )
    assert [o["data"] for o in saida] == ["2010-01-01", "2000-01-01"]


def test_arquivo_versionado():
    itens = json.loads(
        (RAIZ / "frontend/public/data/ocorrencias.json").read_text(encoding="utf-8")
    )
    ibges = {
        m["ibge"]
        for m in json.loads(
            (RAIZ / "backend/config/municipios.json").read_text(encoding="utf-8")
        )
    }
    assert itens
    assert all(o["ibge"] in ibges for o in itens)
    assert all(o["tipo"] in TIPOS_PUBLICADOS for o in itens)
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", o["data"]) for o in itens)
    datas = [o["data"] for o in itens]
    assert datas == sorted(datas, reverse=True)
