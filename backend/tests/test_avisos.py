"""Testes do envio dos avisos (Tarefa 10): bot falso, banco em memória.

`enviar_avisos` é assíncrona; os testes a executam com `asyncio.run` para não
depender de `pytest-asyncio`, que não está nas dependências do projeto.

O bot falso registra cada envio e pode ser programado para falhar por chat, de
modo a provar o que acontece com `Forbidden` (RNF05), com erro transitório e
com a gravação da nova classe.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import pytest
from telegram.error import Forbidden, NetworkError, TelegramError

from app.bot.avisos import enviar_avisos
from app.bot.regra_aviso import Aviso
from app.modelos import banco

UTC = timezone.utc
AGORA = datetime(2026, 10, 1, 21, 0, tzinfo=UTC)
SITE_URL = "https://vigia.exemplo.org"


class BotFalso:
    """Dublê do `telegram.Bot`: registra os envios e levanta erros programados.

    `erros_por_chat` mapeia `chat_id` -> exceção a levantar naquele envio.
    """

    def __init__(self, erros_por_chat: dict[int, Exception] | None = None):
        self.enviados: list[tuple[int, str]] = []
        self.erros_por_chat = erros_por_chat or {}

    async def send_message(self, chat_id: int, text: str, **_):
        erro = self.erros_por_chat.get(chat_id)
        if erro is not None:
            raise erro
        self.enviados.append((chat_id, text))


def conexao():
    return banco.abrir(":memory:")


def aviso(
    ibge: str = "4206900",
    nome: str = "Ibirama",
    indice: float = 1.25,
    classe_do_aviso: int = 4,
    avisar: bool = True,
    nova_classe: int | None = 4,
) -> Aviso:
    return Aviso(
        ibge=ibge,
        nome=nome,
        indice=indice,
        classe=classe_do_aviso,
        avisar=avisar,
        nova_classe=nova_classe,
    )


def executar(bot, conn, avisos, agora=AGORA):
    asyncio.run(enviar_avisos(bot, conn, avisos, agora, SITE_URL))


# --- envio --------------------------------------------------------------------


def test_envia_a_todos_os_inscritos_do_municipio_e_grava_a_nova_classe():
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    banco.inscrever(conn, 2, "4206900", AGORA)
    bot = BotFalso()

    executar(bot, conn, [aviso()])

    assert sorted(chat for chat, _ in bot.enviados) == [1, 2]
    assert banco.ultima_classe_notificada(conn, "4206900") == 4


def test_a_mensagem_enviada_e_a_do_modulo_de_mensagens():
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    bot = BotFalso()

    executar(bot, conn, [aviso()])

    (_, texto), = bot.enviados
    assert "Ibirama" in texto
    assert "1,25" in texto
    assert SITE_URL in texto
    assert "não emite alerta oficial" in texto


def test_nao_envia_para_inscritos_de_outro_municipio():
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    banco.inscrever(conn, 2, "4205100", AGORA)
    bot = BotFalso()

    executar(bot, conn, [aviso()])

    assert [chat for chat, _ in bot.enviados] == [1]


def test_aviso_com_avisar_falso_nao_envia_nada():
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    bot = BotFalso()

    executar(bot, conn, [aviso(avisar=False, nova_classe=4)])

    assert bot.enviados == []


def test_aviso_com_avisar_falso_grava_a_nova_classe_para_zerar():
    # Sair de alerta zera a última classe (RN08). Sem essa gravação, a classe
    # ficaria presa na mais alta já avisada e uma volta ao alerta não avisaria.
    conn = conexao()
    banco.atualizar_ultima_classe_notificada(conn, "4206900", 5, AGORA)
    bot = BotFalso()

    executar(bot, conn, [aviso(avisar=False, nova_classe=None)])

    assert banco.ultima_classe_notificada(conn, "4206900") is None


def test_grava_a_nova_classe_uma_vez_por_municipio_mesmo_com_varios_inscritos():
    conn = conexao()
    for chat in (1, 2, 3):
        banco.inscrever(conn, chat, "4206900", AGORA)
    bot = BotFalso()

    executar(bot, conn, [aviso()])

    linhas = conn.execute(
        "SELECT COUNT(*) FROM notificacoes WHERE ibge = ?", ("4206900",)
    ).fetchone()
    assert linhas[0] == 1


def test_varios_municipios_sao_tratados_de_forma_independente():
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    banco.inscrever(conn, 2, "4205100", AGORA)
    bot = BotFalso()

    executar(
        bot,
        conn,
        [aviso(), aviso(ibge="4205100", nome="Dona Emma", classe_do_aviso=5, nova_classe=5)],
    )

    assert sorted(chat for chat, _ in bot.enviados) == [1, 2]
    assert banco.ultima_classe_notificada(conn, "4206900") == 4
    assert banco.ultima_classe_notificada(conn, "4205100") == 5


# --- Forbidden (chat bloqueou o bot) ------------------------------------------


def test_forbidden_remove_as_inscricoes_do_chat_e_segue_para_os_outros():
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    banco.inscrever(conn, 1, "4205100", AGORA)
    banco.inscrever(conn, 2, "4206900", AGORA)
    bot = BotFalso(erros_por_chat={1: Forbidden("bot was blocked by the user")})

    executar(bot, conn, [aviso()])

    assert [chat for chat, _ in bot.enviados] == [2]
    # RNF05: bloquear o bot apaga todos os registros do chat, não só o deste
    # município.
    assert banco.listar_inscritos(conn, "4206900") == [2]
    assert banco.listar_inscritos(conn, "4205100") == []


def test_forbidden_em_todos_os_inscritos_ainda_grava_a_nova_classe():
    # Não há ninguém para quem reenviar: insistir na próxima execução não muda
    # nada, e deixar a classe sem gravar faria o aviso "pendente" para sempre.
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    bot = BotFalso(erros_por_chat={1: Forbidden("blocked")})

    executar(bot, conn, [aviso()])

    assert banco.ultima_classe_notificada(conn, "4206900") == 4


# --- erros transitórios -------------------------------------------------------


def test_erro_de_rede_num_chat_registra_e_segue_para_o_proximo(caplog):
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    banco.inscrever(conn, 2, "4206900", AGORA)
    bot = BotFalso(erros_por_chat={1: NetworkError("timeout")})

    with caplog.at_level(logging.WARNING):
        executar(bot, conn, [aviso()])

    assert [chat for chat, _ in bot.enviados] == [2]
    assert caplog.records != []


def test_falha_parcial_ainda_grava_a_nova_classe():
    # Alguém recebeu: reenviar na próxima execução duplicaria a mensagem para
    # quem já leu.
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    banco.inscrever(conn, 2, "4206900", AGORA)
    bot = BotFalso(erros_por_chat={1: NetworkError("timeout")})

    executar(bot, conn, [aviso()])

    assert banco.ultima_classe_notificada(conn, "4206900") == 4


def test_todos_os_envios_falhando_por_erro_de_rede_nao_grava_a_nova_classe():
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    banco.inscrever(conn, 2, "4206900", AGORA)
    bot = BotFalso(
        erros_por_chat={1: NetworkError("timeout"), 2: TelegramError("erro qualquer")}
    )

    executar(bot, conn, [aviso()])

    # Nada gravado: a próxima execução decide avisar de novo e reenvia.
    assert banco.ultima_classe_notificada(conn, "4206900") is None
    assert (
        conn.execute("SELECT COUNT(*) FROM notificacoes").fetchone()[0] == 0
    )


def test_todos_os_envios_falhando_preserva_a_classe_anterior():
    conn = conexao()
    banco.atualizar_ultima_classe_notificada(conn, "4206900", 4, AGORA)
    banco.inscrever(conn, 1, "4206900", AGORA)
    bot = BotFalso(erros_por_chat={1: NetworkError("timeout")})

    executar(bot, conn, [aviso(classe_do_aviso=5, nova_classe=5, indice=2.0)])

    assert banco.ultima_classe_notificada(conn, "4206900") == 4


def test_municipio_sem_inscritos_nao_grava_a_nova_classe():
    # Ninguém foi avisado, então nada foi notificado: se alguém se inscrever
    # durante o alerta, recebe o aviso na execução seguinte.
    conn = conexao()
    bot = BotFalso()

    executar(bot, conn, [aviso()])

    assert bot.enviados == []
    assert banco.ultima_classe_notificada(conn, "4206900") is None


def test_falha_num_municipio_nao_impede_o_proximo():
    conn = conexao()
    banco.inscrever(conn, 1, "4206900", AGORA)
    banco.inscrever(conn, 2, "4205100", AGORA)
    bot = BotFalso(erros_por_chat={1: NetworkError("timeout")})

    executar(
        bot,
        conn,
        [aviso(), aviso(ibge="4205100", nome="Dona Emma", classe_do_aviso=5, nova_classe=5)],
    )

    assert [chat for chat, _ in bot.enviados] == [2]
    assert banco.ultima_classe_notificada(conn, "4206900") is None
    assert banco.ultima_classe_notificada(conn, "4205100") == 5


def test_agora_sem_fuso_levanta_erro():
    conn = conexao()
    bot = BotFalso()

    with pytest.raises(ValueError):
        executar(bot, conn, [aviso()], agora=datetime(2026, 10, 1, 21, 0))
