"""Ligação entre o Telegram e as funções do bot. Só fiação, nenhuma regra.

Os comandos traduzem a mensagem recebida em chamadas a `app.bot.inscricao` e
`app.bot.mensagens`, que são testados sem Telegram nenhum. Toda dependência
entra por parâmetro em `construir_aplicacao`: a `Config` (de onde vem o token e
a URL do site), a lista de municípios, a conexão SQLite **desta thread** e o
relógio.

Segurança (RNF06): o token vive só na `Config` e na URL que a biblioteca monta
internamente. É por isso que o logger do `httpx` é posto em `WARNING` — em
`INFO` ele registra a URL de cada requisição, e a URL da API do Telegram contém
o token.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot.inscricao import (
    OPCAO_TODOS,
    inscrever_escolha,
    municipio_sugerido,
    opcoes_do_teclado,
    parar,
    situacoes_do_chat,
)
from app.bot.mensagens import RESSALVA_RN04, texto_do_status
from app.config import Config, Municipio

_log = logging.getLogger(__name__)

#: Chaves usadas em `application.bot_data` para carregar as dependências.
CHAVE_CONFIG = "config"
CHAVE_MUNICIPIOS = "municipios"
CHAVE_CONEXAO = "conexao"
CHAVE_RELOGIO = "relogio"


def silenciar_url_com_token() -> None:
    """Põe o logger do `httpx` em `WARNING`, porque em `INFO` ele loga a URL.

    A URL de toda chamada à API do Telegram contém o token do bot; registrá-la
    no arquivo de log vazaria a credencial (RNF06).
    """
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _teclado(municipios: list[Municipio]) -> ReplyKeyboardMarkup:
    """Teclado de uma coluna com os municípios da configuração e "Todos"."""
    return ReplyKeyboardMarkup(
        [[opcao] for opcao in opcoes_do_teclado(municipios)],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def comando_start(update: Update, contexto: ContextTypes.DEFAULT_TYPE) -> None:
    """`/start [ibge]`: mostra o teclado e, com o parâmetro, já sugere o município.

    Um código fora da configuração é ignorado em silêncio e o teclado normal
    aparece — o parâmetro vem de um link externo e não é confiável.
    """
    municipios = contexto.bot_data[CHAVE_MUNICIPIOS]
    argumento = contexto.args[0] if contexto.args else None
    sugerido = municipio_sugerido(municipios, argumento)

    saudacao = (
        "Olá! Escolha os municípios que quer acompanhar no VIGIA.\n\n"
        f"Toque em um município ou em \"{OPCAO_TODOS}\". "
        "Use /status para ver a situação e /parar para cancelar."
    )
    if sugerido is not None:
        saudacao = (
            f"Olá! O link veio de {sugerido.nome} — toque em \"{sugerido.nome}\" "
            f"para se inscrever só nele, ou em \"{OPCAO_TODOS}\" "
            "para acompanhar todos.\n\n"
            "Use /status para ver a situação e /parar para cancelar."
        )

    await update.message.reply_text(saudacao, reply_markup=_teclado(municipios))


async def escolha_do_teclado(update: Update, contexto: ContextTypes.DEFAULT_TYPE) -> None:
    """Trata o toque num botão do teclado do `/start`."""
    municipios = contexto.bot_data[CHAVE_MUNICIPIOS]
    conexao = contexto.bot_data[CHAVE_CONEXAO]
    relogio = contexto.bot_data[CHAVE_RELOGIO]

    inscritos = inscrever_escolha(
        conexao, municipios, update.message.chat_id, update.message.text, relogio()
    )

    if not inscritos:
        await update.message.reply_text(
            "Não reconheci essa opção. Use /start para ver a lista de municípios.",
            reply_markup=_teclado(municipios),
        )
        return

    nomes = [
        municipio.nome for municipio in municipios if municipio.ibge in inscritos
    ]
    await update.message.reply_text(
        "Pronto! Você vai receber avisos de: " + ", ".join(nomes) + ".\n\n"
        f"{RESSALVA_RN04}",
        reply_markup=ReplyKeyboardRemove(),
    )


async def comando_status(update: Update, contexto: ContextTypes.DEFAULT_TYPE) -> None:
    """`/status`: índice e classe atuais (D0) dos municípios inscritos."""
    config = contexto.bot_data[CHAVE_CONFIG]
    municipios = contexto.bot_data[CHAVE_MUNICIPIOS]
    conexao = contexto.bot_data[CHAVE_CONEXAO]

    situacoes = situacoes_do_chat(conexao, municipios, update.message.chat_id)
    await update.message.reply_text(texto_do_status(situacoes, config.site_url))


async def comando_parar(update: Update, contexto: ContextTypes.DEFAULT_TYPE) -> None:
    """`/parar`: apaga todos os registros do chat (RNF05)."""
    conexao = contexto.bot_data[CHAVE_CONEXAO]
    parar(conexao, update.message.chat_id)
    await update.message.reply_text(
        "Suas inscrições foram apagadas. Use /start quando quiser voltar.",
        reply_markup=ReplyKeyboardRemove(),
    )


def construir_aplicacao(
    config: Config,
    municipios: list[Municipio],
    conexao: sqlite3.Connection,
    relogio: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    post_init=None,
    post_shutdown=None,
) -> Application:
    """Monta a `Application` do python-telegram-bot com os três comandos.

    `conexao` tem de ser a conexão SQLite **desta** thread: o pipeline agendado
    roda em outra e abre a sua (Tarefa 11). O token vem só de
    `config.telegram_token`; nenhum módulo lê `os.environ`.

    `post_init` e `post_shutdown` são os ganchos que o `run_polling` chama dentro
    do loop que ele cria — é por eles que `app/main.py` sobe e desce o agendador
    no mesmo loop do bot.
    """
    silenciar_url_com_token()

    construtor = ApplicationBuilder().token(config.telegram_token)
    if post_init is not None:
        construtor = construtor.post_init(post_init)
    if post_shutdown is not None:
        construtor = construtor.post_shutdown(post_shutdown)
    aplicacao = construtor.build()
    aplicacao.bot_data.update(
        {
            CHAVE_CONFIG: config,
            CHAVE_MUNICIPIOS: municipios,
            CHAVE_CONEXAO: conexao,
            CHAVE_RELOGIO: relogio,
        }
    )

    aplicacao.add_handler(CommandHandler("start", comando_start))
    aplicacao.add_handler(CommandHandler("status", comando_status))
    aplicacao.add_handler(CommandHandler("parar", comando_parar))
    aplicacao.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, escolha_do_teclado)
    )
    return aplicacao
