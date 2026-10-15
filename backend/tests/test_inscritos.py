"""Testes dos repositórios de inscritos (SQLite local e Worker), sem rede."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import pytest
import requests

from app.bot.inscritos import (
    InscritosIndisponiveisError,
    InscritosSqlite,
    InscritosWorker,
)
from app.modelos import banco

URL = "https://worker.exemplo.dev"
SEGREDO = "segredo-super-secreto"
AGORA = datetime(2026, 10, 1, 21, 0, tzinfo=timezone.utc)


class RespostaFalsa:
    def __init__(self, status_code: int, corpo=None):
        self.status_code = status_code
        self._corpo = corpo if corpo is not None else {}
        self.text = json.dumps(self._corpo)

    def json(self):
        return self._corpo


class HttpFalso:
    def __init__(self, respostas_get=None, respostas_delete=None):
        self.respostas_get = list(respostas_get or [])
        self.respostas_delete = list(respostas_delete or [])
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

    def delete(self, url, **kwargs):
        return self._responder(self.respostas_delete, "DELETE", url, kwargs)


def lista(*itens):
    return RespostaFalsa(
        200, {"inscritos": [{"chat_id": c, "ibge": i} for c, i in itens]}
    )


def test_worker_manda_o_segredo_como_bearer():
    http = HttpFalso([lista((1, "4206900"))])

    InscritosWorker(URL, SEGREDO, http).listar("4206900")

    (metodo, url, kwargs), = http.chamadas
    assert (metodo, url) == ("GET", f"{URL}/inscritos")
    assert kwargs["headers"] == {"Authorization": f"Bearer {SEGREDO}"}


def test_worker_agrupa_por_ibge_e_busca_uma_vez_so():
    http = HttpFalso([lista((3, "4206900"), (1, "4206900"), (2, "4205100"))])
    worker = InscritosWorker(URL, SEGREDO, http)

    assert worker.listar("4206900") == [1, 3]
    assert worker.listar("4205100") == [2]
    assert worker.listar("0000000") == []
    assert len(http.chamadas) == 1


def test_worker_lista_vazia_devolve_lista_vazia():
    worker = InscritosWorker(URL, SEGREDO, HttpFalso([lista()]))

    assert worker.listar("4206900") == []


def test_worker_401_levanta_indisponivel():
    worker = InscritosWorker(URL, SEGREDO, HttpFalso([RespostaFalsa(401)]))

    with pytest.raises(InscritosIndisponiveisError, match="401"):
        worker.listar("4206900")


def test_worker_erro_de_rede_levanta_indisponivel():
    http = HttpFalso([requests.ConnectionError("sem rede")])

    with pytest.raises(InscritosIndisponiveisError, match="ConnectionError"):
        InscritosWorker(URL, SEGREDO, http).listar("4206900")


def test_worker_corpo_sem_inscritos_levanta_indisponivel():
    http = HttpFalso([RespostaFalsa(200, {"outra": []})])

    with pytest.raises(InscritosIndisponiveisError):
        InscritosWorker(URL, SEGREDO, http).listar("4206900")


def test_erro_do_worker_nao_contem_o_segredo():
    for resposta in (
        RespostaFalsa(500),
        requests.ConnectionError(f"falha em {URL} com {SEGREDO}"),
        RespostaFalsa(200, {}),
    ):
        worker = InscritosWorker(URL, SEGREDO, HttpFalso([resposta]))
        with pytest.raises(InscritosIndisponiveisError) as info:
            worker.listar("4206900")
        assert SEGREDO not in str(info.value)


def test_timeout_de_30_s_em_todas_as_chamadas():
    http = HttpFalso([lista((1, "4206900"))], [RespostaFalsa(204)])
    worker = InscritosWorker(URL, SEGREDO, http)

    worker.listar("4206900")
    worker.remover_chat(1)

    assert InscritosWorker.TIMEOUT_S == 30
    assert [k["timeout"] for _, _, k in http.chamadas] == [30, 30]


def test_remover_chat_negativo_chama_delete_e_some_da_lista(caplog):
    http = HttpFalso(
        [lista((-1001234567890, "4206900"), (5, "4206900"))], [RespostaFalsa(204)]
    )
    worker = InscritosWorker(URL, SEGREDO, http)
    assert worker.listar("4206900") == [-1001234567890, 5]

    with caplog.at_level("WARNING"):
        worker.remover_chat(-1001234567890)

    assert "falha" not in caplog.text
    metodo, url, kwargs = http.chamadas[-1]
    assert (metodo, url) == ("DELETE", f"{URL}/inscritos/-1001234567890")
    assert kwargs["headers"] == {"Authorization": f"Bearer {SEGREDO}"}
    assert worker.listar("4206900") == [5]


def test_remover_chat_com_falha_nao_levanta_e_nao_loga_o_chat(caplog):
    http = HttpFalso([lista((987654321, "4206900"))], [RespostaFalsa(500)])
    worker = InscritosWorker(URL, SEGREDO, http)
    worker.listar("4206900")

    with caplog.at_level(logging.DEBUG):
        worker.remover_chat(987654321)

    assert caplog.records
    assert "987654321" not in caplog.text
    assert "500" in caplog.text


def test_sqlite_lista_e_remove_pelo_banco():
    conn = banco.abrir(":memory:")
    banco.inscrever(conn, 1, "4206900", AGORA)
    banco.inscrever(conn, 1, "4205100", AGORA)
    banco.inscrever(conn, 2, "4206900", AGORA)
    repo = InscritosSqlite(conn)

    assert repo.listar("4206900") == [1, 2]

    repo.remover_chat(1)

    assert repo.listar("4206900") == [2]
    assert repo.listar("4205100") == []
