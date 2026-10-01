"""Testes da coleta de chuva observada e dos membros do ensemble (Open-Meteo).

Os testes da suíte padrão usam fixtures de respostas reais e um cliente HTTP
falso — nenhum acessa a rede. O único teste que acessa a rede de verdade está
marcado `@pytest.mark.rede` e fica fora da suíte padrão.
"""

from __future__ import annotations

import copy
import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from app.config import Municipio, Ponto
from app.coleta.open_meteo import URL_FORECAST, URL_PREVIOUS_RUNS, ColetaError, coletar
from app.modelos.tipos import DadosMunicipio, Membro

RAIZ_FIXTURES = Path(__file__).resolve().parent / "fixtures"

AGORA_UTC = datetime(2026, 10, 1, 21, 0, tzinfo=timezone.utc)
RODADA_ATUAL_ESPERADA = datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc)
RODADA_ANTERIOR_ESPERADA = datetime(2026, 9, 30, 18, 0, tzinfo=timezone.utc)

MODELOS = ("gfs_global", "ecmwf_ifs025", "icon_global")


def _carregar_fixture(nome: str) -> dict:
    return json.loads((RAIZ_FIXTURES / nome).read_text(encoding="utf-8"))


def _municipio(pontos):
    return Municipio(
        ibge="4206900",
        nome="Ibirama",
        limiar_mm=250,
        fonte_limiar="teste",
        mv_h=24,
        pontos=tuple(pontos),
    )


class RespostaFalsa:
    """Dublê de `requests.Response`: só o necessário para o coletor."""

    def __init__(self, corpo: dict, status_code: int = 200):
        self._corpo = corpo
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"status {self.status_code}")

    def json(self) -> dict:
        return self._corpo


class HttpFalso:
    """Roteia por (url, modelo) uma fila de respostas/exceções programadas."""

    def __init__(self):
        self.chamadas: list[tuple[str, dict]] = []
        self._filas: dict[tuple[str, str | None], list] = {}

    def programar(self, url: str, modelo: str | None, *itens) -> None:
        self._filas[(url, modelo)] = list(itens)

    def get(self, url: str, params: dict | None = None, timeout: float | None = None):
        params = params or {}
        self.chamadas.append((url, dict(params)))
        chave = (url, params.get("models"))
        fila = self._filas.get(chave)
        if not fila:
            raise AssertionError(f"chamada inesperada (sem item programado): {chave}")
        item = fila.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class HttpComFalhasIniciais:
    """Decora outro cliente HTTP falso, fazendo as N primeiras chamadas falharem."""

    def __init__(self, http_interno, n_falhas: int):
        self._http = http_interno
        self._n_falhas = n_falhas
        self.chamadas = 0

    def get(self, *args, **kwargs):
        self.chamadas += 1
        if self.chamadas <= self._n_falhas:
            raise requests.exceptions.ConnectionError("falha de rede simulada")
        return self._http.get(*args, **kwargs)


def _http_completo_programado(municipio: Municipio) -> HttpFalso:
    """Monta um HttpFalso que atende a todas as chamadas de `coletar` com sucesso."""
    antecedente = _carregar_fixture("open_meteo_antecedente.json")
    previous_runs = _carregar_fixture("open_meteo_previous_runs.json")

    http = HttpFalso()
    http.programar(
        URL_FORECAST,
        None,
        *(RespostaFalsa(copy.deepcopy(antecedente)) for _ in municipio.pontos),
    )
    for modelo in MODELOS:
        http.programar(
            URL_PREVIOUS_RUNS,
            modelo,
            *(RespostaFalsa(copy.deepcopy(previous_runs)) for _ in municipio.pontos),
        )
    return http


def _espera_registrada():
    chamadas: list[float] = []

    def espera(segundos: float) -> None:
        chamadas.append(segundos)

    return espera, chamadas


# --- tipos: dataclasses imutáveis -------------------------------------------


def test_membro_e_imutavel():
    membro = Membro(modelo="gfs_global", rodada=RODADA_ATUAL_ESPERADA, chuva=[{}])
    with pytest.raises(FrozenInstanceError):
        membro.modelo = "outro"


def test_dados_municipio_e_imutavel():
    dados = DadosMunicipio(ibge="4206900", antecedente=[{}], membros=[])
    with pytest.raises(FrozenInstanceError):
        dados.ibge = "0000000"


