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
from app.coleta.open_meteo import (
    MODELO_PARA_CAMINHO_META,
    URL_FORECAST,
    URL_META,
    URL_PREVIOUS_RUNS,
    ColetaError,
    coletar,
)
from app.modelos.tipos import DadosMunicipio, Membro

RAIZ_FIXTURES = Path(__file__).resolve().parent / "fixtures"

AGORA_UTC = datetime(2026, 10, 1, 21, 0, tzinfo=timezone.utc)

# Rodada "forçada" nos testes de uso geral: o `meta.json` programado para
# todos os modelos tem `last_run_initialisation_time` ajustado para este
# instante, independente do conteúdo bruto da fixture (que reflete a rodada
# real no momento em que foi gravada). Mantém os testes determinísticos.
RODADA_ATUAL_ESPERADA = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
RODADA_ANTERIOR_ESPERADA = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)

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


def _url_meta(modelo: str) -> str:
    return URL_META.format(caminho=MODELO_PARA_CAMINHO_META[modelo])


def _meta_com_rodada(rodada: datetime) -> dict:
    meta = _carregar_fixture("open_meteo_meta.json")
    meta["last_run_initialisation_time"] = int(rodada.timestamp())
    return meta


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
    """Roteia por (url, modelo, lat, lon) uma fila de respostas/exceções programadas.

    Rotear por ponto (não só por url/modelo) importa para provar que a
    coleta associa a série certa ao ponto certo, na ordem certa — ver
    `test_series_por_ponto_seguem_a_mesma_ordem_dos_pontos_da_configuracao`.
    Quando o teste não precisa distinguir pontos (a maioria), `programar` é
    chamado sem `lat`/`lon` (ficam `None`), e `get` cai de volta para essa
    chave "sem ponto" — cobre também `meta.json`, que não tem lat/lon.

    Um item programado pode ser: uma exceção (é levantada), uma
    `RespostaFalsa` (é devolvida como está) ou uma função `params -> objeto
    com .json()/.raise_for_status()` (chamada com os parâmetros reais da
    requisição) — usado para simular, por exemplo, o truncamento real que a
    API faria conforme o `forecast_days` enviado.
    """

    def __init__(self):
        self.chamadas: list[tuple[str, dict]] = []
        self._filas: dict[tuple[str, str | None, float | None, float | None], list] = {}

    def programar(
        self,
        url: str,
        modelo: str | None,
        *itens,
        lat: float | None = None,
        lon: float | None = None,
    ) -> None:
        self._filas[(url, modelo, lat, lon)] = list(itens)

    def get(self, url: str, params: dict | None = None, timeout: float | None = None):
        params = params or {}
        self.chamadas.append((url, dict(params)))
        chave = (url, params.get("models"), params.get("latitude"), params.get("longitude"))
        fila = self._filas.get(chave)
        if fila is None:
            chave = (url, params.get("models"), None, None)
            fila = self._filas.get(chave)
        if not fila:
            raise AssertionError(f"chamada inesperada (sem item programado): {chave}")
        item = fila.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(params)
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


def _programar_meta_para_todos_os_modelos(http: HttpFalso, rodada: datetime = RODADA_ATUAL_ESPERADA) -> None:
    for modelo in MODELOS:
        http.programar(_url_meta(modelo), None, RespostaFalsa(_meta_com_rodada(rodada)))


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
    _programar_meta_para_todos_os_modelos(http)
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


def _deslocar_precipitacao(fixture: dict, campos: list[str], deslocamento: float) -> dict:
    """Copia a fixture somando `deslocamento` a cada valor não nulo dos
    `campos` indicados — usado para dar a cada ponto um valor numericamente
    distinto e provável de detectar inversão de ordem."""
    copia = copy.deepcopy(fixture)
    for campo in campos:
        copia["hourly"][campo] = [
            (valor + deslocamento) if valor is not None else None
            for valor in copia["hourly"][campo]
        ]
    return copia


