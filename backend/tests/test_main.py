"""Testes da entrada do processo (Tarefas 11 e 13).

O que é testado aqui é a fiação: leitura do ambiente, horários do agendador,
configuração do log e o código de saída do `--uma-vez`. O ciclo em si (pipeline
+ envio) é coberto por `test_pipeline.py` e `test_avisos.py`; aqui ele entra
como dublê, para que nenhum teste abra rede ou fale com o Telegram.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app import main as modulo_main
from app.calculo.agregacao import Resultado, ResultadoDia, ResultadoMunicipio
from app.classificacao.probabilidades import Probabilidades
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
