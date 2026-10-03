"""Testes da regra de aviso (Tarefa 8, RN08).

A tabela de decisão do plano está transcrita literalmente em
`CASOS_DA_TABELA`: cada linha é (última classe, índice do D0) -> (avisa?, nova
última classe). Nada aqui chama `classe()` para montar o esperado — as classes
dos índices usados estão escritas à mão no comentário de cada linha.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.bot.regra_aviso import Aviso, decidir

#: (última classe, índice do D0, avisa?, nova última classe)
CASOS_DA_TABELA = [
    (None, 1.20, True, 4),  # nenhuma classe anterior, entra em alerta (classe 4)
    (4, 1.50, False, 4),  # continua na classe 4: não repete
    (4, 2.00, True, 5),  # sobe para a classe 5: avisa
    (5, 1.50, False, 5),  # desce para 4 mas segue em alerta: não avisa, mantém 5
    (5, 0.90, False, None),  # sai de alerta (< 1,00): zera
    (None, 1.20, True, 4),  # depois de zerar, voltar ao alerta avisa de novo
    (4, None, False, 4),  # sem dados nesta execução: não avisa e mantém
]


@pytest.mark.parametrize(
    ("ultima_classe", "indice_d0", "avisa_esperado", "nova_classe_esperada"),
    CASOS_DA_TABELA,
)
def test_tabela_de_decisao_da_rn08(
    ultima_classe, indice_d0, avisa_esperado, nova_classe_esperada
):
    assert decidir(ultima_classe, indice_d0) == (avisa_esperado, nova_classe_esperada)


def test_fronteira_do_alerta_e_1_00_inclusive():
    # 0,9999 não está em alerta (classe 3); 1,00 está (classe 4). Literais
    # exatos, sem `approx`, como manda a convenção do plano.
    assert decidir(None, 0.9999) == (False, None)
    assert decidir(None, 1.00) == (True, 4)


def test_sair_de_alerta_zera_mesmo_vindo_da_classe_mais_alta():
    assert decidir(7, 0.39) == (False, None)


def test_subir_duas_classes_de_uma_vez_avisa_com_a_classe_nova():
    assert decidir(4, 3.50) == (True, 7)


def test_sem_dados_e_sem_classe_anterior_nao_avisa_e_segue_sem_classe():
    assert decidir(None, None) == (False, None)


def test_aviso_e_imutavel_e_tem_os_campos_que_o_bot_e_o_pipeline_usam():
    aviso = Aviso(
        ibge="4206900",
        nome="Ibirama",
        indice=1.2,
        classe=4,
        avisar=True,
        nova_classe=4,
    )

    assert (aviso.ibge, aviso.nome, aviso.indice, aviso.classe) == (
        "4206900",
        "Ibirama",
        1.2,
        4,
    )
    assert (aviso.avisar, aviso.nova_classe) == (True, 4)
    with pytest.raises(FrozenInstanceError):
        aviso.avisar = False