def _resposta_previous_runs_truncada_pelo_forecast_days(fixture_completa: dict):
    """Responder dinâmico: trunca a fixture completa (120 rótulos, gravada
    com `forecast_days=5`) para `forecast_days * 24` rótulos, simulando o que
    a API realmente devolveria para o valor de `forecast_days` que a
    implementação de fato enviar. Detecta a regressão de verdade — não
    confere o parâmetro enviado, confere a consequência de enviá-lo."""

    def responder(params: dict):
        dias = params.get("forecast_days", 4)
        n_horas = dias * 24
        truncada = copy.deepcopy(fixture_completa)
        for campo in ("time", "precipitation", "precipitation_previous_day1"):
            truncada["hourly"][campo] = truncada["hourly"][campo][:n_horas]
        return RespostaFalsa(truncada)

    return responder


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
    """Não basta len(...) == 2 (cardinalidade): a Tarefa 6 usa "primeiro
    ponto da configuração" como critério de desempate, então a *identidade*
    de qual série pertence a qual ponto importa. Cada ponto recebe aqui um
    deslocamento numérico distinto (+0 mm e +10 mm) para que a asserção
    dependa de qual ponto gerou qual série — um teste que só conferisse o
    tamanho das listas passaria mesmo com a ordem invertida."""
    pontos = (Ponto(lat=-27.0181, lon=-49.5286), Ponto(lat=-26.90, lon=-49.60))
    municipio = _municipio(pontos)

    antecedente_base = _carregar_fixture("open_meteo_antecedente.json")
    previous_runs_base = _carregar_fixture("open_meteo_previous_runs.json")

    http = HttpFalso()
    for indice, ponto in enumerate(pontos):
        deslocamento = 10.0 * indice  # ponto 0: +0 mm; ponto 1: +10 mm
        http.programar(
            URL_FORECAST,
            None,
            RespostaFalsa(_deslocar_precipitacao(antecedente_base, ["precipitation"], deslocamento)),
            lat=ponto.lat,
            lon=ponto.lon,
        )
    _programar_meta_para_todos_os_modelos(http)
    for modelo in MODELOS:
        for indice, ponto in enumerate(pontos):
            deslocamento = 10.0 * indice
            http.programar(
                URL_PREVIOUS_RUNS,
                modelo,
                RespostaFalsa(
                    _deslocar_precipitacao(
                        previous_runs_base, ["precipitation", "precipitation_previous_day1"], deslocamento
                    )
                ),
                lat=ponto.lat,
                lon=ponto.lon,
            )

    dados = coletar(municipio, AGORA_UTC, http)

    hora_antecedente = datetime(2026, 10, 1, 21, 0, tzinfo=timezone.utc)
    indice_hora_antecedente = antecedente_base["hourly"]["time"].index("2026-10-01T21:00")
    valor_base_antecedente = antecedente_base["hourly"]["precipitation"][indice_hora_antecedente]

    assert len(dados.antecedente) == 2
    assert dados.antecedente[0][hora_antecedente] == pytest.approx(valor_base_antecedente)
    assert dados.antecedente[1][hora_antecedente] == pytest.approx(valor_base_antecedente + 10.0)

    hora_membro = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    indice_hora_membro = previous_runs_base["hourly"]["time"].index("2026-10-01T00:00")
    valor_base_membro = previous_runs_base["hourly"]["precipitation"][indice_hora_membro]

    membro_gfs_atual = next(
        m for m in dados.membros if m.modelo == "gfs_global" and m.rodada == RODADA_ATUAL_ESPERADA
    )
    assert len(membro_gfs_atual.chuva) == 2
    assert membro_gfs_atual.chuva[0][hora_membro] == pytest.approx(valor_base_membro)
    assert membro_gfs_atual.chuva[1][hora_membro] == pytest.approx(valor_base_membro + 10.0)


# --- rtotal de D3: o rótulo que fecha a janela não pode faltar --------------
#
# Rodada de correção 2. A janela do Rtotal de um dia-alvo D são os 24
# rótulos D T01:00Z .. (D+1)T00:00Z — termina na meia-noite do dia seguinte,
# porque o rótulo marca o fim do intervalo (ensemble.md §2). Para D3
# (= D0+3), isso exige o rótulo (D3+1)T00:00Z = (D0+4)T00:00Z. Com
# forecast_days=4 a API para em D3 T23:00 — falta exatamente esse rótulo, e
# o Rtotal de D3 nunca fecharia (todos os dias-alvo do município cairiam
# abaixo de n_min, mandando o município inteiro para municipios_sem_dados
# em toda execução).


