"""Testes do exportador (Tarefa 9): `montar_indices` e `serializar`.

`montar_indices` é pura — recebe resultado, configuração, históricos e
`gerado_em` por parâmetro. Os valores esperados são literais; o JSON montado é
validado contra `docs/indices.schema.json` com verificação de formato ativa
(`tests/apoio_schema.py`).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.calculo.agregacao import Resultado, ResultadoDia, ResultadoMunicipio
from app.classificacao.probabilidades import Probabilidades
from app.config import Municipio, Ponto
from app.exportacao.exportar import montar_indices, serializar
from app.modelos.banco import ItemHistorico
from tests.apoio_schema import carregar_schema, validador_estrito

UTC = timezone.utc
GERADO_EM = datetime(2026, 10, 1, 9, 12, 30, tzinfo=UTC)
D0 = date(2026, 10, 1)


def municipio_de_teste(ibge: str = "4206900", nome: str = "Ibirama") -> Municipio:
    return Municipio(
        ibge=ibge,
        nome=nome,
        limiar_mm=250.0,
        fonte_limiar="GeoRisk, limiar hipotético padrão",
        mv_h=24.0,
        pontos=(Ponto(lat=-27.0181, lon=-49.5286),),
    )


def dia_de_teste(d: int, indice: float, classe_do_dia: int) -> ResultadoDia:
    return ResultadoDia(
        dia_alvo=D0 + timedelta(days=d),
        d=d,
        indice=indice,
        classe=classe_do_dia,
        efr_mm=52.0 + d,
        rtotal_mm=105.0 + d,
        n_membros=4,
        prob=Probabilidades(pontuais=0.5, esparsos=0.25, generalizados=0.0),
    )


def resultado_de_teste(
    ibge: str = "4206900", sem_dados: list[str] | None = None
) -> Resultado:
    return Resultado(
        dia_alvo_d0=D0,
        municipios=[
            ResultadoMunicipio(
                ibge=ibge,
                limiar_mm=250.0,
                dias=(
                    dia_de_teste(0, 1.05, 4),
                    dia_de_teste(1, 0.60, 3),
                    dia_de_teste(2, 0.30, 1),
                    dia_de_teste(3, 2.00, 5),
                ),
                chuva_acum_mm={"24h": 24.0, "48h": 48.0, "72h": 72.0, "96h": 96.0},
            )
        ],
        municipios_sem_dados=sem_dados or [],
    )


HISTORICO_DE_TESTE = {
    "4206900": [
        ItemHistorico(dia_alvo=date(2026, 9, 29), indice=0.40, classe=2),
        ItemHistorico(dia_alvo=date(2026, 9, 30), indice=0.80, classe=3),
    ]
}


# --- validade pelo schema -----------------------------------------------------


def test_json_montado_e_valido_pelo_schema_do_contrato():
    dados = montar_indices(
        resultado_de_teste(),
        [municipio_de_teste()],
        HISTORICO_DE_TESTE,
        GERADO_EM,
    )

    validador_estrito(carregar_schema()).validate(dados)


def test_json_com_municipio_sem_dados_tambem_e_valido_pelo_schema():
    dados = montar_indices(
        resultado_de_teste(sem_dados=["4205100"]),
        [municipio_de_teste(), municipio_de_teste("4205100", "Dona Emma")],
        HISTORICO_DE_TESTE,
        GERADO_EM,
    )

    validador_estrito(carregar_schema()).validate(dados)


# --- raiz ---------------------------------------------------------------------


def test_raiz_tem_os_cinco_campos_do_contrato():
    dados = montar_indices(
        resultado_de_teste(), [municipio_de_teste()], HISTORICO_DE_TESTE, GERADO_EM
    )

    assert dados["schema_version"] == 1
    assert dados["dia_alvo_d0"] == "2026-10-01"
    assert dados["municipios_sem_dados"] == []
    assert [item["ibge"] for item in dados["municipios"]] == ["4206900"]


def test_gerado_em_sai_com_fuso_e_em_utc():
    gerado_em_em_brasilia = datetime(
        2026, 10, 1, 6, 12, 30, tzinfo=timezone(timedelta(hours=-3))
    )

    dados = montar_indices(
        resultado_de_teste(), [municipio_de_teste()], HISTORICO_DE_TESTE,
        gerado_em_em_brasilia,
    )

    # Mesmo instante do GERADO_EM, normalizado para UTC com fuso explícito.
    assert dados["gerado_em"] == "2026-10-01T09:12:30+00:00"


def test_gerado_em_sem_fuso_levanta_erro():
    with pytest.raises(ValueError, match="gerado_em"):
        montar_indices(
            resultado_de_teste(),
            [municipio_de_teste()],
            HISTORICO_DE_TESTE,
            datetime(2026, 10, 1, 9, 12, 30),
        )


# --- item de municipios -------------------------------------------------------


def test_item_do_municipio_traz_os_parametros_da_configuracao():
    dados = montar_indices(
        resultado_de_teste(), [municipio_de_teste()], HISTORICO_DE_TESTE, GERADO_EM
    )

    (item,) = dados["municipios"]
    assert item["ibge"] == "4206900"
    assert item["nome"] == "Ibirama"
    assert item["limiar_mm"] == 250.0
    assert item["fonte_limiar"] == "GeoRisk, limiar hipotético padrão"
    assert item["mv_h"] == 24.0


def test_chuva_acum_mm_tem_exatamente_as_quatro_chaves_do_contrato():
    dados = montar_indices(
        resultado_de_teste(), [municipio_de_teste()], HISTORICO_DE_TESTE, GERADO_EM
    )

    (item,) = dados["municipios"]
    assert item["chuva_acum_mm"] == {
        "24h": 24.0,
        "48h": 48.0,
        "72h": 72.0,
        "96h": 96.0,
    }


def test_historico_sai_na_ordem_recebida_com_dia_alvo_em_texto():
    dados = montar_indices(
        resultado_de_teste(), [municipio_de_teste()], HISTORICO_DE_TESTE, GERADO_EM
    )

    (item,) = dados["municipios"]
    assert item["historico"] == [
        {"dia_alvo": "2026-09-29", "indice": 0.40, "classe": 2},
        {"dia_alvo": "2026-09-30", "indice": 0.80, "classe": 3},
    ]


def test_municipio_sem_historico_sai_com_lista_vazia():
    dados = montar_indices(
        resultado_de_teste(), [municipio_de_teste()], {}, GERADO_EM
    )

    assert dados["municipios"][0]["historico"] == []


# --- dias ---------------------------------------------------------------------


def test_dias_tem_quatro_itens_com_d_de_0_a_3_e_dias_consecutivos():
    dados = montar_indices(
        resultado_de_teste(), [municipio_de_teste()], HISTORICO_DE_TESTE, GERADO_EM
    )

    dias = dados["municipios"][0]["dias"]
    assert [dia["d"] for dia in dias] == [0, 1, 2, 3]
    assert [dia["dia_alvo"] for dia in dias] == [
        "2026-10-01",
        "2026-10-02",
        "2026-10-03",
        "2026-10-04",
    ]


def test_cada_dia_traz_indice_classe_efr_rtotal_n_membros_e_prob():
    dados = montar_indices(
        resultado_de_teste(), [municipio_de_teste()], HISTORICO_DE_TESTE, GERADO_EM
    )

    dia_d0 = dados["municipios"][0]["dias"][0]
    assert dia_d0["indice"] == 1.05
    assert dia_d0["classe"] == 4
    assert dia_d0["efr_mm"] == 52.0
    assert dia_d0["rtotal_mm"] == 105.0
    assert dia_d0["n_membros"] == 4
    assert dia_d0["prob"] == {"pontuais": 0.5, "esparsos": 0.25, "generalizados": 0.0}


# --- municípios sem dados -----------------------------------------------------


def test_municipio_sem_dados_aparece_na_lista_e_nao_entre_os_municipios():
    dados = montar_indices(
        resultado_de_teste(sem_dados=["4205100"]),
        [municipio_de_teste(), municipio_de_teste("4205100", "Dona Emma")],
        HISTORICO_DE_TESTE,
        GERADO_EM,
    )

    assert dados["municipios_sem_dados"] == ["4205100"]
    assert [item["ibge"] for item in dados["municipios"]] == ["4206900"]


def test_resultado_de_municipio_fora_da_configuracao_levanta_erro():
    # O nome, o limiar e o mv_h vêm da configuração; um ibge sem entrada lá
    # geraria um item incompleto em silêncio.
    with pytest.raises(KeyError, match="4206900"):
        montar_indices(resultado_de_teste(), [], HISTORICO_DE_TESTE, GERADO_EM)


# --- serializar ---------------------------------------------------------------


def test_serializar_devolve_bytes_utf8_que_voltam_ao_mesmo_dicionario():
    dados = montar_indices(
        resultado_de_teste(), [municipio_de_teste()], HISTORICO_DE_TESTE, GERADO_EM
    )

    conteudo = serializar(dados)

    assert isinstance(conteudo, bytes)
    assert json.loads(conteudo.decode("utf-8")) == dados


def test_serializar_escreve_acentos_em_utf8_e_nao_em_escapes_ascii():
    dados = montar_indices(
        resultado_de_teste(ibge="4209151"),
        [municipio_de_teste("4209151", "José Boiteux")],
        HISTORICO_DE_TESTE,
        GERADO_EM,
    )

    conteudo = serializar(dados)

    assert "José Boiteux".encode("utf-8") in conteudo
    assert b"\\u00e9" not in conteudo


def test_serializar_termina_com_quebra_de_linha():
    # O arquivo é versionado por commit no repositório; sem a quebra final o
    # diff do GitHub marca "no newline at end of file" em cada publicação.
    conteudo = serializar(
        montar_indices(
            resultado_de_teste(), [municipio_de_teste()], HISTORICO_DE_TESTE, GERADO_EM
        )
    )

    assert conteudo.endswith(b"\n")
