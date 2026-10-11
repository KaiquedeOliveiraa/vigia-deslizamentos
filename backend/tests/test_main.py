"""Testes da entrada do processo (Tarefas 11 e 13).

O que é testado aqui é a fiação: leitura do ambiente, horários do agendador,
configuração do log e o código de saída do `--uma-vez`. O ciclo em si (pipeline
+ envio) é coberto por `test_pipeline.py` e `test_avisos.py`; aqui ele entra
como dublê, para que nenhum teste abra rede ou fale com o Telegram.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from telegram.error import InvalidToken

from app import main as modulo_main
from app.bot.regra_aviso import Aviso
from app.calculo.agregacao import Resultado, ResultadoDia, ResultadoMunicipio
from app.classificacao.probabilidades import Probabilidades
from app.modelos import banco
from app.modelos.tipos import DadosMunicipio, Membro
from app.pipeline import Execucao

UTC = timezone.utc
AGORA = datetime(2026, 10, 1, 21, 0, tzinfo=UTC)

CAMINHO_MUNICIPIOS = (
    Path(__file__).resolve().parent.parent / "config" / "municipios.json"
)


def ambiente_de_teste(tmp_path: Path) -> dict[str, str]:
    return {
        "TELEGRAM_TOKEN": "123:ABC",
        "GITHUB_TOKEN_DADOS": "ghp_x",
        "GITHUB_REPO": "dono/repo",
        "SITE_URL": "https://vigia.exemplo.org",
        "DB_PATH": str(tmp_path / "vigia.db"),
        "LOG_PATH": str(tmp_path / "vigia.log"),
    }


def _resultado(com_dados: bool) -> Resultado:
    if not com_dados:
        return Resultado(
            dia_alvo_d0=date(2026, 10, 1), municipios=[], municipios_sem_dados=["4206900"]
        )
    dia = ResultadoDia(
        dia_alvo=date(2026, 10, 1),
        d=0,
        indice=1.2,
        classe=4,
        efr_mm=10.0,
        rtotal_mm=110.0,
        n_membros=3,
        prob=Probabilidades(0.0, 0.0, 0.0),
    )
    return Resultado(
        dia_alvo_d0=date(2026, 10, 1),
        municipios=[
            ResultadoMunicipio(
                ibge="4206900",
                limiar_mm=250.0,
                dias=(dia, dia, dia, dia),
                chuva_acum_mm={"24h": 1.0, "48h": 2.0, "72h": 3.0, "96h": 4.0},
            )
        ],
        municipios_sem_dados=[],
    )


def ciclo_falso(com_dados: bool, registro: list | None = None):
    """Dublê do ciclo (pipeline + envio): devolve uma `Execucao` programada."""

    async def ciclo(config, municipios, agora_utc, **_dependencias):
        if registro is not None:
            registro.append((config, municipios, agora_utc))
        return Execucao(
            resultado=_resultado(com_dados), publicado=com_dados, avisos=[]
        )

    return ciclo


def ciclo_que_abre_o_bot(com_dados: bool = True):
    """Dublê que abre o `abrir_bot` recebido, como o ciclo real faz quando há aviso."""

    async def ciclo(config, municipios, agora_utc, *, abrir_bot=None, **_dependencias):
        async with abrir_bot():
            pass
        return Execucao(
            resultado=_resultado(com_dados), publicado=com_dados, avisos=[]
        )

    return ciclo


# --- --uma-vez ----------------------------------------------------------------


def test_uma_vez_executa_o_ciclo_uma_unica_vez_e_sai_com_zero(tmp_path):
    chamadas: list = []

    codigo = modulo_main.main(
        ["--uma-vez"],
        ambiente=ambiente_de_teste(tmp_path),
        executar_ciclo=ciclo_falso(True, chamadas),
    )

    assert codigo == 0
    assert len(chamadas) == 1


def test_uma_vez_sai_com_um_em_falha_geral(tmp_path):
    codigo = modulo_main.main(
        ["--uma-vez"],
        ambiente=ambiente_de_teste(tmp_path),
        executar_ciclo=ciclo_falso(False),
    )

    assert codigo == 1


def test_uma_vez_recebe_a_config_do_ambiente_e_os_municipios_da_configuracao(tmp_path):
    chamadas: list = []

    modulo_main.main(
        ["--uma-vez"],
        ambiente=ambiente_de_teste(tmp_path),
        executar_ciclo=ciclo_falso(True, chamadas),
    )

    (config, municipios, agora_utc) = chamadas[0]
    assert config.site_url == "https://vigia.exemplo.org"
    assert config.db_path == str(tmp_path / "vigia.db")
    assert {municipio.ibge for municipio in municipios} == {
        "4205100",
        "4206900",
        "4209151",
        "4214003",
        "4219358",
        "4219408",
    }
    assert agora_utc.tzinfo is not None


def test_variavel_de_ambiente_faltando_sai_com_dois_e_nomeia_a_variavel(tmp_path, capsys):
    ambiente = ambiente_de_teste(tmp_path)
    del ambiente["TELEGRAM_TOKEN"]

    codigo = modulo_main.main(
        ["--uma-vez"], ambiente=ambiente, executar_ciclo=ciclo_falso(True)
    )

    assert codigo == 2
    assert "TELEGRAM_TOKEN" in capsys.readouterr().err


# --- log ----------------------------------------------------------------------


def test_configurar_log_escreve_no_arquivo_do_log_path(tmp_path):
    caminho = tmp_path / "subpasta" / "vigia.log"

    modulo_main.configurar_log(str(caminho))
    try:
        logging.getLogger("app.teste").error("linha de teste")
        for manipulador in logging.getLogger().handlers:
            manipulador.flush()

        assert "linha de teste" in caminho.read_text(encoding="utf-8")
    finally:
        modulo_main.encerrar_log()


def test_configurar_log_poe_o_httpx_em_warning_para_nao_vazar_o_token(tmp_path):
    logging.getLogger("httpx").setLevel(logging.INFO)

    modulo_main.configurar_log(str(tmp_path / "vigia.log"))
    try:
        assert logging.getLogger("httpx").level == logging.WARNING
    finally:
        modulo_main.encerrar_log()


# --- horários do agendador ----------------------------------------------------


def test_horarios_do_cron_sao_os_decididos_na_tarefa_0():
    # 9 h depois de cada rodada sinótica (docs/decisoes/ensemble.md §7): a
    # rodada mais lenta (ECMWF) leva ~8 h para ficar disponível.
    assert modulo_main.HORAS_DO_CRON == "3,9,15,21"


def test_agendador_usa_utc_e_as_protecoes_contra_execucao_sobreposta():
    # O agendador não é iniciado: `montar_agendador` só o monta, e o job fica
    # pendente — que é exatamente o que se quer inspecionar aqui, sem subir loop.
    agendador = modulo_main.montar_agendador(lambda: None)

    (job,) = agendador.get_jobs()
    assert str(agendador.timezone) == "UTC"
    assert job.misfire_grace_time == 3600
    assert job.coalesce is True
    assert job.max_instances == 1
    assert str(job.trigger.fields[job.trigger.FIELD_NAMES.index("hour")]) == "3,9,15,21"


# --- token rejeitado não pode vazar no traceback (RNF06) ----------------------


def test_token_rejeitado_nao_aparece_na_saida_nem_no_log(tmp_path, capsys, caplog):
    # O python-telegram-bot põe o token na mensagem de `InvalidToken`
    # ("The token `...` was rejected by the server"). Sem captura, a exceção sobe
    # e o interpretador imprime o traceback com o token em stderr — que o
    # systemd manda para o journal, a cada 10 s por causa do Restart=always.
    token = "123456:token-secreto-que-nao-pode-vazar"
    ambiente = ambiente_de_teste(tmp_path)
    ambiente["TELEGRAM_TOKEN"] = token

    def abrir_bot_que_rejeita_o_token(*_, **__):
        raise InvalidToken(f"The token `{token}` was rejected by the server.")

    codigo = modulo_main.main(
        ["--uma-vez"],
        ambiente=ambiente,
        executar_ciclo=ciclo_que_abre_o_bot(),
        construir_aplicacao=abrir_bot_que_rejeita_o_token,
    )

    capturado = capsys.readouterr()
    assert codigo == 3
    assert token not in capturado.out
    assert token not in capturado.err
    for registro in caplog.records:
        assert token not in registro.getMessage()
    assert token not in (tmp_path / "vigia.log").read_text(encoding="utf-8")


def test_token_rejeitado_registra_o_motivo_sem_a_credencial(tmp_path, caplog):
    ambiente = ambiente_de_teste(tmp_path)
    ambiente["TELEGRAM_TOKEN"] = "123456:token-secreto"

    def abrir_bot_que_rejeita_o_token(*_, **__):
        raise InvalidToken("The token `123456:token-secreto` was rejected by the server.")

    with caplog.at_level(logging.ERROR):
        modulo_main.main(
            ["--uma-vez"],
            ambiente=ambiente,
            executar_ciclo=ciclo_que_abre_o_bot(),
            construir_aplicacao=abrir_bot_que_rejeita_o_token,
        )

    mensagens = " ".join(registro.getMessage() for registro in caplog.records)
    assert "TELEGRAM_TOKEN" in mensagens


# --- executar_ciclo: montagem do bot e fronteira de conexão -------------------


def _dados_de_teste(ibge: str) -> DadosMunicipio:
    """Três membros de peso igual, chuva só em D0, EfR zero.

    `AGORA` é 2026-10-01T21:00Z, logo D0 é 2026-10-01: a antecedente cobre
    2026-09-24T00:00Z em diante e a previsão vai de 2026-10-01T01:00Z a
    2026-10-05T00:00Z. Com o `limiar_mm = 150` de config/municipios.json e 180 mm
    de chuva em D0, o índice do D0 é 1,2 (classe 4) e o município entra em alerta.
    """
    antecedente = {
        datetime(2026, 9, 24, 0, 0, tzinfo=UTC) + timedelta(hours=k): 0.0
        for k in range(190)
    }
    previsao = {
        datetime(2026, 10, 1, 1, 0, tzinfo=UTC) + timedelta(hours=k): 0.0
        for k in range(96)
    }
    previsao[datetime(2026, 10, 1, 1, 0, tzinfo=UTC)] = 180.0
    return DadosMunicipio(
        ibge=ibge,
        antecedente=[antecedente],
        membros=[
            Membro(
                modelo=modelo,
                rodada=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
                chuva=[dict(previsao)],
            )
            for modelo in ("gfs_global", "ecmwf_ifs025", "icon_global")
        ],
    )


def _execucao_com_aviso() -> Execucao:
    return Execucao(
        resultado=_resultado(True),
        publicado=True,
        avisos=[
            Aviso(
                ibge="4206900",
                nome="Ibirama",
                indice=1.2,
                classe=4,
                avisar=True,
                nova_classe=4,
            )
        ],
    )


def _pipeline_falso(execucao: Execucao):
    """Substitui `executar_pipeline` dentro da thread, registrando a conexão vista."""
    vistos: list = []

    def pipeline(agora_utc, municipios, conexao, http, config, **_):
        vistos.append(conexao)
        return execucao

    return pipeline, vistos


def test_sem_aviso_o_bot_nao_e_montado(tmp_path, monkeypatch):
    # R27: inicializar o `Bot` chama a API do Telegram. Fazer isso quando não há
    # nada a enviar é uma ida à rede por execução — foi descoberto por um
    # travamento de teste, e esta asserção é o que impede a regressão.
    config, municipios = modulo_main.carregar_dependencias(ambiente_de_teste(tmp_path))
    sem_aviso = Execucao(resultado=_resultado(True), publicado=True, avisos=[])
    pipeline, _ = _pipeline_falso(sem_aviso)
    monkeypatch.setattr(modulo_main, "executar_pipeline", pipeline)

    def abrir_bot_que_nao_deve_ser_chamado():
        raise AssertionError("o bot não deveria ser montado sem aviso")

    asyncio.run(
        modulo_main.executar_ciclo_padrao(
            config,
            municipios,
            AGORA,
            abrir_bot=abrir_bot_que_nao_deve_ser_chamado,
            conexao_do_bot=banco.abrir(":memory:"),
            http=object(),
        )
    )


def test_com_aviso_o_bot_e_montado_e_o_envio_usa_a_conexao_do_loop(tmp_path, monkeypatch):
    config, municipios = modulo_main.carregar_dependencias(ambiente_de_teste(tmp_path))
    pipeline, conexoes_da_thread = _pipeline_falso(_execucao_com_aviso())
    monkeypatch.setattr(modulo_main, "executar_pipeline", pipeline)

    conexao_do_loop = banco.abrir(":memory:")
    banco.inscrever(conexao_do_loop, 777, "4206900", AGORA)
    enviados: list = []
    montagens: list = []

    class BotDeTeste:
        async def send_message(self, chat_id, text, **_):
            enviados.append(chat_id)

    @asynccontextmanager
    async def abrir_bot():
        montagens.append(True)
        yield BotDeTeste()

    asyncio.run(
        modulo_main.executar_ciclo_padrao(
            config,
            municipios,
            AGORA,
            abrir_bot=abrir_bot,
            conexao_do_bot=conexao_do_loop,
            http=object(),
        )
    )

    assert montagens == [True]
    assert enviados == [777]
    # A classe notificada foi gravada na conexão do loop, que é a que o envio
    # recebeu — e não na que o pipeline abriu dentro da thread.
    assert banco.ultima_classe_notificada(conexao_do_loop, "4206900") == 4
    assert conexoes_da_thread[0] is not conexao_do_loop


def test_a_conexao_do_pipeline_nasce_dentro_da_thread_de_trabalho(tmp_path, monkeypatch):
    # O `sqlite3` recusa uma conexão usada em outra thread (`check_same_thread`
    # fica no padrão). Este teste afirma que a conexão que o pipeline recebe
    # pertence à thread de trabalho, não à do loop — se alguém "otimizar"
    # reaproveitando a conexão do bot, o teste pega.
    config, municipios = modulo_main.carregar_dependencias(ambiente_de_teste(tmp_path))
    threads: list = []

    def pipeline(agora_utc, municipios_, conexao, http, config_, **_):
        threads.append(threading.current_thread().name)
        # Usa a conexão de fato: se ela viesse de outra thread, isto levantaria.
        conexao.execute("SELECT COUNT(*) FROM indices").fetchone()
        return Execucao(resultado=_resultado(True), publicado=True, avisos=[])

    monkeypatch.setattr(modulo_main, "executar_pipeline", pipeline)

    asyncio.run(
        modulo_main.executar_ciclo_padrao(config, municipios, AGORA, http=object())
    )

    assert threads[0] != threading.main_thread().name


def test_ciclo_completo_em_arquivo_grava_o_banco_e_a_classe_notificada(
    tmp_path, monkeypatch
):
    """Ciclo de verdade: pipeline real na thread, envio real no loop, banco em arquivo.

    Só a coleta e a publicação são dubladas. É o teste que cobre, de ponta a
    ponta, o que o item da Tarefa 13 pede do `--uma-vez`: executa o pipeline e
    envia os avisos.
    """
    config, municipios = modulo_main.carregar_dependencias(ambiente_de_teste(tmp_path))
    pipeline_real = modulo_main.executar_pipeline

    def pipeline_com_coleta_dublada(agora_utc, municipios_, conexao, http, config_, **_):
        return pipeline_real(
            agora_utc,
            municipios_,
            conexao,
            http,
            config_,
            relogio=lambda: AGORA,
            coletar=lambda municipio, agora, http_, cache_rodadas=None: _dados_de_teste(
                municipio.ibge
            ),
            publicar=lambda conteudo, cfg, http_: True,
            comparar_com_inmet=lambda *_args, **_kwargs: None,
        )

    monkeypatch.setattr(modulo_main, "executar_pipeline", pipeline_com_coleta_dublada)

    conexao_do_loop = banco.abrir(config.db_path)
    banco.inscrever(conexao_do_loop, 777, "4206900", AGORA)
    enviados: list = []

    class BotDeTeste:
        async def send_message(self, chat_id, text, **_):
            enviados.append((chat_id, text))

    @asynccontextmanager
    async def abrir_bot():
        yield BotDeTeste()

    execucao = asyncio.run(
        modulo_main.executar_ciclo_padrao(
            config,
            municipios,
            AGORA,
            abrir_bot=abrir_bot,
            conexao_do_bot=conexao_do_loop,
            http=object(),
        )
    )

    assert execucao.publicado is True
    # Seis municípios x quatro dias-alvo, gravados pela conexão da thread e
    # legíveis pela do loop — é o WAL que permite isso.
    assert conexao_do_loop.execute("SELECT COUNT(*) FROM indices").fetchone()[0] == 24
    assert len(enviados) == 1
    assert "Ibirama" in enviados[0][1]
    assert banco.ultima_classe_notificada(conexao_do_loop, "4206900") == 4