def test_membro_contem_o_ultimo_rotulo_que_o_rtotal_de_d3_precisa():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    # fixture gravada com forecast_days=5 (120 rótulos, D0 T00:00 .. (D0+4)T23:00)
    previous_runs_completa = _carregar_fixture("open_meteo_previous_runs.json")
    antecedente = _carregar_fixture("open_meteo_antecedente.json")

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaFalsa(antecedente))
    _programar_meta_para_todos_os_modelos(http)
    for modelo in MODELOS:
        http.programar(
            URL_PREVIOUS_RUNS,
            modelo,
            _resposta_previous_runs_truncada_pelo_forecast_days(previous_runs_completa),
        )

    dados = coletar(municipio, AGORA_UTC, http)

    rotulo_que_fecha_rtotal_de_d3 = datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc)  # (D0+4)T00:00Z
    membro_gfs_atual = next(
        m for m in dados.membros if m.modelo == "gfs_global" and m.rodada == RODADA_ATUAL_ESPERADA
    )
    assert rotulo_que_fecha_rtotal_de_d3 in membro_gfs_atual.chuva[0]


# --- rodada: vem do meta.json, não de agora_utc -----------------------------
#
# Rodada de correção 1. A versão anterior calculava `rodada` como a maior
# hora sinótica <= agora_utc, uma fórmula pura de agora_utc. Isso está errado
# porque o atraso de disponibilização (até ~8h, ECMWF — ensemble.md §7) faz
# com que, em boa parte do tempo, a rodada sinótica "mais recente <= agora"
# ainda não esteja disponível: a rodada de fato servida pela API é uma mais
# antiga. O teste abaixo reproduz exatamente o cenário do cron da Tarefa 11
# (chamada às 03:00 UTC, rodada real disponível é a de 18 UTC do dia
# anterior) e teria falhado com a fórmula antiga, que devolveria 00:00 UTC do
# dia corrente — 6h adiantada e com atraso computado como 3h em vez de 9h.


def test_rodada_vem_do_last_run_initialisation_time_do_meta_json():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    agora_utc = datetime(2026, 10, 2, 3, 0, tzinfo=timezone.utc)
    rodada_real_disponivel = datetime(2026, 10, 1, 18, 0, tzinfo=timezone.utc)
    rodada_que_a_formula_antiga_produziria = datetime(2026, 10, 2, 0, 0, tzinfo=timezone.utc)

    antecedente = _carregar_fixture("open_meteo_antecedente.json")
    previous_runs = _carregar_fixture("open_meteo_previous_runs.json")

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaFalsa(antecedente))
    for modelo in MODELOS:
        http.programar(
            _url_meta(modelo), None, RespostaFalsa(_meta_com_rodada(rodada_real_disponivel))
        )
        http.programar(URL_PREVIOUS_RUNS, modelo, RespostaFalsa(copy.deepcopy(previous_runs)))

    dados = coletar(municipio, agora_utc, http)

    for modelo in MODELOS:
        membro_atual = next(
            m for m in dados.membros if m.modelo == modelo and m.rodada == rodada_real_disponivel
        )
        assert membro_atual.rodada == rodada_real_disponivel

    assert not any(
        m.rodada == rodada_que_a_formula_antiga_produziria for m in dados.membros
    )


def test_rodada_anterior_e_24h_antes_da_rodada_atual_do_meta_json():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    rodada_real = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)

    antecedente = _carregar_fixture("open_meteo_antecedente.json")

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaFalsa(antecedente))
    _programar_meta_para_todos_os_modelos(http, rodada=rodada_real)
    for modelo in MODELOS:
        http.programar(
            URL_PREVIOUS_RUNS, modelo, RespostaFalsa(_carregar_fixture("open_meteo_previous_runs.json"))
        )

    dados = coletar(municipio, AGORA_UTC, http)

    membro_anterior = next(
        m for m in dados.membros
        if m.modelo == "gfs_global" and m.rodada == rodada_real - timedelta(hours=24)
    )
    assert membro_anterior.rodada == datetime(2026, 9, 30, 6, 0, tzinfo=timezone.utc)