# --- conversão de horas e valores --------------------------------------------


def test_antecedente_tem_horas_utc_com_fuso_e_valor_associado_a_hora_certa():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    http = _http_completo_programado(municipio)

    dados = coletar(municipio, AGORA_UTC, http)

    assert isinstance(dados, DadosMunicipio)
    serie = dados.antecedente[0]

    hora_verificada = datetime(2026, 10, 1, 21, 0, tzinfo=timezone.utc)
    assert hora_verificada in serie
    assert serie[hora_verificada] == pytest.approx(0.5)
    assert hora_verificada.tzinfo is not None

    # nenhuma hora depois de agora_utc deve aparecer na série antecedente
    assert all(hora <= AGORA_UTC for hora in serie)
    assert datetime(2026, 10, 1, 22, 0, tzinfo=timezone.utc) not in serie


def test_membros_tem_horas_utc_com_fuso_valor_certo_e_rodada_correta():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    http = _http_completo_programado(municipio)

    dados = coletar(municipio, AGORA_UTC, http)

    assert len(dados.membros) == 6  # 3 modelos x 2 rodadas (atual + anterior)

    membro_gfs_atual = next(
        m for m in dados.membros if m.modelo == "gfs_global" and m.rodada == RODADA_ATUAL_ESPERADA
    )
    membro_gfs_anterior = next(
        m for m in dados.membros if m.modelo == "gfs_global" and m.rodada == RODADA_ANTERIOR_ESPERADA
    )

    hora = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    assert membro_gfs_atual.chuva[0][hora] == pytest.approx(0.7)
    assert membro_gfs_anterior.chuva[0][hora] == pytest.approx(0.2)
    assert hora.tzinfo is not None
    assert membro_gfs_atual.rodada.tzinfo is not None


def test_series_por_ponto_seguem_a_mesma_ordem_dos_pontos_da_configuracao():
    municipio = _municipio(
        [Ponto(lat=-27.0181, lon=-49.5286), Ponto(lat=-26.90, lon=-49.60)]
    )
    http = _http_completo_programado(municipio)

    dados = coletar(municipio, AGORA_UTC, http)

    assert len(dados.antecedente) == 2
    membro_gfs_atual = next(
        m for m in dados.membros if m.modelo == "gfs_global" and m.rodada == RODADA_ATUAL_ESPERADA
    )
    assert len(membro_gfs_atual.chuva) == 2


# --- lacuna na série antecedente ---------------------------------------------


def test_lacuna_na_serie_antecedente_levanta_erro_identificando_municipio():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    antecedente_com_lacuna = _carregar_fixture("open_meteo_antecedente.json")
    indice_10h_01out = antecedente_com_lacuna["hourly"]["time"].index("2026-10-01T10:00")
    antecedente_com_lacuna["hourly"]["precipitation"][indice_10h_01out] = None

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaFalsa(antecedente_com_lacuna))

    with pytest.raises(ColetaError, match="4206900"):
        coletar(municipio, AGORA_UTC, http)


# --- lacuna ou rodada ausente num membro: descarta só esse membro -----------


def test_lacuna_num_membro_descarta_so_esse_membro():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    previous_runs_com_lacuna = _carregar_fixture("open_meteo_previous_runs.json")
    indice_5h = previous_runs_com_lacuna["hourly"]["time"].index("2026-10-01T05:00")
    previous_runs_com_lacuna["hourly"]["precipitation"][indice_5h] = None

    antecedente = _carregar_fixture("open_meteo_antecedente.json")
    previous_runs_ok = _carregar_fixture("open_meteo_previous_runs.json")

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaFalsa(antecedente))
    http.programar(URL_PREVIOUS_RUNS, "gfs_global", RespostaFalsa(previous_runs_ok))
    http.programar(URL_PREVIOUS_RUNS, "ecmwf_ifs025", RespostaFalsa(copy.deepcopy(previous_runs_ok)))
    # icon_global: rodada atual com lacuna -> descartada; rodada anterior intacta -> mantida
    http.programar(URL_PREVIOUS_RUNS, "icon_global", RespostaFalsa(previous_runs_com_lacuna))

    dados = coletar(municipio, AGORA_UTC, http)

    assert len(dados.membros) == 5  # 6 - 1 (icon_global atual, descartado)
    assert not any(
        m.modelo == "icon_global" and m.rodada == RODADA_ATUAL_ESPERADA for m in dados.membros
    )
    assert any(
        m.modelo == "icon_global" and m.rodada == RODADA_ANTERIOR_ESPERADA for m in dados.membros
    )


