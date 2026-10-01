"""Testes das probabilidades complementares (pontuais, esparsos, generalizados)."""

import pytest

from app.classificacao.probabilidades import Probabilidades, probabilidades


def test_probabilidades_com_pesos_iguais():
    subs = [0.5, 1.2, 2.0, 3.0]
    pesos = [1, 1, 1, 1]

    resultado = probabilidades(subs, pesos)

    assert isinstance(resultado, Probabilidades)
    assert resultado.pontuais == pytest.approx(0.75)
    assert resultado.esparsos == pytest.approx(0.5)
    assert resultado.generalizados == pytest.approx(0.25)


def test_probabilidades_comparacao_e_estrita_valor_igual_ao_limite_nao_conta():
    subs = [1.0, 1.8, 2.6]
    pesos = [1, 1, 1]

    resultado = probabilidades(subs, pesos)

    assert resultado.pontuais == pytest.approx(2 / 3)
    assert resultado.esparsos == pytest.approx(1 / 3)
    assert resultado.generalizados == pytest.approx(0.0)


def test_probabilidades_ponderadas_pelo_peso_e_nao_por_cabeca():
    subs = [0.5, 2.0]
    pesos = [3, 1]

    resultado = probabilidades(subs, pesos)

    assert resultado.pontuais == pytest.approx(0.25)