def test_meta_json_indisponivel_degrada_para_piso_sinotico_menos_8h():
    """Se o `meta.json` falhar após as tentativas, a rodada cai para a
    derivação documentada em `ensemble.md` §7 (gargalo do ECMWF, ~8h de
    atraso de disponibilização) — nunca para uma fórmula baseada só em
    `agora_utc` sem margem nenhuma (o erro da rodada de correção 1)."""
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    agora_utc = datetime(2026, 10, 1, 21, 0, tzinfo=timezone.utc)
    # piso_sinotico(21:00 - 8h) = piso_sinotico(13:00) = 12:00 UTC
    rodada_degradada_esperada = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    antecedente = _carregar_fixture("open_meteo_antecedente.json")
    previous_runs = _carregar_fixture("open_meteo_previous_runs.json")

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaFalsa(antecedente))
    http.programar(
        _url_meta("gfs_global"),
        None,
        requests.exceptions.ConnectionError("falha simulada"),
        requests.exceptions.ConnectionError("falha simulada"),
        requests.exceptions.ConnectionError("falha simulada"),
    )
    http.programar(URL_PREVIOUS_RUNS, "gfs_global", RespostaFalsa(previous_runs))
    for modelo in ("ecmwf_ifs025", "icon_global"):
        http.programar(_url_meta(modelo), None, RespostaFalsa(_meta_com_rodada(RODADA_ATUAL_ESPERADA)))
        http.programar(URL_PREVIOUS_RUNS, modelo, RespostaFalsa(_carregar_fixture("open_meteo_previous_runs.json")))

    espera, chamadas_espera = _espera_registrada()
    dados = coletar(municipio, agora_utc, http, espera=espera)

    membro_gfs_atual = next(
        m for m in dados.membros if m.modelo == "gfs_global" and m.rodada == rodada_degradada_esperada
    )
    assert membro_gfs_atual.rodada == rodada_degradada_esperada
    assert len(chamadas_espera) >= 2  # as 2 pausas entre as 3 tentativas do meta.json


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
    _programar_meta_para_todos_os_modelos(http)
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
    _programar_meta_para_todos_os_modelos(http)
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


# --- falha de transporte ao buscar um membro: descarta só esse membro -------
#
# Rodada de correção 1, decisão 2. n_min = 3 e há até 6 membros possíveis (3
# modelos x 2 rodadas); perder a rede de um modelo inteiro ainda deixa 4
# membros, de sobra — abortar o município inteiro jogaria fora um resultado
# utilizável. Só a série antecedente, que não admite lacuna nenhuma, aborta o
# município quando a rede se esgota.


def test_falha_de_transporte_ao_buscar_membro_descarta_so_aquele_modelo():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])

    antecedente = _carregar_fixture("open_meteo_antecedente.json")
    previous_runs = _carregar_fixture("open_meteo_previous_runs.json")

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaFalsa(antecedente))
    _programar_meta_para_todos_os_modelos(http)
    http.programar(
        URL_PREVIOUS_RUNS,
        "icon_global",
        requests.exceptions.ConnectionError("falha simulada"),
        requests.exceptions.ConnectionError("falha simulada"),
        requests.exceptions.ConnectionError("falha simulada"),
    )
    http.programar(URL_PREVIOUS_RUNS, "gfs_global", RespostaFalsa(previous_runs))
    http.programar(URL_PREVIOUS_RUNS, "ecmwf_ifs025", RespostaFalsa(copy.deepcopy(previous_runs)))

    espera, _ = _espera_registrada()
    dados = coletar(municipio, AGORA_UTC, http, espera=espera)

    assert len(dados.membros) == 4  # 2 modelos restantes x 2 rodadas
    assert not any(m.modelo == "icon_global" for m in dados.membros)
    assert any(m.modelo == "gfs_global" and m.rodada == RODADA_ATUAL_ESPERADA for m in dados.membros)
    assert any(m.modelo == "ecmwf_ifs025" and m.rodada == RODADA_ATUAL_ESPERADA for m in dados.membros)


# --- retentativas (série antecedente) ------------------------------------------


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


