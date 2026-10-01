"""Testes do subíndice de risco e do índice ponderado."""

import pytest

from app.calculo.indice import (
    IndicePonderadoInvalidoError,
    SubindiceInvalidoError,
    indice_ponderado,
    subindice,
)


# --- subindice ----------------------------------------------------------------


def test_subindice_calcula_razao_entre_chuva_e_limiar():
    assert subindice(efr=100, rtotal=20, limiar=120) == pytest.approx(1.0)


def test_subindice_com_limiar_zero_levanta_erro_identificando_o_limiar():
    with pytest.raises(SubindiceInvalidoError, match="subindice.*limiar=0"):
        subindice(efr=100, rtotal=20, limiar=0)


def test_subindice_com_limiar_negativo_levanta_erro_identificando_o_limiar():
    with pytest.raises(SubindiceInvalidoError, match="subindice.*limiar=-10"):
        subindice(efr=100, rtotal=20, limiar=-10)


# --- indice_ponderado -----------------------------------------------------------


def test_indice_ponderado_com_pesos_iguais_e_media_simples():
    subs = [0.5, 1.0, 1.5]
    pesos = [1, 1, 1]
    assert indice_ponderado(subs, pesos) == pytest.approx(1.0)


def test_indice_ponderado_com_pesos_tres_e_um_pondera_pelo_peso():
    subs = [1.0, 2.0]
    pesos = [3, 1]
    assert indice_ponderado(subs, pesos) == pytest.approx(1.25)


def test_indice_ponderado_com_lista_vazia_levanta_erro():
    with pytest.raises(IndicePonderadoInvalidoError):
        indice_ponderado([], [])


def test_indice_ponderado_com_tamanhos_diferentes_levanta_erro():
    with pytest.raises(IndicePonderadoInvalidoError):
        indice_ponderado([1.0, 2.0], [1])


def test_indice_ponderado_com_soma_de_pesos_zero_levanta_erro():
    with pytest.raises(IndicePonderadoInvalidoError):
        indice_ponderado([1.0, 2.0], [0, 0])
