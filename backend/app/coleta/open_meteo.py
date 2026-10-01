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

`Membro.rodada` vem de `last_run_initialisation_time` do endpoint de
metadados do modelo (`meta.json`, `ensemble.md` §7) — nunca de uma fórmula
baseada só em `agora_utc`. A resposta do endpoint de previsão não traz o
horário real de inicialização em lugar nenhum (nem no corpo, nem nos
cabeçalhos), e o atraso de disponibilização (até ~8 h, ECMWF) faz com que "a
hora sinótica mais recente <= agora_utc" quase nunca seja a rodada
efetivamente servida (rodada de correção 1 da Tarefa 5).
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
URL_META = "https://api.open-meteo.com/data/{caminho}/static/meta.json"

#: Os três modelos escolhidos na Tarefa 0 (`docs/decisoes/ensemble.md`, §3).
MODELOS = ("gfs_global", "ecmwf_ifs025", "icon_global")

#: Caminho interno de metadados de cada modelo — vocabulário diferente do
#: parâmetro `models=` da API de previsão (`ensemble.md` §7). Confirmado por
#: chamada real: `models=gfs_global`/`icon_global` devolvem 500 em
#: `/data/<id>/static/meta.json`; os caminhos corretos são estes.
MODELO_PARA_CAMINHO_META = {
    "gfs_global": "ncep_gfs013",
    "ecmwf_ifs025": "ecmwf_ifs025",
    "icon_global": "dwd_icon",
}

#: Horários sinóticos em que os três modelos são atualizados (UTC).
HORAS_SINOTICAS = (0, 6, 12, 18)

TIMEOUT_S = 30
TENTATIVAS = 3  # 1 tentativa inicial + 2 novas tentativas

#: Atraso (h) usado para degradar a rodada quando o `meta.json` está
#: indisponível: o gargalo medido entre os três modelos (ECMWF, `ensemble.md`
#: §7). Degradação conservadora de propósito — assumir o atraso do modelo
#: mais lento para um modelo mais rápido (GFS ~5,6 h, ICON ~3,6 h) envelhece
#: a rodada e a subpondera no cálculo de pesos da Tarefa 6, nunca o
#: contrário.
ATRASO_DEGRADACAO_H = 8


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


def _obter_rodada_atual(
    http: requests.Session,
    municipio: Municipio,
    modelo: str,
    agora_utc: datetime,
    espera: Callable[[float], None],
) -> datetime:
    """Rodada atual (horário real de inicialização) do modelo, via `meta.json`.

    O endpoint de previsão (`precipitation`/`precipitation_previous_day1`) não
    traz essa informação em lugar nenhum da resposta — confirmado por
    inspeção da resposta completa e dos cabeçalhos HTTP. O horário vem de
    `last_run_initialisation_time` em
    `https://api.open-meteo.com/data/<caminho>/static/meta.json`
    (`ensemble.md` §7), onde `<caminho>` é o id interno do modelo
    (`MODELO_PARA_CAMINHO_META`), **diferente** do valor usado em `models=`
    na API de previsão.

    Se o `meta.json` estiver indisponível após as tentativas, degrada para o
    horário sinótico mais recente a `ATRASO_DEGRADACAO_H` horas de
    `agora_utc` (ver o comentário na constante).
    """
    caminho = MODELO_PARA_CAMINHO_META[modelo]
    url = URL_META.format(caminho=caminho)
    contexto = f"município '{municipio.ibge}' ({municipio.nome}): metadados do modelo '{modelo}'"
    try:
        dados = _requisitar(http, url, {}, espera, contexto)
    except ColetaError:
        return _piso_sinotico(agora_utc - timedelta(hours=ATRASO_DEGRADACAO_H))
    return datetime.fromtimestamp(dados["last_run_initialisation_time"], tz=timezone.utc)


def _coletar_membros_modelo(
    http: requests.Session,
    municipio: Municipio,
    modelo: str,
    agora_utc: datetime,
    espera: Callable[[float], None],
) -> list[Membro]:
    rodada_atual = _obter_rodada_atual(http, municipio, modelo, agora_utc, espera)
    rodada_anterior = rodada_atual - timedelta(hours=24)

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
        try:
            dados = _requisitar(http, URL_PREVIOUS_RUNS, params, espera, contexto)
        except ColetaError:
            # Falha de transporte esgotada ao buscar um membro descarta só
            # esse membro (as duas rodadas desse modelo) — não o município
            # inteiro. n_min=3 com até 6 membros possíveis tolera a perda de
            # um modelo inteiro; quem decide se o que sobra basta é a
            # Tarefa 6 (ensemble.md §6).
            atual_valido = False
            anterior_valido = False
            break

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
    nela levanta `ColetaError` identificando o município — rede esgotada
    nessa série também aborta a coleta do município (não há como substituir
    observação ausente). Já um membro do ensemble (modelo × rodada) que
    esteja incompleto, cuja rodada não exista na resposta, ou cuja busca
    esgote as tentativas de rede, é descartado silenciosamente — descarta só
    aquele membro, nunca o município inteiro; cabe à Tarefa 6 decidir se os
    membros restantes bastam (`n_min`).
    """
    _validar_agora_utc(agora_utc)

    antecedente = [
        _coletar_antecedente_ponto(http, municipio, ponto, agora_utc, espera)
        for ponto in municipio.pontos
    ]

    membros: list[Membro] = []
    for modelo in MODELOS:
        membros.extend(_coletar_membros_modelo(http, municipio, modelo, agora_utc, espera))

    return DadosMunicipio(ibge=municipio.ibge, antecedente=antecedente, membros=membros)
