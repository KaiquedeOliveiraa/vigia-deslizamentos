"""Prepara o `vigia.db` para o commit na branch pública `estado`.

Antes do commit o script confere que a tabela `inscritos` está vazia (os inscritos vivem no Worker,
e o banco publicado é público) e faz o checkpoint do WAL, deixando o banco inteiro dentro do
`vigia.db`, sem `-wal` nem `-shm`.

    python -m scripts.preparar_estado ../estado/vigia.db
"""

import sqlite3
import sys
from pathlib import Path


class EstadoComInscritosError(Exception):
    """A tabela `inscritos` tem linhas: o banco não pode ir para a branch pública."""


def preparar(caminho_db: Path) -> None:
    conexao = sqlite3.connect(caminho_db)
    try:
        (total,) = conexao.execute("SELECT COUNT(*) FROM inscritos").fetchone()
        if total:
            raise EstadoComInscritosError(f"a tabela inscritos tem {total} linha(s)")
        conexao.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        conexao.execute("PRAGMA journal_mode=DELETE").fetchall()
    finally:
        conexao.close()


def main(argv: list[str] | None = None) -> int:
    argumentos = sys.argv[1:] if argv is None else argv
    if len(argumentos) != 1:
        print("uso: python -m scripts.preparar_estado <caminho do vigia.db>", file=sys.stderr)
        return 1
    caminho = Path(argumentos[0])
    if not caminho.is_file():
        print(f"banco não encontrado: {caminho}", file=sys.stderr)
        return 1
    try:
        preparar(caminho)
    except EstadoComInscritosError as erro:
        print(f"commit bloqueado: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
