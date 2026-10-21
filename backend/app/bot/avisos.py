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

import asyncio
import logging
import sqlite3
import warnings
from datetime import datetime, timedelta

from telegram.constants import ParseMode
from telegram.error import Forbidden, RetryAfter, TelegramError
from telegram.warnings import PTBDeprecationWarning

from app.bot.inscritos import InscritosIndisponiveisError, RepositorioInscritos
from app.bot.mensagens import texto_do_aviso
from app.bot.regra_aviso import Aviso
from app.modelos import banco

_log = logging.getLogger(__name__)

#: Espaço mínimo entre dois envios: o Telegram aceita ~30 msg/s no total.
PAUSA_ENTRE_ENVIOS_S = 0.05
#: Teto da espera pedida pelo Telegram num 429.
ESPERA_MAXIMA_S = 60

_dormir = asyncio.sleep


def _segundos_de_espera(erro: RetryAfter) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PTBDeprecationWarning)
        espera = erro.retry_after
    segundos = espera.total_seconds() if isinstance(espera, timedelta) else float(espera)
    return min(max(segundos, 0.0), ESPERA_MAXIMA_S)


async def _enviar(bot, chat_id: int, texto: str) -> None:
    """Envia; num 429 espera o que o Telegram pediu e tenta uma vez mais."""
    try:
        await bot.send_message(chat_id=chat_id, text=texto, parse_mode=ParseMode.HTML)
    except RetryAfter as erro:
        await _dormir(_segundos_de_espera(erro))
        try:
            await bot.send_message(chat_id=chat_id, text=texto, parse_mode=ParseMode.HTML)
        except Forbidden:
            raise
        except TelegramError as segundo:
            # A especificação pede erro (vira aviso no resumo do Actions); o laço trata como transitória.
            _log.error("aviso não entregue após esperar o limite do Telegram: %s", type(segundo).__name__)
            raise


def _exigir_fuso(nome: str, momento: datetime) -> None:
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError(
            f"'{nome}' precisa ser um datetime com fuso (aware); recebido sem fuso"
        )


async def _enviar_para_um_municipio(
    bot,
    inscritos: RepositorioInscritos,
    chats: list[int],
    aviso: Aviso,
    site_url: str,
) -> tuple[int, int, int]:
    """Envia o aviso a cada inscrito do município.

    Devolve `(tentativas, enviados, falhas_transitorias)`. `Forbidden` (o chat
    bloqueou o bot ou o apagou) apaga os registros daquele chat — RNF05 — e
    **não** conta como falha transitória: não há o que reenviar. Qualquer outro
    erro do Telegram conta como transitório e é registrado, e o laço segue para
    o próximo chat: um chat problemático não pode calar os demais.
    """
    texto = texto_do_aviso(aviso, site_url)

    enviados = 0
    falhas_transitorias = 0
    for chat_id in chats:
        await _dormir(PAUSA_ENTRE_ENVIOS_S)
        try:
            await _enviar(bot, chat_id, texto)
        except Forbidden:
            _log.info(
                "um chat de '%s' bloqueou o bot: apagando as inscrições dele (RNF05)",
                aviso.ibge,
            )
            inscritos.remover_chat(chat_id)
        except TelegramError as erro:
            falhas_transitorias += 1
            _log.warning(
                "falha ao avisar um chat sobre '%s': %s",
                aviso.ibge,
                type(erro).__name__,
            )
        else:
            enviados += 1

    return len(chats), enviados, falhas_transitorias


async def enviar_avisos(
    bot,
    conexao: sqlite3.Connection,
    inscritos: RepositorioInscritos,
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

    Os chats de todos os avisos com `avisar = True` são buscados antes do laço.
    Se a fonte dos inscritos estiver indisponível, nada é enviado e nenhuma
    classe é gravada (nem a dos avisos com `avisar = False`).

    Nunca propaga erro de um município para o seguinte.
    """
    _exigir_fuso("agora_utc", agora_utc)

    try:
        chats_por_ibge = {a.ibge: inscritos.listar(a.ibge) for a in avisos if a.avisar}
    except InscritosIndisponiveisError as erro:
        _log.error(
            "inscritos indisponíveis (%s): nenhum aviso enviado e nenhuma classe gravada",
            erro,
        )
        return
    except Exception:  # noqa: BLE001 — p.ex. `sqlite3.OperationalError` (banco travado)
        # Tratada como fonte indisponível: sem os chats não se envia nem se grava
        # classe; a execução seguinte tenta de novo.
        _log.exception(
            "falha inesperada ao ler os inscritos: nenhum aviso enviado e "
            "nenhuma classe gravada"
        )
        return

    for aviso in avisos:
        # Uma exceção inesperada num município não pode calar os seguintes. O
        # caso realista não é o bot: é `sqlite3.OperationalError` nas escritas,
        # porque a thread do pipeline e este loop gravam no mesmo arquivo e o
        # `timeout` pode esgotar. Sem esta guarda, os municípios restantes
        # ficariam sem gravar a classe e os inscritos do município que já
        # recebeu a mensagem a receberiam de novo na execução seguinte.
        try:
            await _tratar_um_aviso(
                bot,
                conexao,
                inscritos,
                chats_por_ibge.get(aviso.ibge, []),
                aviso,
                agora_utc,
                site_url,
            )
        except Exception:  # noqa: BLE001 — ver comentário acima
            _log.exception(
                "tratamento do aviso de '%s' falhou; seguindo para o próximo município",
                aviso.ibge,
            )


async def _tratar_um_aviso(
    bot,
    conexao: sqlite3.Connection,
    inscritos: RepositorioInscritos,
    chats: list[int],
    aviso: Aviso,
    agora_utc: datetime,
    site_url: str,
) -> None:
    """Envia (se for o caso) e grava a classe notificada de **um** município."""
    if not aviso.avisar:
        banco.atualizar_ultima_classe_notificada(
            conexao, aviso.ibge, aviso.nova_classe, agora_utc
        )
        return

    tentativas, enviados, falhas = await _enviar_para_um_municipio(
        bot, inscritos, chats, aviso, site_url
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
