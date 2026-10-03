"""Entrada do processo: bot em long polling e pipeline agendado, num só asyncio.

Este é o **único** módulo que lê `os.environ` e o único que cria o cliente HTTP e
as conexões SQLite. Tudo o mais recebe essas dependências por parâmetro.

Um processo, um loop: o bot do Telegram atende no loop e o `AsyncIOScheduler`
dispara o pipeline nos horários da `docs/decisoes/ensemble.md` §7 (9 h depois de
cada rodada sinótica, porque a rodada mais lenta — ECMWF — leva ~8 h para ficar
disponível). O pipeline é síncrono e roda em `asyncio.to_thread`, com conexão
SQLite **aberta dentro da thread**: o `sqlite3` recusa uma conexão usada em outra
thread, e o WAL é o que permite as duas conexões conviverem.

Modos:

- sem argumento: roda para sempre (bot + agendador);
- `--uma-vez`: faz uma execução, envia os avisos e sai. Código 0 em sucesso, 1
  quando nenhum município foi calculado, 2 quando a configuração está incompleta.
  Rodar isso com o serviço no ar significa dois processos gravando e avisos
  duplicados — ver `backend/README.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Callable, Coroutine, Mapping
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from telegram.error import InvalidToken

from app.bot.avisos import enviar_avisos
from app.bot.bot import construir_aplicacao as construir_aplicacao_padrao
from app.bot.bot import silenciar_url_com_token
from app.config import (
    Config,
    ConfiguracaoInvalidaError,
    Municipio,
    carregar_env,
    carregar_municipios,
)
from app.modelos import banco
from app.pipeline import Execucao, executar_pipeline

#: Horas UTC em que o pipeline roda (`docs/decisoes/ensemble.md` §7).
HORAS_DO_CRON = "3,9,15,21"

#: 1 h de tolerância para uma execução perdida (máquina suspensa, reinício) e
#: `coalesce` para que várias perdidas virem uma só. `max_instances=1` impede
#: duas execuções simultâneas gravando no mesmo banco.
TOLERANCIA_DE_ATRASO_S = 3600

#: Códigos de saída. `CODIGO_TOKEN_REJEITADO` existe separado porque é falha
#: permanente: reiniciar não resolve, e o `vigia.service` usa
#: `RestartPreventExitStatus` para não entrar em laço de 10 s.
CODIGO_SUCESSO = 0
CODIGO_FALHA_GERAL = 1
CODIGO_CONFIGURACAO_INVALIDA = 2
CODIGO_TOKEN_REJEITADO = 3

CAMINHO_MUNICIPIOS = Path(__file__).resolve().parent.parent / "config" / "municipios.json"

_log = logging.getLogger(__name__)

#: Manipuladores que `configurar_log` instalou, para `encerrar_log` desfazer.
_manipuladores_instalados: list[logging.Handler] = []


def configurar_log(log_path: str) -> None:
    """Registra no arquivo `log_path` e também na saída padrão.

    O logger do `httpx` vai para `WARNING`: em `INFO` ele registra a URL de cada
    requisição, e a URL da API do Telegram contém o token (RNF06).
    """
    caminho = Path(log_path)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    formato = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    arquivo = logging.FileHandler(caminho, encoding="utf-8")
    arquivo.setFormatter(formato)
    console = logging.StreamHandler()
    console.setFormatter(formato)

    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    for manipulador in (arquivo, console):
        raiz.addHandler(manipulador)
        _manipuladores_instalados.append(manipulador)

    silenciar_url_com_token()


def encerrar_log() -> None:
    """Remove e fecha os manipuladores instalados por `configurar_log`."""
    raiz = logging.getLogger()
    while _manipuladores_instalados:
        manipulador = _manipuladores_instalados.pop()
        raiz.removeHandler(manipulador)
        manipulador.close()


def carregar_dependencias(
    ambiente: Mapping[str, str],
) -> tuple[Config, list[Municipio]]:
    """Lê a `Config` do ambiente e os municípios da configuração versionada."""
    return carregar_env(ambiente), carregar_municipios(CAMINHO_MUNICIPIOS)


def _executar_na_thread(
    agora_utc: datetime, municipios: list[Municipio], config: Config, http
) -> Execucao:
    """Abre a conexão desta thread, roda o pipeline e fecha a conexão.

    A conexão nasce e morre aqui porque o `sqlite3` recusa uma conexão criada em
    outra thread, e esta função é o corpo do `asyncio.to_thread`.
    """
    conexao = banco.abrir(config.db_path)
    try:
        return executar_pipeline(agora_utc, municipios, conexao, http, config)
    finally:
        conexao.close()


@asynccontextmanager
async def bot_temporario(
    config: Config,
    municipios: list[Municipio],
    conexao,
    construir_aplicacao=construir_aplicacao_padrao,
):
    """Um `Bot` inicializado e desmontado no fim, sem abrir long polling.

    `async with aplicacao` é o que inicializa o `Bot` — sem isso `send_message`
    recusa. A inicialização fala com a API do Telegram, então este gerenciador só
    é aberto quando há mesmo aviso a enviar.
    """
    aplicacao = construir_aplicacao(config, municipios, conexao)
    async with aplicacao:
        yield aplicacao.bot


async def executar_ciclo_padrao(
    config: Config,
    municipios: list[Municipio],
    agora_utc: datetime,
    *,
    bot=None,
    abrir_bot: Callable[[], object] | None = None,
    conexao_do_bot=None,
    http=None,
    relogio: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> Execucao:
    """Uma execução completa: pipeline numa thread e envio dos avisos no loop.

    O pipeline roda sempre. O bot só entra se houver aviso: no processo em pé ele
    já existe e vem em `bot`; no modo `--uma-vez`, `abrir_bot` monta um
    temporário, e não montá-lo quando não há aviso evita uma ida à API do
    Telegram por execução.

    O envio usa a conexão **do loop** (`conexao_do_bot`), nunca a que o pipeline
    usou na thread: o `sqlite3` recusa uma conexão vinda de outra thread.

    `agora_utc` é o instante de referência do cálculo; o `notificado_em` gravado
    em `notificacoes` sai de `relogio()`, lido depois do envio, porque é quando a
    notificação de fato aconteceu.
    """
    criou_http = http is None
    http = http or requests.Session()
    try:
        execucao = await asyncio.to_thread(
            _executar_na_thread, agora_utc, municipios, config, http
        )
    finally:
        if criou_http:
            http.close()

    if not execucao.avisos:
        return execucao

    conexao = conexao_do_bot if conexao_do_bot is not None else banco.abrir(config.db_path)
    try:
        if bot is not None:
            await enviar_avisos(
                bot, conexao, execucao.avisos, relogio(), config.site_url
            )
        elif abrir_bot is not None:
            async with abrir_bot() as bot_do_envio:
                await enviar_avisos(
                    bot_do_envio, conexao, execucao.avisos, relogio(), config.site_url
                )
        else:
            _log.warning(
                "%s aviso(s) decidido(s) sem bot disponível: nada foi enviado",
                len(execucao.avisos),
            )
    finally:
        if conexao_do_bot is None:
            conexao.close()

    return execucao


def montar_agendador(job: Callable[[], Coroutine | None]) -> AsyncIOScheduler:
    """`AsyncIOScheduler` em UTC com o cron da Tarefa 0 e as proteções do plano."""
    agendador = AsyncIOScheduler(timezone=timezone.utc)
    agendador.add_job(
        job,
        trigger=CronTrigger(hour=HORAS_DO_CRON, minute=0, timezone=timezone.utc),
        misfire_grace_time=TOLERANCIA_DE_ATRASO_S,
        coalesce=True,
        max_instances=1,
        name="pipeline",
    )
    return agendador


async def _uma_execucao_isolada(
    config: Config,
    municipios: list[Municipio],
    agora_utc: datetime,
    executar: Callable[..., Coroutine],
    construir_aplicacao=construir_aplicacao_padrao,
) -> Execucao:
    """Roda um ciclo com um bot montado só se houver aviso — modo `--uma-vez`."""
    conexao = banco.abrir(config.db_path)
    try:
        return await executar(
            config,
            municipios,
            agora_utc,
            abrir_bot=lambda: bot_temporario(
                config, municipios, conexao, construir_aplicacao
            ),
            conexao_do_bot=conexao,
        )
    finally:
        conexao.close()


def _rodar_para_sempre(
    config: Config,
    municipios: list[Municipio],
    executar: Callable[..., Coroutine],
    relogio: Callable[[], datetime],
    construir_aplicacao=construir_aplicacao_padrao,
) -> None:
    """Bot em long polling com o agendador no mesmo loop.

    O agendador sobe no `post_init` e desce no `post_shutdown` para viver no
    loop que o `run_polling` cria — é o único jeito de bot e agendador
    compartilharem um loop sem um gerenciar o do outro.
    """
    conexao_do_bot = banco.abrir(config.db_path)
    agendadores: list[AsyncIOScheduler] = []

    async def job() -> None:
        try:
            await executar(
                config,
                municipios,
                relogio(),
                bot=aplicacao.bot,
                conexao_do_bot=conexao_do_bot,
            )
        except Exception:  # noqa: BLE001 — um job que levanta mata o agendador
            _log.exception("execução agendada falhou")

    async def ao_iniciar(_aplicacao) -> None:
        agendador = montar_agendador(job)
        agendador.start()
        agendadores.append(agendador)
        _log.info("agendador no ar: horas %s UTC", HORAS_DO_CRON)

    async def ao_encerrar(_aplicacao) -> None:
        for agendador in agendadores:
            agendador.shutdown(wait=False)

    aplicacao = construir_aplicacao(
        config, municipios, conexao_do_bot, post_init=ao_iniciar, post_shutdown=ao_encerrar
    )
    try:
        aplicacao.run_polling()
    finally:
        conexao_do_bot.close()


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        prog="python -m app.main", description="VIGIA Deslizamentos — backend"
    )
    analisador.add_argument(
        "--uma-vez",
        action="store_true",
        help=(
            "faz uma execução do pipeline, envia os avisos e sai; "
            "rodar com o serviço no ar duplica os avisos"
        ),
    )
    return analisador.parse_args(argv)


def main(
    argv: list[str] | None = None,
    ambiente: Mapping[str, str] | None = None,
    *,
    executar_ciclo: Callable[..., Coroutine] | None = None,
    relogio: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    construir_aplicacao=construir_aplicacao_padrao,
) -> int:
    """Ponto de entrada. Devolve o código de saída do processo.

    `ambiente`, `executar_ciclo` e `construir_aplicacao` existem para o teste: em
    produção são `os.environ`, `executar_ciclo` e o construtor do bot. Códigos de
    saída: 0 em sucesso, 1 quando nenhum município foi calculado, 2 quando a
    configuração está incompleta, 3 quando o Telegram rejeitou o token.
    """
    argumentos = _argumentos(argv)
    ambiente = os.environ if ambiente is None else ambiente
    ciclo = executar_ciclo or executar_ciclo_padrao

    try:
        config, municipios = carregar_dependencias(ambiente)
    except ConfiguracaoInvalidaError as erro:
        print(f"configuração inválida: {erro}", file=sys.stderr)
        return CODIGO_CONFIGURACAO_INVALIDA

    configurar_log(config.log_path)
    try:
        # `InvalidToken` do python-telegram-bot traz **o token** na mensagem
        # ("The token `...` was rejected by the server"). Deixá-la subir faria o
        # interpretador imprimir o traceback com a credencial em stderr, que o
        # systemd manda para o journal — e com `Restart=always` isso se repetiria
        # a cada 10 s. Capturamos aqui e registramos só o nome da variável
        # (RNF06). Note que `silenciar_url_com_token()` não cobre este caminho:
        # ele vem da mensagem da exceção, não do logger do httpx.
        try:
            if argumentos.uma_vez:
                execucao = asyncio.run(
                    _uma_execucao_isolada(
                        config, municipios, relogio(), ciclo, construir_aplicacao
                    )
                )
                if not execucao.resultado.municipios:
                    _log.error("execução única terminou sem nenhum município calculado")
                    return CODIGO_FALHA_GERAL
                return CODIGO_SUCESSO

            _rodar_para_sempre(
                config, municipios, ciclo, relogio, construir_aplicacao
            )
            return CODIGO_SUCESSO
        except InvalidToken:
            _log.error(
                "o Telegram rejeitou o token do bot: confira TELEGRAM_TOKEN no "
                "arquivo de ambiente (a credencial não é registrada aqui de "
                "propósito)"
            )
            return CODIGO_TOKEN_REJEITADO
    finally:
        encerrar_log()


if __name__ == "__main__":
    raise SystemExit(main())
