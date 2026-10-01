"""Coleta de chuva observada e dos membros do ensemble via Open-Meteo.

Para cada município, busca (1) a chuva horária observada/antecedente das
horas até `agora_utc`, por ponto de cálculo, e (2) para cada um dos três
modelos do ensemble, a chuva horária prevista das duas rodadas alcançáveis
pela API pública ("atual" e a de ~24 h antes, `previous_day1`) — ver
`docs/decisoes/ensemble.md`.

Dependências (cliente HTTP e relógio) entram por parâmetro: esta função não
cria sessão, não lê `os.environ` e não chama `datetime.now()`.

Convenção do rótulo horário: o rótulo `T` da Open-Meteo marca o *fim* da
hora — o valor só é associado ao rótulo correto aqui, sem deslocamento; o
deslocamento semântico das janelas (EfR, Rtotal) é responsabilidade da
camada de cálculo (Tarefa 6).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import requests

from app.config import Municipio, Ponto
from app.modelos.tipos import DadosMunicipio, Membro

URL_FORECAST = "https://api.open-meteo.com/v1/forecast"
URL_PREVIOUS_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"

#: Os três modelos escolhidos na Tarefa 0 (`docs/decisoes/ensemble.md`, §3).
MODELOS = ("gfs_global", "ecmwf_ifs025", "icon_global")

#: Horários sinóticos em que os três modelos são atualizados (UTC).
HORAS_SINOTICAS = (0, 6, 12, 18)

TIMEOUT_S = 30
TENTATIVAS = 3  # 1 tentativa inicial + 2 novas tentativas


class ColetaError(Exception):
    """Falha ao coletar dados de um município: rede esgotada ou lacuna na série antecedente."""


def _validar_agora_utc(agora_utc: datetime) -> None:
    if agora_utc.tzinfo is None:
        raise ValueError(
            "'agora_utc' precisa ser um datetime com fuso (aware); recebido sem fuso"
        )


def _piso_sinotico(momento: datetime) -> datetime:
    """Arredonda `momento` para baixo até o horário sinótico mais recente (0, 6, 12 ou 18 UTC)."""
    hora_sinotica = max(h for h in HORAS_SINOTICAS if h <= momento.hour)
    return momento.replace(hour=hora_sinotica, minute=0, second=0, microsecond=0)


def _hora_utc(rotulo: str) -> datetime:
    """Converte um rótulo `timezone=UTC` da Open-Meteo (sem offset) em `datetime` aware UTC."""
    return datetime.fromisoformat(rotulo).replace(tzinfo=timezone.utc)


def _montar_serie(tempos: list[str], valores: list[float | None]) -> dict[datetime, float | None]:
    return {_hora_utc(tempo): valor for tempo, valor in zip(tempos, valores)}


def _requisitar(
    http: requests.Session,
    url: str,
    params: dict,
    espera: Callable[[float], None],
    contexto: str,
) -> dict:
    """Faz GET com até `TENTATIVAS` tentativas, espera injetável entre elas.

    Levanta `ColetaError` identificando `contexto` se todas as tentativas
    falharem.
    """
    ultimo_erro: Exception | None = None
    for tentativa in range(TENTATIVAS):
        try:
            resposta = http.get(url, params=params, timeout=TIMEOUT_S)
            resposta.raise_for_status()
            return resposta.json()
        except requests.exceptions.RequestException as erro:
            ultimo_erro = erro
            if tentativa < TENTATIVAS - 1:
                espera(1.0)
    raise ColetaError(
        f"{contexto}: falha ao chamar {url} após {TENTATIVAS} tentativas: {ultimo_erro}"
    ) from ultimo_erro


def _coletar_antecedente_ponto(
    http: requests.Session,
    municipio: Municipio,
    ponto: Ponto,
    agora_utc: datetime,
    espera: Callable[[float], None],
) -> dict[datetime, float]:
    params = {
        "latitude": ponto.lat,
        "longitude": ponto.lon,
        "hourly": "precipitation",
        "timezone": "UTC",
        "past_days": 7,
        "forecast_days": 1,
    }
    contexto = f"município '{municipio.ibge}' ({municipio.nome}): chuva antecedente"
    dados = _requisitar(http, URL_FORECAST, params, espera, contexto)

    hourly = dados["hourly"]
    serie_bruta = _montar_serie(hourly["time"], hourly["precipitation"])
    serie = {hora: valor for hora, valor in serie_bruta.items() if hora <= agora_utc}

    for hora, valor in serie.items():
        if valor is None:
            raise ColetaError(
                f"município '{municipio.ibge}' ({municipio.nome}): lacuna (valor ausente) "
                f"na série antecedente na hora {hora.isoformat()}"
            )

    return serie


def _coletar_membros_modelo(
    http: requests.Session,
    municipio: Municipio,
    modelo: str,
    rodada_atual: datetime,
    rodada_anterior: datetime,
    espera: Callable[[float], None],
) -> list[Membro]:
    series_atual: list[dict[datetime, float]] = []
    series_anterior: list[dict[datetime, float]] = []
    atual_valido = True
    anterior_valido = True

    for ponto in municipio.pontos:
        params = {
            "latitude": ponto.lat,
            "longitude": ponto.lon,
            "hourly": "precipitation,precipitation_previous_day1",
            "models": modelo,
            "timezone": "UTC",
            "forecast_days": 4,
        }
        contexto = f"município '{municipio.ibge}' ({municipio.nome}): ensemble modelo '{modelo}'"
        dados = _requisitar(http, URL_PREVIOUS_RUNS, params, espera, contexto)

        hourly = dados.get("hourly", {})
        tempos = hourly.get("time", [])

        if "precipitation" in hourly:
            serie = _montar_serie(tempos, hourly["precipitation"])
            if any(valor is None for valor in serie.values()):
                atual_valido = False
            elif atual_valido:
                series_atual.append(serie)
        else:
            atual_valido = False

        if "precipitation_previous_day1" in hourly:
            serie = _montar_serie(tempos, hourly["precipitation_previous_day1"])
            if any(valor is None for valor in serie.values()):
                anterior_valido = False
            elif anterior_valido:
                series_anterior.append(serie)
        else:
            anterior_valido = False

    membros: list[Membro] = []
    if atual_valido:
        membros.append(Membro(modelo=modelo, rodada=rodada_atual, chuva=series_atual))
    if anterior_valido:
        membros.append(Membro(modelo=modelo, rodada=rodada_anterior, chuva=series_anterior))
    return membros


def coletar(
    municipio: Municipio,
    agora_utc: datetime,
    http: requests.Session,
    espera: Callable[[float], None] = time.sleep,
) -> DadosMunicipio:
    """Coleta a chuva antecedente e os membros do ensemble para um município.

    `antecedente` é a série horária (uma por ponto) até `agora_utc`; lacuna
    nela levanta `ColetaError` identificando o município. Cada membro do
    ensemble (modelo × rodada) que estiver incompleto ou cuja rodada não
    exista na resposta é descartado silenciosamente — cabe à Tarefa 6 decidir
    se os membros restantes são suficientes.
    """
    _validar_agora_utc(agora_utc)

    antecedente = [
        _coletar_antecedente_ponto(http, municipio, ponto, agora_utc, espera)
        for ponto in municipio.pontos
    ]

    rodada_atual = _piso_sinotico(agora_utc)
    rodada_anterior = rodada_atual - timedelta(hours=24)

    membros: list[Membro] = []
    for modelo in MODELOS:
        membros.extend(
            _coletar_membros_modelo(http, municipio, modelo, rodada_atual, rodada_anterior, espera)
        )

    return DadosMunicipio(ibge=municipio.ibge, antecedente=antecedente, membros=membros)
