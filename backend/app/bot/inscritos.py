"""Fonte dos inscritos do bot: SQLite local ou Worker (Cloudflare D1).

O envio dos avisos só conhece o `RepositorioInscritos`; quem monta o ciclo
escolhe a fonte. Nenhuma mensagem de erro ou de log daqui traz `chat_id` nem o
segredo do Worker: o log do pipeline é público no GitHub Actions.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Protocol

import requests

from app.modelos import banco

_log = logging.getLogger(__name__)


class InscritosIndisponiveisError(Exception):
    """A fonte dos inscritos não pôde ser lida; não se deve avisar nem gravar."""


class RepositorioInscritos(Protocol):
    def listar(self, ibge: str) -> list[int]: ...

    def remover_chat(self, chat_id: int) -> None: ...


class InscritosSqlite:
    """Inscritos no banco SQLite local."""

    def __init__(self, conexao: sqlite3.Connection):
        self._conexao = conexao

    def listar(self, ibge: str) -> list[int]:
        return banco.listar_inscritos(self._conexao, ibge)

    def remover_chat(self, chat_id: int) -> None:
        banco.remover_inscricoes(self._conexao, chat_id)


class InscritosWorker:
    """Inscritos no Worker: uma leitura única, guardada para os municípios."""

    TIMEOUT_S = 30

    def __init__(self, url: str, segredo: str, http):
        self._url = url.rstrip("/")
        self._cabecalhos = {"Authorization": f"Bearer {segredo}"}
        self._http = http
        self._por_ibge: dict[str, list[int]] | None = None

    def _carregar(self) -> dict[str, list[int]]:
        try:
            resposta = self._http.get(
                f"{self._url}/inscritos",
                headers=self._cabecalhos,
                timeout=self.TIMEOUT_S,
            )
        except requests.RequestException as erro:
            raise InscritosIndisponiveisError(
                f"falha ao ler os inscritos do Worker: {type(erro).__name__}"
            ) from None
        if resposta.status_code != 200:
            raise InscritosIndisponiveisError(
                f"Worker respondeu status {resposta.status_code} ao ler os inscritos"
            )
        try:
            itens = resposta.json()["inscritos"]
            por_ibge: dict[str, list[int]] = {}
            for item in itens:
                por_ibge.setdefault(str(item["ibge"]), []).append(int(item["chat_id"]))
        except (ValueError, KeyError, TypeError):
            raise InscritosIndisponiveisError(
                "corpo do Worker sem a lista 'inscritos' válida"
            ) from None
        for chats in por_ibge.values():
            chats.sort()
        return por_ibge

    def listar(self, ibge: str) -> list[int]:
        if self._por_ibge is None:
            self._por_ibge = self._carregar()
        return list(self._por_ibge.get(ibge, []))

    def remover_chat(self, chat_id: int) -> None:
        try:
            resposta = self._http.delete(
                f"{self._url}/inscritos/{chat_id}",
                headers=self._cabecalhos,
                timeout=self.TIMEOUT_S,
            )
        except requests.RequestException as erro:
            _log.warning(
                "falha ao remover inscrição no Worker: %s", type(erro).__name__
            )
            return
        if not 200 <= resposta.status_code < 300:
            _log.warning(
                "falha ao remover inscrição no Worker: status %s",
                resposta.status_code,
            )
            return
        if self._por_ibge is not None:
            for chats in self._por_ibge.values():
                if chat_id in chats:
                    chats.remove(chat_id)
