"""Configuração comum da suíte.

O único ajuste global é fechar as conexões SQLite que cada teste abre. Os testes
usam banco em memória e não precisam fechá-lo para funcionar, mas o coletor de
lixo emite `ResourceWarning: unclosed database` no fim do processo, e isso faz a
suíte falhar sob `-W error` — que é como as restrições do projeto mandam
verificar a saída. Em vez de espalhar `try/finally` por dezenas de testes, o
fixture registra o que `banco.abrir` devolveu e fecha ao fim de cada teste.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.modelos import banco


@pytest.fixture(autouse=True)
def _fechar_conexoes_sqlite(monkeypatch):
    abertas: list[sqlite3.Connection] = []
    abrir_original = banco.abrir

    def abrir_e_registrar(caminho):
        conexao = abrir_original(caminho)
        abertas.append(conexao)
        return conexao

    monkeypatch.setattr(banco, "abrir", abrir_e_registrar)
    yield
    for conexao in abertas:
        conexao.close()
