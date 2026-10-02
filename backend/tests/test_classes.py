"""Testes de fronteira das classes de risco e do gatilho de alerta.

Fronteiras são faixas semiabertas `[a, b)`: usar literais exatos, nunca
`pytest.approx` — é justamente a fronteira `<` vs `<=` que estes testes
verificam.
"""

import pytest

from app.classificacao.classes import classe, em_alerta, nome_classe


def test_abaixo_de_0_40_e_classe_1_extremamente_baixo():
    assert classe(0.3999) == 1


def test_0_40_e_classe_2_muito_baixo():
    assert classe(0.40) == 2


def test_0_70_e_classe_3_baixo():
    assert classe(0.70) == 3


def test_logo_abaixo_de_1_00_ainda_e_classe_3():
    assert classe(0.9999) == 3


def test_1_00_e_classe_4_moderado():
    assert classe(1.00) == 4


def test_logo_abaixo_de_1_80_ainda_e_classe_4():
    assert classe(1.7999) == 4


def test_1_80_e_classe_5_alto():
    assert classe(1.80) == 5


def test_2_60_e_classe_6_muito_alto():
    assert classe(2.60) == 6


def test_logo_abaixo_de_3_40_ainda_e_classe_6():
    assert classe(3.3999) == 6


def test_3_40_e_classe_7_extremamente_alto():
    assert classe(3.40) == 7


def test_em_alerta_e_falso_logo_abaixo_de_1_00():
    assert em_alerta(0.9999) is False


def test_em_alerta_e_verdadeiro_a_partir_de_1_00():
    assert em_alerta(1.00) is True


# --- nome da classe (RN03: risco nunca só por cor) ----------------------------


def test_nome_de_cada_uma_das_sete_classes_segue_a_tabela_do_readme():
    assert [nome_classe(numero) for numero in range(1, 8)] == [
        "extremamente baixo",
        "muito baixo",
        "baixo",
        "moderado",
        "alto",
        "muito alto",
        "extremamente alto",
    ]


def test_nome_de_classe_fora_de_1_a_7_levanta_erro():
    with pytest.raises(ValueError, match="classe"):
        nome_classe(0)
    with pytest.raises(ValueError, match="classe"):
        nome_classe(8)
