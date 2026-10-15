"""Testes do `scripts.preparar_estado`: o portão antes do commit do `vigia.db`."""

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.modelos import banco
from scripts.preparar_estado import EstadoComInscritosError, main, preparar

CHAT_ID = 987654321


def _criar_banco(caminho: Path, com_inscrito: bool = False) -> None:
    conexao = banco.abrir(caminho)
    try:
        conexao.execute(
            "INSERT INTO indices (ibge, dia_alvo, calculado_em, indice, classe, efr_mm, rtotal_mm,"
            " limiar_mm, n_membros, prob_pontuais, prob_esparsos, prob_generalizados) "
            "VALUES ('3304557', '2026-10-15', '2026-10-15T06:00:00Z', 0.5, 'Baixo',"
            " 75.0, 80.0, 150.0, 51, 0.1, 0.05, 0.01)"
        )
        if com_inscrito:
            banco.inscrever(conexao, CHAT_ID, "3304557", datetime(2026, 10, 15, 6, tzinfo=timezone.utc))
        conexao.commit()
    finally:
        conexao.close()


def _consultar(caminho: Path, sql: str) -> list:
    conexao = sqlite3.connect(caminho)
    try:
        return conexao.execute(sql).fetchall()
    finally:
        conexao.close()


def test_checkpoint_deixa_tudo_no_arquivo_principal(tmp_path):
    origem = tmp_path / "origem"
    origem.mkdir()
    db = origem / "vigia.db"
    _criar_banco(db)

    preparar(db)

    assert not (origem / "vigia.db-wal").exists()
    outra = tmp_path / "outra"
    outra.mkdir()
    shutil.copy(db, outra / "vigia.db")
    assert len(_consultar(outra / "vigia.db", "SELECT * FROM indices")) == 1


def test_journal_mode_fica_delete(tmp_path):
    db = tmp_path / "vigia.db"
    _criar_banco(db)

    preparar(db)

    assert _consultar(db, "PRAGMA journal_mode") == [("delete",)]


def test_inscritos_com_linha_impede_o_commit(tmp_path, capsys):
    db = tmp_path / "vigia.db"
    _criar_banco(db, com_inscrito=True)

    assert main([str(db)]) == 1

    saida = capsys.readouterr()
    assert str(CHAT_ID) not in saida.out + saida.err


def test_preparar_levanta_com_inscritos(tmp_path):
    db = tmp_path / "vigia.db"
    _criar_banco(db, com_inscrito=True)

    with pytest.raises(EstadoComInscritosError):
        preparar(db)


def test_arquivo_inexistente_devolve_1(tmp_path):
    assert main([str(tmp_path / "nao_existe.db")]) == 1
    assert not (tmp_path / "nao_existe.db").exists()


def test_banco_valido_devolve_0(tmp_path):
    db = tmp_path / "vigia.db"
    _criar_banco(db)

    assert main([str(db)]) == 0
