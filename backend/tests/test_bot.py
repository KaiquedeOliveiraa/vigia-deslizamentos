"""Testes da fiação do bot (Tarefa 10): `bot.py` só liga o Telegram às funções.

Nenhum teste fala com o Telegram. Os `handlers` são chamados direto com dublês
de `Update` e de contexto, que é o que permite verificar o comportamento dos
três comandos sem rede e sem token real.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram.ext import CommandHandler, MessageHandler

from app.bot import bot as modulo_bot
from app.bot.inscricao import OPCAO_TODOS
from app.config import Config, Municipio, Ponto
from app.modelos import banco

UTC = timezone.utc
AGORA = datetime(2026, 10, 1, 21, 0, tzinfo=UTC)
CHAT = 42


def municipio(ibge: str, nome: str) -> Municipio:
    return Municipio(
        ibge=ibge,
        nome=nome,
        limiar_mm=250.0,
        fonte_limiar="teste",
        mv_h=24.0,
        pontos=(Ponto(lat=-27.0, lon=-49.5),),
    )


MUNICIPIOS = [municipio("4205100", "Dona Emma"), municipio("4206900", "Ibirama")]


def config_de_teste() -> Config:
    return Config(
        telegram_token="123:ABC",
        github_token_dados="ghp_x",
        github_repo="dono/repo",
        site_url="https://vigia.exemplo.org",
        db_path=":memory:",
        log_path="vigia.log",
    )


class MensagemFalsa:
    """Dublê de `telegram.Message`: guarda as respostas em vez de enviá-las."""

    def __init__(self, texto: str, chat_id: int = CHAT):
        self.text = texto
        self.chat_id = chat_id
        self.respostas: list[str] = []
        self.teclados: list[object] = []

    async def reply_text(self, texto: str, reply_markup=None) -> None:
        self.respostas.append(texto)
        self.teclados.append(reply_markup)


class UpdateFalso:
    def __init__(self, mensagem: MensagemFalsa):
        self.message = mensagem


class ContextoFalso:
    def __init__(self, conexao, args=None):
        self.args = args or []
        self.bot_data = {
            modulo_bot.CHAVE_CONFIG: config_de_teste(),
            modulo_bot.CHAVE_MUNICIPIOS: MUNICIPIOS,
            modulo_bot.CHAVE_CONEXAO: conexao,
            modulo_bot.CHAVE_RELOGIO: lambda: AGORA,
        }


def conexao():
    return banco.abrir(":memory:")


# --- /start -------------------------------------------------------------------


def test_start_mostra_o_teclado_com_os_municipios_e_todos():
    mensagem = MensagemFalsa("/start")

    asyncio.run(modulo_bot.comando_start(UpdateFalso(mensagem), ContextoFalso(conexao())))

    teclado = mensagem.teclados[0].keyboard
    assert [linha[0].text for linha in teclado] == [
        "Dona Emma",
        "Ibirama",
        OPCAO_TODOS,
    ]


def test_start_com_ibge_da_configuracao_sugere_o_municipio_no_texto():
    mensagem = MensagemFalsa("/start 4206900")

    asyncio.run(
        modulo_bot.comando_start(
            UpdateFalso(mensagem), ContextoFalso(conexao(), args=["4206900"])
        )
    )

    assert "Ibirama" in mensagem.respostas[0]


def test_start_com_ibge_fora_da_configuracao_mostra_o_teclado_normal():
    mensagem = MensagemFalsa("/start 3550308")

    asyncio.run(
        modulo_bot.comando_start(
            UpdateFalso(mensagem), ContextoFalso(conexao(), args=["3550308"])
        )
    )

    assert "3550308" not in mensagem.respostas[0]
    teclado = mensagem.teclados[0].keyboard
    assert [linha[0].text for linha in teclado] == ["Dona Emma", "Ibirama", OPCAO_TODOS]


# --- escolha no teclado -------------------------------------------------------


def test_escolher_um_municipio_inscreve_so_ele_e_confirma():
    conn = conexao()
    mensagem = MensagemFalsa("Ibirama")

    asyncio.run(modulo_bot.escolha_do_teclado(UpdateFalso(mensagem), ContextoFalso(conn)))

    assert banco.listar_inscritos(conn, "4206900") == [CHAT]
    assert banco.listar_inscritos(conn, "4205100") == []
    assert "Ibirama" in mensagem.respostas[0]


def test_escolher_todos_inscreve_todos():
    conn = conexao()
    mensagem = MensagemFalsa(OPCAO_TODOS)

    asyncio.run(modulo_bot.escolha_do_teclado(UpdateFalso(mensagem), ContextoFalso(conn)))

    assert banco.listar_inscritos(conn, "4206900") == [CHAT]
    assert banco.listar_inscritos(conn, "4205100") == [CHAT]


def test_texto_desconhecido_nao_inscreve_e_mostra_o_teclado_de_novo():
    conn = conexao()
    mensagem = MensagemFalsa("Blumenau")

    asyncio.run(modulo_bot.escolha_do_teclado(UpdateFalso(mensagem), ContextoFalso(conn)))

    assert banco.listar_inscritos(conn, "4206900") == []
    assert "/start" in mensagem.respostas[0]


# --- /status e /parar ---------------------------------------------------------


def test_status_sem_inscricoes_orienta_a_usar_start():
    mensagem = MensagemFalsa("/status")

    asyncio.run(modulo_bot.comando_status(UpdateFalso(mensagem), ContextoFalso(conexao())))

    assert "/start" in mensagem.respostas[0]


def test_status_lista_os_municipios_inscritos_como_sem_dados_antes_do_primeiro_calculo():
    conn = conexao()
    banco.inscrever(conn, CHAT, "4206900", AGORA)
    mensagem = MensagemFalsa("/status")

    asyncio.run(modulo_bot.comando_status(UpdateFalso(mensagem), ContextoFalso(conn)))

    assert "Ibirama" in mensagem.respostas[0]
    assert "sem dados" in mensagem.respostas[0]


def test_parar_apaga_as_inscricoes_do_chat():
    conn = conexao()
    banco.inscrever(conn, CHAT, "4206900", AGORA)
    banco.inscrever(conn, 999, "4206900", AGORA)
    mensagem = MensagemFalsa("/parar")

    asyncio.run(modulo_bot.comando_parar(UpdateFalso(mensagem), ContextoFalso(conn)))

    assert banco.listar_inscritos(conn, "4206900") == [999]


# --- montagem da aplicação ----------------------------------------------------


def test_aplicacao_registra_os_tres_comandos_e_o_tratador_do_teclado():
    conn = conexao()

    aplicacao = modulo_bot.construir_aplicacao(
        config_de_teste(), MUNICIPIOS, conn, relogio=lambda: AGORA
    )

    handlers = aplicacao.handlers[0]
    comandos = {
        comando
        for handler in handlers
        if isinstance(handler, CommandHandler)
        for comando in handler.commands
    }
    assert comandos == {"start", "status", "parar"}
    assert any(isinstance(handler, MessageHandler) for handler in handlers)


def test_logger_do_httpx_fica_em_warning_porque_a_url_contem_o_token():
    logging.getLogger("httpx").setLevel(logging.INFO)

    modulo_bot.silenciar_url_com_token()

    assert logging.getLogger("httpx").level == logging.WARNING
