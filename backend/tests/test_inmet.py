"""Testes da coleta do INMET e da comparação de 24 h (Tarefa 12).

Nenhum teste acessa a rede. Duas fixtures:

- `inmet_estacoes.json`: subconjunto **real** de `GET /estacoes/T` (as estações
  de SC mais próximas da região mais uma da Bahia, para provar o descarte);
- `inmet_chuva_horaria.json`: **sintética**. A rota de chuva horária do INMET
  exige token obtido por e-mail (`docs/decisoes/ensemble.md` §8, confirmado por
  resposta real `"CHAVE INVÁLIDA!"`), então não há resposta real para gravar. O
  formato segue os nomes de campo documentados; se o token chegar e o formato
  divergir, é a fixture que muda, não a interface.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import requests

from app.calculo.agregacao import Resultado, ResultadoDia, ResultadoMunicipio
from app.classificacao.probabilidades import Probabilidades
from app.coleta import inmet
from app.config import Config, Municipio, Ponto

UTC = timezone.utc
AGORA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
RAIZ_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fixture(nome: str):
    return json.loads((RAIZ_FIXTURES / nome).read_text(encoding="utf-8"))


def municipio(ibge: str, nome: str, lat: float, lon: float) -> Municipio:
    return Municipio(
        ibge=ibge,
        nome=nome,
        limiar_mm=250.0,
        fonte_limiar="teste",
        mv_h=24.0,
        pontos=(Ponto(lat=lat, lon=lon),),
    )


# Centroides reais (backend/config/municipios.json).
IBIRAMA = municipio("4206900", "Ibirama", -27.0181, -49.5286)
JOSE_BOITEUX = municipio("4209151", "José Boiteux", -26.8595, -49.6463)
MUNICIPIOS = [IBIRAMA, JOSE_BOITEUX]


def config_de_teste(inmet_token: str | None = "token-valido") -> Config:
    return Config(
        telegram_token="123:ABC",
        github_token_dados="ghp_x",
        github_repo="dono/repo",
        site_url="https://exemplo.org",
        db_path=":memory:",
        log_path="vigia.log",
        inmet_token=inmet_token,
    )


class RespostaFalsa:
    def __init__(self, corpo, status_code: int = 200):
        self._corpo = corpo
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"status {self.status_code}")

    def json(self):
        if isinstance(self._corpo, Exception):
            raise self._corpo
        return self._corpo


class HttpFalso:
    def __init__(self, resposta_por_prefixo: dict[str, object]):
        self.resposta_por_prefixo = resposta_por_prefixo
        self.urls: list[str] = []

    def get(self, url, params=None, timeout=None):
        self.urls.append(url)
        for prefixo, resposta in self.resposta_por_prefixo.items():
            if prefixo in url:
                if isinstance(resposta, Exception):
                    raise resposta
                return resposta
        raise AssertionError(f"chamada inesperada: {url}")


# --- haversine ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("codigo", "distancia_esperada"),
    [("A817", 30.7), ("A861", 61.0), ("A863", 69.4)],
)
def test_haversine_reproduz_as_distancias_da_decisao_da_tarefa_0(
    codigo, distancia_esperada
):
    # Ponto de referência e valores da tabela da §8 de
    # docs/decisoes/ensemble.md. As coordenadas vêm da fixture (resposta real
    # do INMET), não de literais digitados à mão.
    bruta = next(
        estacao
        for estacao in _fixture("inmet_estacoes.json")
        if estacao["CD_ESTACAO"] == codigo
    )

    distancia = inmet.distancia_km(
        -26.8, -49.55, float(bruta["VL_LATITUDE"]), float(bruta["VL_LONGITUDE"])
    )

    assert distancia == pytest.approx(distancia_esperada, abs=0.1)


def test_haversine_corrige_a_longitude_pelo_cosseno_da_latitude():
    # 1 grau de longitude a -27° de latitude vale ~99 km, não ~111 km.
    assert inmet.distancia_km(-27.0, -49.0, -27.0, -50.0) == pytest.approx(99.1, abs=0.5)


# --- associação das estações --------------------------------------------------


def test_associa_cada_estacao_ao_municipio_mais_proximo_e_converte_para_o_contrato():
    estacoes = inmet.associar_estacoes(_fixture("inmet_estacoes.json"), MUNICIPIOS)

    por_codigo = {estacao.codigo: estacao for estacao in estacoes}
    assert por_codigo["A861"].nome == "RIO DO CAMPO"
    assert por_codigo["A861"].ibge == "4209151"  # José Boiteux é o mais próximo
    assert por_codigo["A861"].lat == pytest.approx(-26.9381, abs=0.01)
    assert por_codigo["A861"].lon == pytest.approx(-50.1455, abs=0.01)


def test_descarta_estacao_fora_do_raio_de_corte():
    # ACAJUTIBA (BA) está a milhares de quilômetros dos seis municípios.
    estacoes = inmet.associar_estacoes(_fixture("inmet_estacoes.json"), MUNICIPIOS)

    assert "A472" not in {estacao.codigo for estacao in estacoes}


def test_descarta_estacao_fora_de_operacao():
    # A817 (Indaial) é a mais próxima de todas, e está em pane: incluí-la faria
    # a comparação apontar para uma estação que não mede nada.
    estacoes = inmet.associar_estacoes(_fixture("inmet_estacoes.json"), MUNICIPIOS)

    codigos = {estacao.codigo for estacao in estacoes}
    assert "A817" not in codigos
    assert "A862" not in codigos  # Rio Negrinho, também em pane


def test_descarta_estacao_que_nao_e_automatica():
    bruta = {
        "CD_ESTACAO": "B999",
        "DC_NOME": "CONVENCIONAL",
        "CD_SITUACAO": "Operante",
        "TP_ESTACAO": "Convencional",
        "VL_LATITUDE": "-27.0181",
        "VL_LONGITUDE": "-49.5286",
    }

    assert inmet.associar_estacoes([bruta], MUNICIPIOS) == []


def test_raio_de_corte_mais_estreito_descarta_todas_as_estacoes_da_regiao():
    # Nenhuma estação operante fica dentro dos seis municípios: a mais próxima
    # está a ~61 km (ensemble.md §8). Com raio de 10 km, não sobra nenhuma.
    estacoes = inmet.associar_estacoes(
        _fixture("inmet_estacoes.json"), MUNICIPIOS, raio_km=10
    )

    assert estacoes == []


def test_estacao_registra_a_distancia_ate_o_municipio_de_referencia():
    # Sem esse campo, uma estação a 61 km passaria por estação "do município".
    estacoes = inmet.associar_estacoes(_fixture("inmet_estacoes.json"), MUNICIPIOS)

    por_codigo = {estacao.codigo: estacao for estacao in estacoes}
    assert por_codigo["A861"].distancia_km > 50


def test_estacoes_em_json_tem_exatamente_as_chaves_do_contrato_mais_a_distancia():
    estacoes = inmet.associar_estacoes(_fixture("inmet_estacoes.json"), MUNICIPIOS)

    item = inmet.estacao_em_json(estacoes[0])

    assert set(item) == {"codigo", "nome", "ibge", "lat", "lon", "distancia_km"}


# --- chuva de 24 h ------------------------------------------------------------


def test_chuva_24h_soma_os_registros_da_janela():
    http = HttpFalso({"apitempo.inmet.gov.br": RespostaFalsa(_fixture("inmet_chuva_horaria.json"))})

    medida = inmet.chuva_24h(http, "A861", AGORA, "token-valido")

    assert medida == pytest.approx(24 * 1.5)


def test_chuva_24h_ignora_registro_sem_valor():
    registros = _fixture("inmet_chuva_horaria.json")
    registros[0]["CHUVA"] = None
    registros[1]["CHUVA"] = ""
    http = HttpFalso({"apitempo.inmet.gov.br": RespostaFalsa(registros)})

    medida = inmet.chuva_24h(http, "A861", AGORA, "token-valido")

    assert medida == pytest.approx(22 * 1.5)


def test_chuva_24h_sem_nenhum_registro_devolve_none():
    http = HttpFalso({"apitempo.inmet.gov.br": RespostaFalsa([])})

    assert inmet.chuva_24h(http, "A861", AGORA, "token-valido") is None


def test_chuva_24h_com_resposta_204_sem_corpo_devolve_none():
    # Foi o que a API devolveu em toda combinação testada na Tarefa 0.
    http = HttpFalso({"apitempo.inmet.gov.br": RespostaFalsa(None, status_code=204)})

    assert inmet.chuva_24h(http, "A861", AGORA, "token-valido") is None


def test_chuva_24h_com_chave_invalida_devolve_none():
    # A API responde 200 com o corpo "CHAVE INVÁLIDA!" (texto, não lista).
    http = HttpFalso({"apitempo.inmet.gov.br": RespostaFalsa("CHAVE INVÁLIDA!")})

    assert inmet.chuva_24h(http, "A861", AGORA, "token-valido") is None


def test_chuva_24h_com_erro_de_rede_devolve_none():
    http = HttpFalso({"apitempo.inmet.gov.br": requests.exceptions.ConnectionError("sem rede")})

    assert inmet.chuva_24h(http, "A861", AGORA, "token-valido") is None


def test_o_token_nao_aparece_em_mensagem_de_log(caplog):
    token = "token-secreto-do-inmet"
    http = HttpFalso({"apitempo.inmet.gov.br": requests.exceptions.ConnectionError("sem rede")})

    with caplog.at_level(logging.DEBUG):
        inmet.chuva_24h(http, "A861", AGORA, token)

    for registro in caplog.records:
        assert token not in registro.getMessage()


# --- comparação registrada no log ---------------------------------------------


def resultado_de_teste(chuva_24h_prevista: float = 30.0) -> Resultado:
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
                ibge="4209151",
                limiar_mm=250.0,
                dias=(dia, dia, dia, dia),
                chuva_acum_mm={
                    "24h": chuva_24h_prevista,
                    "48h": 60.0,
                    "72h": 90.0,
                    "96h": 120.0,
                },
            )
        ],
        municipios_sem_dados=[],
    )


def estacoes_de_teste():
    return inmet.associar_estacoes(_fixture("inmet_estacoes.json"), MUNICIPIOS)


def test_comparacao_registra_a_diferenca_entre_medido_e_calculado(caplog):
    http = HttpFalso({"apitempo.inmet.gov.br": RespostaFalsa(_fixture("inmet_chuva_horaria.json"))})

    with caplog.at_level(logging.INFO):
        inmet.registrar_comparacao_24h(
            resultado_de_teste(chuva_24h_prevista=30.0),
            AGORA,
            http,
            config_de_teste(),
            estacoes=estacoes_de_teste(),
        )

    mensagens = " ".join(registro.getMessage() for registro in caplog.records)
    assert "A861" in mensagens
    assert "4209151" in mensagens
    # Medido 36,0 mm contra 30,0 mm calculados: diferença de 6,0 mm.
    assert "6.0" in mensagens or "6,0" in mensagens


def test_comparacao_nao_altera_o_resultado():
    resultado = resultado_de_teste()
    http = HttpFalso({"apitempo.inmet.gov.br": RespostaFalsa(_fixture("inmet_chuva_horaria.json"))})

    inmet.registrar_comparacao_24h(
        resultado, AGORA, http, config_de_teste(), estacoes=estacoes_de_teste()
    )

    assert resultado.municipios[0].dias[0].indice == 1.2
    assert resultado.municipios[0].chuva_acum_mm["24h"] == 30.0


def test_estacao_sem_dado_registra_a_ausencia_e_nao_interrompe(caplog):
    http = HttpFalso({"apitempo.inmet.gov.br": RespostaFalsa([])})

    with caplog.at_level(logging.INFO):
        inmet.registrar_comparacao_24h(
            resultado_de_teste(), AGORA, http, config_de_teste(), estacoes=estacoes_de_teste()
        )

    assert caplog.records != []


def test_erro_do_inmet_nao_interrompe_o_pipeline(caplog):
    http = HttpFalso({"apitempo.inmet.gov.br": requests.exceptions.ConnectionError("sem rede")})

    with caplog.at_level(logging.INFO):
        inmet.registrar_comparacao_24h(
            resultado_de_teste(), AGORA, http, config_de_teste(), estacoes=estacoes_de_teste()
        )

    # Nenhuma exceção escapou — é o que este teste prova.


def test_erro_inesperado_na_comparacao_nao_interrompe_o_pipeline():
    class HttpQueExplode:
        def get(self, *_, **__):
            raise RuntimeError("defeito inesperado")

    inmet.registrar_comparacao_24h(
        resultado_de_teste(),
        AGORA,
        HttpQueExplode(),
        config_de_teste(),
        estacoes=estacoes_de_teste(),
    )


def test_sem_token_do_inmet_a_comparacao_e_pulada_com_o_motivo_no_log(caplog):
    class HttpQueNaoDeveSerChamado:
        def get(self, *_, **__):
            raise AssertionError("não deveria chamar o INMET sem token")

    with caplog.at_level(logging.INFO):
        inmet.registrar_comparacao_24h(
            resultado_de_teste(),
            AGORA,
            HttpQueNaoDeveSerChamado(),
            config_de_teste(inmet_token=None),
            estacoes=estacoes_de_teste(),
        )

    mensagens = " ".join(registro.getMessage() for registro in caplog.records)
    assert "token" in mensagens.lower()


def test_municipio_sem_estacao_de_referencia_nao_gera_comparacao():
    class HttpQueNaoDeveSerChamado:
        def get(self, *_, **__):
            raise AssertionError("não deveria chamar o INMET sem estação")

    inmet.registrar_comparacao_24h(
        resultado_de_teste(), AGORA, HttpQueNaoDeveSerChamado(), config_de_teste(), estacoes=[]
    )


# --- carregamento do estacoes.json -------------------------------------------


def test_carregar_estacoes_de_arquivo_inexistente_devolve_lista_vazia(tmp_path):
    assert inmet.carregar_estacoes(tmp_path / "nao-existe.json") == []


def test_carregar_estacoes_le_o_arquivo_gerado_pelo_script(tmp_path):
    caminho = tmp_path / "estacoes.json"
    caminho.write_text(
        json.dumps(
            [
                {
                    "codigo": "A861",
                    "nome": "RIO DO CAMPO",
                    "ibge": "4209151",
                    "lat": -26.9381,
                    "lon": -50.1455,
                    "distancia_km": 61.0,
                }
            ]
        ),
        encoding="utf-8",
    )

    (estacao,) = inmet.carregar_estacoes(caminho)

    assert estacao.codigo == "A861"
    assert estacao.ibge == "4209151"


# --- script gerador -----------------------------------------------------------


def test_script_gera_os_itens_do_contrato_ordenados_por_municipio_e_distancia():
    from scripts.gerar_estacoes import gerar

    itens = gerar(_fixture("inmet_estacoes.json"), MUNICIPIOS, raio_km=100.0)

    assert all(set(item) == {"codigo", "nome", "ibge", "lat", "lon", "distancia_km"} for item in itens)
    chaves = [(item["ibge"], item["distancia_km"]) for item in itens]
    assert chaves == sorted(chaves)


def test_script_grava_o_arquivo_com_quebra_de_linha_final(tmp_path):
    from scripts.gerar_estacoes import gerar, gravar

    caminho = tmp_path / "data" / "estacoes.json"
    itens = gerar(_fixture("inmet_estacoes.json"), MUNICIPIOS, raio_km=100.0)

    gravar(itens, caminho)

    conteudo = caminho.read_text(encoding="utf-8")
    assert conteudo.endswith("\n")
    assert json.loads(conteudo) == itens


def test_script_com_raio_estreito_grava_lista_vazia_em_vez_de_falhar(tmp_path):
    from scripts.gerar_estacoes import gerar, gravar

    caminho = tmp_path / "estacoes.json"
    gravar(gerar(_fixture("inmet_estacoes.json"), MUNICIPIOS, raio_km=1.0), caminho)

    assert json.loads(caminho.read_text(encoding="utf-8")) == []