def test_tres_falhas_na_antecedente_levanta_erro_identificando_municipio():
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
        assert membro.rodada.hour in (0, 6, 12, 18)
        assert len(membro.chuva) == 1


# --- cache da rodada entre municípios (decisão da Tarefa 11) ------------------


def test_cache_de_rodadas_evita_repetir_o_meta_json_por_municipio():
    # Sem cache, `meta.json` é chamado 3 vezes por município (18 por execução
    # com os seis municípios). Com um cache compartilhado pela execução, cada
    # modelo é consultado uma vez só — o volume de chamadas da API é limite
    # real do plano gratuito.
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    cache: dict[str, datetime] = {}
    espera, _ = _espera_registrada()

    for _ in range(3):
        http = _http_completo_programado(municipio)
        coletar(municipio, AGORA_UTC, http, espera, cache_rodadas=cache)
        chamadas_meta = [
            url for url, _ in http.chamadas if url.startswith("https://api.open-meteo.com/data/")
        ]
        if len(cache) == len(MODELOS):
            ultimas_chamadas_meta = chamadas_meta

    # Na terceira coleta, o cache já está completo: nenhuma chamada a meta.json.
    assert ultimas_chamadas_meta == []
    assert set(cache) == set(MODELOS)


def test_sem_cache_a_rodada_e_consultada_a_cada_coleta():
    # O parâmetro é opcional: sem ele o comportamento é o anterior, para que
    # uma coleta isolada (ou um teste) não dependa de estado compartilhado.
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    espera, _ = _espera_registrada()
    http = _http_completo_programado(municipio)

    coletar(municipio, AGORA_UTC, http, espera)

    chamadas_meta = [
        url for url, _ in http.chamadas if url.startswith("https://api.open-meteo.com/data/")
    ]
    assert len(chamadas_meta) == len(MODELOS)


def test_rodada_do_cache_e_usada_nos_membros():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    rodada_no_cache = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)
    cache = {modelo: rodada_no_cache for modelo in MODELOS}
    espera, _ = _espera_registrada()
    http = _http_completo_programado(municipio)

    dados = coletar(municipio, AGORA_UTC, http, espera, cache_rodadas=cache)

    rodadas_atuais = {
        membro.rodada for membro in dados.membros if membro.rodada == rodada_no_cache
    }
    assert rodadas_atuais == {rodada_no_cache}


# --- corpo malformado ---------------------------------------------------------


def test_json_invalido_na_antecedente_levanta_coleta_error_identificando_municipio():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    espera, _ = _espera_registrada()

    class RespostaComJsonInvalido:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            raise json.JSONDecodeError("corpo truncado", "", 0)

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaComJsonInvalido())

    with pytest.raises(ColetaError, match="4206900"):
        coletar(municipio, AGORA_UTC, http, espera)


def test_resposta_200_sem_a_chave_hourly_levanta_coleta_error_identificando_municipio():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    espera, _ = _espera_registrada()

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaFalsa({"latitude": -27.0}))

    with pytest.raises(ColetaError, match="4206900"):
        coletar(municipio, AGORA_UTC, http, espera)


def test_antecedente_sem_a_chave_precipitation_levanta_coleta_error():
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    espera, _ = _espera_registrada()

    http = HttpFalso()
    http.programar(URL_FORECAST, None, RespostaFalsa({"hourly": {"time": []}}))

    with pytest.raises(ColetaError, match="4206900"):
        coletar(municipio, AGORA_UTC, http, espera)


def test_meta_json_com_corpo_malformado_degrada_em_vez_de_quebrar():
    # O `meta.json` tem caminho de degradação documentado; corpo inesperado
    # segue o mesmo caminho do erro de rede, em vez de abortar o município.
    municipio = _municipio([Ponto(lat=-27.0181, lon=-49.5286)])
    espera, _ = _espera_registrada()
    http = _http_completo_programado(municipio)
    for modelo in MODELOS:
        http._filas[(_url_meta(modelo), None, None, None)] = [RespostaFalsa({})]

    dados = coletar(municipio, AGORA_UTC, http, espera)

    # Degradação: piso sinótico de agora_utc - 8 h = 2026-10-01T21:00Z - 8 h.
    assert {membro.rodada for membro in dados.membros} == {
        datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc),
    }
