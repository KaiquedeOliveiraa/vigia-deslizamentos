"""Envio dos avisos aos inscritos e gravação da classe notificada.

Assíncrona porque o `telegram.Bot` é assíncrono; o bot e a conexão SQLite entram
por parâmetro, e o relógio também (`agora_utc`). Roda no loop do processo do bot
(Tarefa 11), depois de o pipeline ter decidido os avisos.

Ordem importante: **envia primeiro, grava depois**. Gravar antes faria um aviso
perdido por falha de rede nunca ser reenviado, porque a execução seguinte veria
a classe já notificada e decidiria não avisar.

Limitação aceita: se o processo cair entre o envio e a gravação, o aviso pode
se repetir na execução seguinte. É preferível a perder um aviso — e é a escolha
que o plano registra.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from telegram.error import Forbidden, TelegramError

from app.bot.mensagens import texto_do_aviso
from app.bot.regra_aviso import Aviso
from app.modelos import banco

_log = logging.getLogger(__name__)


def _exigir_fuso(nome: str, momento: datetime) -> None:
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError(
            f"'{nome}' precisa ser um datetime com fuso (aware); recebido sem fuso"
        )


async def _enviar_para_um_municipio(
    bot, conexao: sqlite3.Connection, aviso: Aviso, site_url: str
) -> tuple[int, int, int]:
    """Envia o aviso a cada inscrito do município.

    Devolve `(tentativas, enviados, falhas_transitorias)`. `Forbidden` (o chat
    bloqueou o bot ou o apagou) apaga os registros daquele chat — RNF05 — e
    **não** conta como falha transitória: não há o que reenviar. Qualquer outro
    erro do Telegram conta como transitório e é registrado, e o laço segue para
    o próximo chat: um chat problemático não pode calar os demais.
    """
    texto = texto_do_aviso(aviso, site_url)
    chats = banco.listar_inscritos(conexao, aviso.ibge)

    enviados = 0
    falhas_transitorias = 0
    for chat_id in chats:
        try:
            await bot.send_message(chat_id=chat_id, text=texto)
        except Forbidden:
            _log.info(
                "chat %s bloqueou o bot: apagando as inscrições dele (RNF05)", chat_id
            )
            banco.remover_inscricoes(conexao, chat_id)
        except TelegramError as erro:
            falhas_transitorias += 1
            _log.warning(
                "falha ao avisar o chat %s sobre '%s': %s",
                chat_id,
                aviso.ibge,
                type(erro).__name__,
            )
        else:
            enviados += 1

    return len(chats), enviados, falhas_transitorias


async def enviar_avisos(
    bot,
    conexao: sqlite3.Connection,
    avisos: list[Aviso],
    agora_utc: datetime,
    site_url: str,
) -> None:
    """Envia os avisos marcados e grava a nova última classe de cada município.

    Para um aviso com `avisar = False` nada é enviado, mas `nova_classe` **é**
    gravada: é assim que sair de alerta zera a classe (RN08) e que um município
    sem dados mantém a classe anterior.

    Para um aviso com `avisar = True`, a nova classe é gravada quando alguém
    recebeu a mensagem, ou quando houve inscritos e nenhuma falha transitória
    (caso em que todos bloquearam o bot). Se **todos** os envios falharam por
    erro transitório, nada é gravado — a execução seguinte decide avisar de novo
    e reenvia. Município sem inscrito nenhum também não grava: não houve
    notificação, e quem se inscrever durante o alerta recebe o aviso na próxima
    execução.

    Nunca propaga erro de um município para o seguinte.
    """
    _exigir_fuso("agora_utc", agora_utc)

    for aviso in avisos:
        if not aviso.avisar:
            banco.atualizar_ultima_classe_notificada(
                conexao, aviso.ibge, aviso.nova_classe, agora_utc
            )
            continue

        tentativas, enviados, falhas = await _enviar_para_um_municipio(
            bot, conexao, aviso, site_url
        )

        if enviados > 0 or (tentativas > 0 and falhas == 0):
            banco.atualizar_ultima_classe_notificada(
                conexao, aviso.ibge, aviso.nova_classe, agora_utc
            )
            _log.info(
                "aviso de '%s' enviado a %s de %s inscrito(s); classe notificada: %s",
                aviso.ibge,
                enviados,
                tentativas,
                aviso.nova_classe,
            )
        else:
            _log.warning(
                "aviso de '%s' não chegou a ninguém (%s inscrito(s), %s falha(s)): "
                "a classe notificada não foi gravada e o aviso será reenviado",
                aviso.ibge,
                tentativas,
                falhas,
            )