def test_rodada_ausente_num_membro_descarta_so_esse_membro():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    previous_runs_sem_rodada_anterior = _carregar_fixture("open_meteo_previous_runs.json")
    del previous_runs_sem_rodada_anterior["hourly"]["precipitation_previous_day1"]

    antecedente = _carregar_fixture("open_meteo_antecedente.json")
    previous_runs_ok = _carregar_fixture("open_meteo_previous_runs.json")

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaFalsa(antecedente))
    http.programar(URL_PREVIOUS_RUNS, "gfs_global", RespostaFalsa(previous_runs_ok))
    # ecmwf_ifs025: rodada anterior ausente no payload -> descartada; rodada atual mantida
    http.programar(URL_PREVIOUS_RUNS, "ecmwf_ifs025", RespostaFalsa(previous_runs_sem_rodada_anterior))
    http.programar(URL_PREVIOUS_RUNS, "icon_global", RespostaFalsa(copy.deepcopy(previous_runs_ok)))

    dados = coletar(municipio, AGORA_UTC, http)

    assert len(dados.membros) == 5  # 6 - 1 (ecmwf_ifs025 anterior, descartado)
    assert not any(
        m.modelo == "ecmwf_ifs025" and m.rodada == RODADA_ANTERIOR_ESPERADA for m in dados.membros
    )
    assert any(
        m.modelo == "ecmwf_ifs025" and m.rodada == RODADA_ATUAL_ESPERADA for m in dados.membros
    )


# --- retentativas -------------------------------------------------------------


def test_erro_transitorio_na_primeira_tentativa_sucesso_na_segunda_devolve_dados():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    http_interno = _http_completo_programado(municipio)
    http = HttpComFalhasIniciais(http_interno, n_falhas=1)
    espera, chamadas_espera = _espera_registrada()

    dados = coletar(municipio, AGORA_UTC, http, espera=espera)

    hora = datetime(2026, 10, 1, 21, 0, tzinfo=timezone.utc)
    assert dados.antecedente[0][hora] == pytest.approx(0.5)
    assert len(dados.membros) == 6
    assert len(chamadas_espera) == 1  # uma pausa entre a 1ª tentativa (falha) e a 2ª (sucesso)


def test_tres_falhas_levanta_erro_identificando_municipio():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])

    class HttpSempreFalha:
        def __init__(self):
            self.chamadas = 0

        def get(self, *args, **kwargs):
            self.chamadas += 1
            raise requests.exceptions.ConnectionError("falha de rede simulada")

    http = HttpSempreFalha()
    espera, chamadas_espera = _espera_registrada()

    with pytest.raises(ColetaError, match="4206900"):
        coletar(municipio, AGORA_UTC, http, espera=espera)

    assert http.chamadas == 3  # 1 tentativa inicial + 2 novas tentativas
    assert len(chamadas_espera) == 2  # pausa entre tentativa 1-2 e entre 2-3


# --- fuso horário --------------------------------------------------------------


def test_agora_utc_sem_fuso_levanta_erro_sem_chamar_rede():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])

    class HttpNuncaDeveriaSerChamado:
        def get(self, *args, **kwargs):
            raise AssertionError("não deveria chamar a rede com agora_utc inválido")

    agora_sem_fuso = datetime(2026, 10, 1, 21, 0)  # naive, sem tzinfo

    with pytest.raises(ValueError):
        coletar(municipio, agora_sem_fuso, HttpNuncaDeveriaSerChamado())


# --- integração real (fora da suíte padrão) ------------------------------------


@pytest.mark.rede
def test_coleta_real_para_um_ponto():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    agora_utc = datetime.now(timezone.utc)

    dados = coletar(municipio, agora_utc, requests.Session())

    assert isinstance(dados, DadosMunicipio)
    assert len(dados.antecedente) == 1
    assert len(dados.antecedente[0]) > 0
    for hora in dados.antecedente[0]:
        assert hora.tzinfo is not None
    assert len(dados.membros) >= 1
    for membro in dados.membros:
        assert membro.rodada.tzinfo is not None
        assert len(membro.chuva) == 1
