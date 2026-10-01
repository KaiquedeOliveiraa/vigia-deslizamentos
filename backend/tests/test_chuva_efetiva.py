"""Testes da chuva efetiva antecedente (EfR)."""

import pytest

from app.calculo.chuva_efetiva import SerieInvalidaError, efr


def test_dez_mm_so_na_hora_t0_retorna_o_proprio_valor():
    assert efr([10.0], mv_h=24) == pytest.approx(10.0)


def test_dez_mm_so_em_t24_com_mv_24_decai_pela_metade():
    chuva_horaria = [0.0] * 24 + [10.0]  # índice 24 -> t=24
    assert efr(chuva_horaria, mv_h=24) == pytest.approx(5.0)


def test_dez_mm_so_em_t48_com_mv_24_decai_para_um_quarto():
    chuva_horaria = [0.0] * 48 + [10.0]  # índice 48 -> t=48
    assert efr(chuva_horaria, mv_h=24) == pytest.approx(2.5)


def test_serie_vazia_retorna_zero():
    assert efr([], mv_h=24) == 0


def test_valor_none_na_serie_levanta_erro():
    with pytest.raises(SerieInvalidaError):
        efr([10.0, None, 5.0], mv_h=24)


def test_mais_de_169_valores_levanta_erro():
    chuva_horaria = [1.0] * 170
    with pytest.raises(SerieInvalidaError):
        efr(chuva_horaria, mv_h=24)
