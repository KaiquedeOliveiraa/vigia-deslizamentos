"""Testes da publicação do `indices.json` no repositório (Tarefa 9).

Nenhum teste acessa a rede: o cliente HTTP é um dublê que registra as chamadas
e devolve respostas programadas. A publicação nunca propaga exceção — ela
registra o erro e devolve `False`, porque uma falha de commit não pode impedir
os avisos do bot (contrato de dados, seção "Publicação").
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging

import pytest
import requests

from app.config import Config
from app.exportacao.publicar import CAMINHO_HISTORICO, CAMINHO_NO_REPOSITORIO, BRANCH, publicar, sha_do_blob

TOKEN = "ghp_segredo_que_nunca_pode_aparecer_no_log"
CONTEUDO = b'{"schema_version": 1}\n'


def config_de_teste() -> Config:
    return Config(
        telegram_token="telegram:nao-usado-aqui",
        github_token_dados=TOKEN,
        github_repo="KaiquedeOliveiraa/vigia-deslizamentos",
        site_url="https://exemplo.org",
        db_path=":memory:",
        log_path="vigia.log",
    )


class RespostaFalsa:
    """Dublê de `requests.Response` com o necessário para a publicação."""

    def __init__(self, status_code: int, corpo=None):
        self.status_code = status_code
        self._corpo = corpo if corpo is not None else {}
        self.text = json.dumps(self._corpo)

    def json(self):
        return self._corpo


class HttpFalso:
    """Devolve respostas programadas por método e registra cada chamada.

    `respostas_get` e `respostas_put` são filas: cada chamada consome a
    primeira. Um item que seja exceção é levantado em vez de devolvido, para
    simular falha de transporte.
    """

    def __init__(self, respostas_get=None, respostas_put=None):
        self.respostas_get = list(respostas_get or [])
        self.respostas_put = list(respostas_put or [])
        self.chamadas: list[tuple[str, str, dict]] = []

    def _responder(self, fila, metodo, url, kwargs):
        self.chamadas.append((metodo, url, kwargs))
        if not fila:
            raise AssertionError(f"{metodo} {url}: nenhuma resposta programada")
        resposta = fila.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    def get(self, url, **kwargs):
        return self._responder(self.respostas_get, "GET", url, kwargs)

    def put(self, url, **kwargs):
        return self._responder(self.respostas_put, "PUT", url, kwargs)


def _chamadas(http: HttpFalso, metodo: str) -> list[tuple[str, dict]]:
    return [(url, kwargs) for m, url, kwargs in http.chamadas if m == metodo]


# --- caminho de sucesso -------------------------------------------------------


def test_arquivo_existente_envia_o_sha_lido_na_leitura():
    http = HttpFalso(
        respostas_get=[RespostaFalsa(200, {"sha": "abc123"})],
        respostas_put=[RespostaFalsa(200, {"commit": {"sha": "novo"}})],
    )

    assert publicar(CONTEUDO, config_de_teste(), http) is True

    (url_put, kwargs_put), = _chamadas(http, "PUT")
    assert url_put == (
        "https://api.github.com/repos/KaiquedeOliveiraa/vigia-deslizamentos/"
        f"contents/{CAMINHO_NO_REPOSITORIO}"
    )
    assert kwargs_put["json"]["sha"] == "abc123"
    assert kwargs_put["json"]["branch"] == BRANCH == "main"


def test_conteudo_vai_em_base64_e_volta_byte_a_byte():
    http = HttpFalso(
        respostas_get=[RespostaFalsa(200, {"sha": "abc123"})],
        respostas_put=[RespostaFalsa(200, {})],
    )

    publicar(CONTEUDO, config_de_teste(), http)

    (_, kwargs_put), = _chamadas(http, "PUT")
    assert base64.b64decode(kwargs_put["json"]["content"]) == CONTEUDO


def test_token_vai_no_cabecalho_de_autorizacao_das_duas_chamadas():
    http = HttpFalso(
        respostas_get=[RespostaFalsa(200, {"sha": "abc123"})],
        respostas_put=[RespostaFalsa(200, {})],
    )

    publicar(CONTEUDO, config_de_teste(), http)

    for _, _, kwargs in http.chamadas:
        assert kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"


def test_arquivo_inexistente_cria_sem_sha():
    http = HttpFalso(
        respostas_get=[RespostaFalsa(404, {"message": "Not Found"})],
        respostas_put=[RespostaFalsa(201, {})],
    )

    assert publicar(CONTEUDO, config_de_teste(), http) is True

    (_, kwargs_put), = _chamadas(http, "PUT")
    assert "sha" not in kwargs_put["json"]


def test_status_201_tambem_e_sucesso():
    http = HttpFalso(
        respostas_get=[RespostaFalsa(404, {})], respostas_put=[RespostaFalsa(201, {})]
    )

    assert publicar(CONTEUDO, config_de_teste(), http) is True


# --- conflito (409) -----------------------------------------------------------


def test_conflito_409_le_o_sha_de_novo_e_tenta_uma_vez():
    http = HttpFalso(
        respostas_get=[
            RespostaFalsa(200, {"sha": "sha_velho"}),
            RespostaFalsa(200, {"sha": "sha_novo"}),
        ],
        respostas_put=[RespostaFalsa(409, {"message": "conflict"}), RespostaFalsa(200, {})],
    )

    assert publicar(CONTEUDO, config_de_teste(), http) is True

    puts = _chamadas(http, "PUT")
    assert len(puts) == 2
    assert puts[0][1]["json"]["sha"] == "sha_velho"
    assert puts[1][1]["json"]["sha"] == "sha_novo"
    assert len(_chamadas(http, "GET")) == 2


def test_conflito_409_e_o_outro_ja_publicou_o_mesmo_conteudo_nao_reenvia():
    # Depois do 409 o sha relido pode já ser o do nosso conteúdo: nada a enviar.
    http = HttpFalso(
        respostas_get=[
            RespostaFalsa(200, {"sha": "sha_velho"}),
            RespostaFalsa(200, {"sha": sha_do_blob(CONTEUDO)}),
        ],
        respostas_put=[RespostaFalsa(409, {})],
    )

    assert publicar(CONTEUDO, config_de_teste(), http) is True
    assert len(_chamadas(http, "PUT")) == 1


def test_conflito_409_duas_vezes_desiste_e_devolve_false():
    # Uma retentativa, não um laço: duas execuções simultâneas gravando o mesmo
    # arquivo não podem virar tentativa infinita.
    http = HttpFalso(
        respostas_get=[
            RespostaFalsa(200, {"sha": "sha_velho"}),
            RespostaFalsa(200, {"sha": "sha_novo"}),
        ],
        respostas_put=[RespostaFalsa(409, {}), RespostaFalsa(409, {})],
    )

    assert publicar(CONTEUDO, config_de_teste(), http) is False
    assert len(_chamadas(http, "PUT")) == 2


# --- falhas -------------------------------------------------------------------


def test_erro_de_rede_na_leitura_devolve_false_sem_excecao(caplog):
    http = HttpFalso(
        respostas_get=[requests.exceptions.ConnectionError("sem rede")],
        respostas_put=[],
    )

    with caplog.at_level(logging.ERROR):
        assert publicar(CONTEUDO, config_de_teste(), http) is False

    assert [registro.levelname for registro in caplog.records] == ["ERROR"]
    assert "transporte" in caplog.records[0].getMessage()


def test_erro_de_rede_no_envio_devolve_false_sem_excecao(caplog):
    http = HttpFalso(
        respostas_get=[RespostaFalsa(200, {"sha": "abc123"})],
        respostas_put=[requests.exceptions.ConnectionError("sem rede")],
    )

    with caplog.at_level(logging.ERROR):
        assert publicar(CONTEUDO, config_de_teste(), http) is False

    assert [registro.levelname for registro in caplog.records] == ["ERROR"]
    assert "transporte" in caplog.records[0].getMessage()


def test_401_devolve_false_sem_excecao(caplog):
    http = HttpFalso(
        respostas_get=[RespostaFalsa(200, {"sha": "abc123"})],
        respostas_put=[RespostaFalsa(401, {"message": "Bad credentials"})],
    )

    with caplog.at_level(logging.ERROR):
        assert publicar(CONTEUDO, config_de_teste(), http) is False

    assert [registro.levelname for registro in caplog.records] == ["ERROR"]
    assert "401" in caplog.records[0].getMessage()


def test_401_na_leitura_nao_e_tratado_como_arquivo_inexistente(caplog):
    # Só 404 significa "arquivo não existe". Tratar 401 como ausência faria o
    # PUT sair sem `sha` e, num token corrigido depois, sobrescrever o arquivo.
    http = HttpFalso(respostas_get=[RespostaFalsa(401, {})], respostas_put=[])

    with caplog.at_level(logging.ERROR):
        assert publicar(CONTEUDO, config_de_teste(), http) is False

    assert _chamadas(http, "PUT") == []


@pytest.mark.parametrize(
    "http",
    [
        HttpFalso(
            respostas_get=[RespostaFalsa(401, {"message": f"token {TOKEN} rejeitado"})],
            respostas_put=[],
        ),
        HttpFalso(
            respostas_get=[RespostaFalsa(200, {"sha": "abc123"})],
            respostas_put=[RespostaFalsa(401, {"message": f"token {TOKEN} rejeitado"})],
        ),
        HttpFalso(
            respostas_get=[requests.exceptions.ConnectionError(f"url?token={TOKEN}")],
            respostas_put=[],
        ),
    ],
)
def test_nada_registrado_no_log_contem_o_token(http, caplog):
    with caplog.at_level(logging.DEBUG):
        publicar(CONTEUDO, config_de_teste(), http)

    # Sem esta linha o teste passaria num mundo em que a publicação não registra
    # nada — e aí ele não protegeria a RNF06, só pareceria proteger.
    assert caplog.records
    for registro in caplog.records:
        assert TOKEN not in registro.getMessage()
        assert TOKEN not in str(registro.args or "")


def test_timeout_e_passado_em_todas_as_chamadas():
    http = HttpFalso(
        respostas_get=[RespostaFalsa(200, {"sha": "abc123"})],
        respostas_put=[RespostaFalsa(200, {})],
    )

    publicar(CONTEUDO, config_de_teste(), http)

    for _, _, kwargs in http.chamadas:
        assert kwargs["timeout"] == 30


# --- corpo anômalo na leitura do sha ------------------------------------------


class RespostaComJsonInvalido:
    """200 cujo corpo não é JSON — proxy corporativo, portal cativo, página de erro."""

    status_code = 200
    text = "<html>502 Bad Gateway</html>"

    def json(self):
        raise requests.exceptions.JSONDecodeError("Expecting value", "", 0)


def test_corpo_nao_json_na_leitura_devolve_false_sem_excecao(caplog):
    http = HttpFalso(respostas_get=[RespostaComJsonInvalido()], respostas_put=[])

    with caplog.at_level(logging.ERROR):
        assert publicar(CONTEUDO, config_de_teste(), http) is False

    assert caplog.records
    assert _chamadas(http, "PUT") == []


def test_corpo_lista_na_leitura_devolve_false_sem_excecao(caplog):
    # A API de conteúdo do GitHub devolve uma lista quando o caminho é um
    # diretório; `.get("sha")` numa lista levantaria AttributeError.
    http = HttpFalso(
        respostas_get=[RespostaFalsa(200, [{"name": "indices.json"}])],
        respostas_put=[],
    )

    with caplog.at_level(logging.ERROR):
        assert publicar(CONTEUDO, config_de_teste(), http) is False

    assert caplog.records
    assert _chamadas(http, "PUT") == []


# --- caminho parametrizado e pulo quando nada mudou ---------------------------


def test_caminho_historico_vai_na_url_e_na_mensagem_do_commit():
    http = HttpFalso(
        respostas_get=[RespostaFalsa(200, {"sha": "abc123"})],
        respostas_put=[RespostaFalsa(200, {})],
    )

    assert publicar(b"x", config_de_teste(), http, caminho=CAMINHO_HISTORICO) is True

    (url_get, _), = _chamadas(http, "GET")
    (url_put, kwargs_put), = _chamadas(http, "PUT")
    assert url_get.endswith("/contents/frontend/public/data/historico.json")
    assert url_put.endswith("/contents/frontend/public/data/historico.json")
    assert "historico.json" in kwargs_put["json"]["message"]


def test_sha_igual_ao_do_conteudo_nao_envia_e_devolve_true(caplog):
    sha = hashlib.sha1(b"blob 1\0x").hexdigest()
    http = HttpFalso(respostas_get=[RespostaFalsa(200, {"sha": sha})], respostas_put=[])

    with caplog.at_level(logging.INFO):
        assert publicar(b"x", config_de_teste(), http, caminho=CAMINHO_HISTORICO) is True

    assert _chamadas(http, "PUT") == []
    assert "sem mudança" in caplog.text


def test_sha_diferente_envia_normalmente():
    http = HttpFalso(
        respostas_get=[RespostaFalsa(200, {"sha": "outro"})],
        respostas_put=[RespostaFalsa(200, {})],
    )

    assert publicar(b"x", config_de_teste(), http) is True
    assert len(_chamadas(http, "PUT")) == 1
