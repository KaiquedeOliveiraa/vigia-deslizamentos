"""Testes da inscrição do bot (Tarefa 10): banco em memória, sem rede.

Estas funções são a ponte entre os comandos do Telegram e o banco; elas não
tocam na rede nem no relógio (`agora_utc` entra por parâmetro). Quem fala com o
Telegram é só `app/bot/bot.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.bot.inscricao import (
    OPCAO_TODOS,
    inscrever_escolha,
    municipio_sugerido,
    opcoes_do_teclado,
    parar,
    situacoes_do_chat,
)
from app.calculo.agregacao import Resultado, ResultadoDia, ResultadoMunicipio
from app.classificacao.probabilidades import Probabilidades
from app.config import Municipio, Ponto
from app.modelos import banco

UTC = timezone.utc
AGORA = datetime(2026, 10, 1, 21, 0, tzinfo=UTC)
CHAT = 123456


def municipio(ibge: str, nome: str) -> Municipio:
    return Municipio(
        ibge=ibge,
        nome=nome,
        limiar_mm=250.0,
        fonte_limiar="teste",
        mv_h=24.0,
        pontos=(Ponto(lat=-27.0, lon=-49.5),),
    )


MUNICIPIOS = [
    municipio("4205100", "Dona Emma"),
    municipio("4206900", "Ibirama"),
    municipio("4209151", "José Boiteux"),
]


def conexao():
    return banco.abrir(":memory:")


# --- teclado ------------------------------------------------------------------


def test_teclado_traz_os_municipios_da_configuracao_e_a_opcao_todos():
    assert opcoes_do_teclado(MUNICIPIOS) == [
        "Dona Emma",
        "Ibirama",
        "José Boiteux",
        OPCAO_TODOS,
    ]


# --- município sugerido pelo parâmetro do /start ------------------------------


def test_start_com_ibge_da_configuracao_sugere_aquele_municipio():
    sugerido = municipio_sugerido(MUNICIPIOS, "4206900")

    assert sugerido is not None
    assert sugerido.nome == "Ibirama"


def test_start_com_ibge_fora_da_configuracao_nao_sugere_nada():
    assert municipio_sugerido(MUNICIPIOS, "3550308") is None


def test_start_sem_parametro_nao_sugere_nada():
    assert municipio_sugerido(MUNICIPIOS, None) is None
    assert municipio_sugerido(MUNICIPIOS, "") is None


def test_start_com_parametro_que_nao_e_codigo_nao_sugere_nada():
    assert municipio_sugerido(MUNICIPIOS, "ibirama") is None


# --- inscrição ----------------------------------------------------------------


def test_escolher_um_municipio_inscreve_so_ele():
    conn = conexao()

    inscritos = inscrever_escolha(conn, MUNICIPIOS, CHAT, "Ibirama", AGORA)

    assert inscritos == ["4206900"]
    assert banco.listar_inscritos(conn, "4206900") == [CHAT]
    assert banco.listar_inscritos(conn, "4205100") == []
    assert banco.listar_inscritos(conn, "4209151") == []


def test_escolher_todos_inscreve_todos_os_municipios_configurados():
    conn = conexao()

    inscritos = inscrever_escolha(conn, MUNICIPIOS, CHAT, OPCAO_TODOS, AGORA)

    assert inscritos == ["4205100", "4206900", "4209151"]
    for ibge in inscritos:
        assert banco.listar_inscritos(conn, ibge) == [CHAT]


def test_escolha_desconhecida_nao_inscreve_ninguem():
    conn = conexao()

    assert inscrever_escolha(conn, MUNICIPIOS, CHAT, "Blumenau", AGORA) == []
    for municipio_configurado in MUNICIPIOS:
        assert banco.listar_inscritos(conn, municipio_configurado.ibge) == []


def test_escolher_o_mesmo_municipio_duas_vezes_nao_duplica():
    conn = conexao()

    inscrever_escolha(conn, MUNICIPIOS, CHAT, "Ibirama", AGORA)
    inscrever_escolha(conn, MUNICIPIOS, CHAT, "Ibirama", AGORA)

    assert banco.listar_inscritos(conn, "4206900") == [CHAT]


def test_inscricao_com_agora_sem_fuso_levanta_erro():
    conn = conexao()

    with pytest.raises(ValueError):
        inscrever_escolha(conn, MUNICIPIOS, CHAT, "Ibirama", datetime(2026, 10, 1, 21, 0))


# --- /parar -------------------------------------------------------------------


def test_parar_remove_todas_as_inscricoes_do_chat_e_so_as_dele():
    conn = conexao()
    inscrever_escolha(conn, MUNICIPIOS, CHAT, OPCAO_TODOS, AGORA)
    inscrever_escolha(conn, MUNICIPIOS, 999, "Ibirama", AGORA)

    parar(conn, CHAT)

    assert banco.listar_inscritos(conn, "4206900") == [999]
    assert banco.listar_inscritos(conn, "4205100") == []


# --- situações para o /status -------------------------------------------------


def _gravar_calculo(conn, ibge: str, indice: float, classe_do_dia: int) -> None:
    resultado = Resultado(
        dia_alvo_d0=AGORA.date(),
        municipios=[
            ResultadoMunicipio(
                ibge=ibge,
                limiar_mm=250.0,
                dias=(
                    ResultadoDia(
                        dia_alvo=AGORA.date(),
                        d=0,
                        indice=indice,
                        classe=classe_do_dia,
                        efr_mm=10.0,
                        rtotal_mm=20.0,
                        n_membros=4,
                        prob=Probabilidades(0.0, 0.0, 0.0),
                    ),
                ),
                chuva_acum_mm={"24h": 1.0, "48h": 2.0, "72h": 3.0, "96h": 4.0},
            )
        ],
        municipios_sem_dados=[],
    )
    banco.gravar_resultado(conn, resultado, AGORA)


def test_situacoes_do_chat_segue_a_ordem_da_configuracao_e_so_os_inscritos():
    conn = conexao()
    inscrever_escolha(conn, MUNICIPIOS, CHAT, "Ibirama", AGORA)
    inscrever_escolha(conn, MUNICIPIOS, CHAT, "Dona Emma", AGORA)
    _gravar_calculo(conn, "4206900", 1.25, 4)

    situacoes = situacoes_do_chat(conn, MUNICIPIOS, CHAT)

    assert [nome for nome, _ in situacoes] == ["Dona Emma", "Ibirama"]
    assert situacoes[0][1] is None  # Dona Emma inscrita, sem cálculo gravado
    assert situacoes[1][1].indice == 1.25
    assert situacoes[1][1].classe == 4


def test_situacoes_do_chat_sem_inscricoes_e_lista_vazia():
    conn = conexao()
    _gravar_calculo(conn, "4206900", 1.25, 4)

    assert situacoes_do_chat(conn, MUNICIPIOS, CHAT) == []
