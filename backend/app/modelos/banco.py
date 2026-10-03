"""Persistência em SQLite: índices calculados, inscritos do bot e controle de
notificações (README, seção "Banco de dados").

SQL puro com `sqlite3`, sem ORM e sem camada de migração — `schema.sql` usa
`CREATE TABLE IF NOT EXISTS`. **Uma conexão por thread**, nunca compartilhada:
o bot (long polling) e o pipeline agendado rodam no mesmo processo (Tarefa
11), cada um com a sua própria conexão para o mesmo arquivo. `PRAGMA
journal_mode=WAL` é o que permite uma conexão gravar enquanto a outra lê, sem
"database is locked".

Todo `datetime` que entra ou sai desta API é *aware* em UTC; sem fuso levanta
`ValueError`. No banco, data-hora é texto ISO `YYYY-MM-DDTHH:MM:SSZ` (ordena
como texto) e data é `YYYY-MM-DD`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.calculo.agregacao import Resultado

CAMINHO_SCHEMA = Path(__file__).resolve().parent / "schema.sql"

#: Formato de data-hora gravado no banco (ordena como texto).
_FORMATO_DATA_HORA = "%Y-%m-%dT%H:%M:%SZ"

#: Versão do schema, gravada em `PRAGMA user_version`. Subir este número ao
#: mudar `schema.sql` **de forma incompatível** (coluna nova, tipo alterado,
#: restrição nova).
#:
#: Existe porque `CREATE TABLE IF NOT EXISTS` não é camada de migração: num
#: banco fora de versão ele passa batido, `abrir()` não falha, e o erro só
#: aparece na primeira gravação — dentro do `except Exception` do job agendado,
#: o que significa o pipeline parando de gravar e de avisar a cada 6 h, com
#: nada no log além de um traceback genérico, enquanto o site segue servindo o
#: último `indices.json` como se estivesse tudo bem. Falhar ruidosamente na
#: subida é muito melhor.
VERSAO_SCHEMA = 1

#: `user_version` nasce em 0; um banco criado antes desta checagem também está
#: em 0 e já tem o schema corrente. Por isso 0 é aceito como "novo ou anterior
#: ao versionamento", e não como incompatível.
_VERSAO_NAO_MARCADA = 0


class SchemaIncompativelError(Exception):
    """O banco está numa versão de schema que este código não sabe ler."""


def versao_compativel(versao_encontrada: int) -> bool:
    """Se um banco em `versao_encontrada` pode ser usado por este código."""
    return versao_encontrada in (_VERSAO_NAO_MARCADA, VERSAO_SCHEMA)


def _exigir_fuso(nome: str, momento: datetime) -> None:
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError(
            f"'{nome}' precisa ser um datetime com fuso (aware); recebido sem fuso"
        )


def _texto_data_hora(momento: datetime) -> str:
    """`datetime` aware -> texto ISO `YYYY-MM-DDTHH:MM:SSZ`, sempre em UTC."""
    return momento.astimezone(timezone.utc).strftime(_FORMATO_DATA_HORA)


def _data_hora_de_texto(texto: str) -> datetime:
    """Texto ISO `YYYY-MM-DDTHH:MM:SSZ` -> `datetime` aware em UTC."""
    return datetime.strptime(texto, _FORMATO_DATA_HORA).replace(tzinfo=timezone.utc)


def abrir(caminho: str | Path) -> sqlite3.Connection:
    """Abre (ou cria) o banco em `caminho` e aplica `schema.sql`.

    `PRAGMA journal_mode=WAL` e `timeout=30` (segundos de espera por um lock
    antes de levantar erro) permitem uma conexão gravar enquanto outra lê.
    Chamar de novo sobre o mesmo arquivo é seguro (`CREATE TABLE IF NOT
    EXISTS`). Uma conexão por thread — nunca compartilhe a mesma conexão
    entre threads.

    Levanta `SchemaIncompativelError` se o `PRAGMA user_version` do arquivo não
    for compatível com `VERSAO_SCHEMA`, em vez de abrir um banco que falharia na
    primeira gravação.
    """
    conexao = sqlite3.connect(str(caminho), timeout=30)
    try:
        conexao.execute("PRAGMA journal_mode=WAL")

        versao = conexao.execute("PRAGMA user_version").fetchone()[0]
        if not versao_compativel(versao):
            raise SchemaIncompativelError(
                f"o banco '{caminho}' está na versão de schema {versao} e este "
                f"código espera a {VERSAO_SCHEMA}; não há camada de migração — "
                "migre o arquivo ou aponte DB_PATH para outro"
            )

        conexao.executescript(CAMINHO_SCHEMA.read_text(encoding="utf-8"))
        conexao.execute(f"PRAGMA user_version = {VERSAO_SCHEMA}")
        conexao.commit()
    except BaseException:
        conexao.close()
        raise
    return conexao


# --- índices calculados --------------------------------------------------


def gravar_resultado(
    conexao: sqlite3.Connection, resultado: Resultado, calculado_em: datetime
) -> None:
    """Grava os dias-alvo de cada município de `resultado`, numa única transação.

    Chave primária `(ibge, dia_alvo, calculado_em)`: repetir a gravação com o
    mesmo `calculado_em` substitui as linhas em vez de duplicá-las
    (`INSERT OR REPLACE`).

    `limiar_mm` vem do próprio `ResultadoMunicipio`, isto é, do limiar que
    entrou na conta — não da configuração lida na hora de gravar, que pode já
    ter mudado.

    Levanta `ValueError` se `calculado_em` não tiver fuso.
    """
    _exigir_fuso("calculado_em", calculado_em)
    texto_calculado_em = _texto_data_hora(calculado_em)

    linhas = [
        (
            municipio.ibge,
            dia.dia_alvo.isoformat(),
            texto_calculado_em,
            dia.indice,
            dia.classe,
            dia.efr_mm,
            dia.rtotal_mm,
            municipio.limiar_mm,
            dia.n_membros,
            dia.prob.pontuais,
            dia.prob.esparsos,
            dia.prob.generalizados,
        )
        for municipio in resultado.municipios
        for dia in municipio.dias
    ]

    with conexao:
        conexao.executemany(
            """
            INSERT OR REPLACE INTO indices (
                ibge, dia_alvo, calculado_em, indice, classe,
                efr_mm, rtotal_mm, limiar_mm, n_membros,
                prob_pontuais, prob_esparsos, prob_generalizados
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            linhas,
        )


@dataclass(frozen=True)
class ItemHistorico:
    """Um item de `historico`: `{dia_alvo, indice, classe}` do contrato."""

    dia_alvo: date
    indice: float
    classe: int


def historico(
    conexao: sqlite3.Connection, ibge: str, dia_alvo_d0: date, dias: int = 15
) -> list[ItemHistorico]:
    """Histórico de `ibge` nos `dias` dias-alvo anteriores a `dia_alvo_d0`.

    Para cada dia-alvo no intervalo `[dia_alvo_d0 − dias, dia_alvo_d0 − 1]`,
    devolve o cálculo de maior `calculado_em` daquele dia-alvo — nunca mais de
    um item por dia-alvo. A lista vem do mais antigo para o mais recente.
    `dia_alvo_d0` não entra (não é "anterior"), dia futuro a ele tampouco, e
    dia sem nenhum cálculo não aparece (não gera buraco nem linha nula).
    """
    inicio = (dia_alvo_d0 - timedelta(days=dias)).isoformat()
    fim = (dia_alvo_d0 - timedelta(days=1)).isoformat()

    linhas = conexao.execute(
        """
        SELECT dia_alvo, indice, classe FROM (
            SELECT dia_alvo, indice, classe,
                   ROW_NUMBER() OVER (
                       PARTITION BY dia_alvo ORDER BY calculado_em DESC
                   ) AS posicao
            FROM indices
            WHERE ibge = ? AND dia_alvo >= ? AND dia_alvo <= ?
        )
        WHERE posicao = 1
        ORDER BY dia_alvo ASC
        """,
        (ibge, inicio, fim),
    ).fetchall()

    return [
        ItemHistorico(dia_alvo=date.fromisoformat(linha[0]), indice=linha[1], classe=linha[2])
        for linha in linhas
    ]


@dataclass(frozen=True)
class IndiceAtual:
    """Índice, classe, dia-alvo e data/hora do cálculo mais recente de um município.

    `dia_alvo` vai junto porque o `/status` tem de exibi-lo (RN11): quando o
    município fica sem dados numa execução, o índice mais recente é o da
    execução anterior, e sem o dia-alvo o leitor não sabe a que dia ele se
    refere.
    """

    indice: float
    classe: int
    dia_alvo: date
    calculado_em: datetime


def indice_atual(conexao: sqlite3.Connection, ibge: str) -> IndiceAtual | None:
    """Índice, classe e `calculado_em` do D0 do cálculo mais recente de `ibge`.

    O cálculo mais recente é o de maior `calculado_em`; dentro dele, o D0 é o
    menor `dia_alvo` — uma execução do pipeline grava D0..D3 com o mesmo
    `calculado_em`, e D0 é o mais antigo dos quatro. Usado pelo `/status` do
    bot. Devolve `None` se não houver nenhum cálculo gravado para `ibge`.
    """
    linha = conexao.execute(
        """
        SELECT indice, classe, dia_alvo, calculado_em
        FROM indices
        WHERE ibge = ?
          AND calculado_em = (SELECT MAX(calculado_em) FROM indices WHERE ibge = ?)
        ORDER BY dia_alvo ASC
        LIMIT 1
        """,
        (ibge, ibge),
    ).fetchone()

    if linha is None:
        return None

    return IndiceAtual(
        indice=linha[0],
        classe=linha[1],
        dia_alvo=date.fromisoformat(linha[2]),
        calculado_em=_data_hora_de_texto(linha[3]),
    )


# --- inscrições do bot ---------------------------------------------------


def inscrever(
    conexao: sqlite3.Connection, chat_id: int, ibge: str, inscrito_em: datetime
) -> None:
    """Inscreve `chat_id` nos avisos de `ibge`.

    Chave primária `(chat_id, ibge)`: repetir a mesma inscrição não duplica
    (`INSERT OR IGNORE` — a data da inscrição original é preservada).
    """
    _exigir_fuso("inscrito_em", inscrito_em)
    with conexao:
        conexao.execute(
            "INSERT OR IGNORE INTO inscritos (chat_id, ibge, inscrito_em) "
            "VALUES (?, ?, ?)",
            (chat_id, ibge, _texto_data_hora(inscrito_em)),
        )


def listar_inscritos(conexao: sqlite3.Connection, ibge: str) -> list[int]:
    """Lista os `chat_id` inscritos nos avisos de `ibge`."""
    linhas = conexao.execute(
        "SELECT chat_id FROM inscritos WHERE ibge = ? ORDER BY chat_id", (ibge,)
    ).fetchall()
    return [linha[0] for linha in linhas]


def remover_inscricoes(conexao: sqlite3.Connection, chat_id: int) -> None:
    """Remove todas as inscrições de `chat_id` — `/parar` ou bloqueio do bot (RNF05)."""
    with conexao:
        conexao.execute("DELETE FROM inscritos WHERE chat_id = ?", (chat_id,))


# --- controle de notificações ---------------------------------------------


def ultima_classe_notificada(conexao: sqlite3.Connection, ibge: str) -> int | None:
    """Última classe notificada de `ibge`.

    Devolve `None` tanto quando `ibge` nunca foi notificado (sem linha em
    `notificacoes`) quanto quando a classe foi explicitamente zerada
    (`ultima_classe IS NULL`, Tarefa 8): para quem lê, as duas situações são
    a mesma coisa — "sem classe anterior para comparar" (RN08).
    """
    linha = conexao.execute(
        "SELECT ultima_classe FROM notificacoes WHERE ibge = ?", (ibge,)
    ).fetchone()
    return None if linha is None else linha[0]


def atualizar_ultima_classe_notificada(
    conexao: sqlite3.Connection,
    ibge: str,
    classe: int | None,
    notificado_em: datetime,
) -> None:
    """Grava a última classe notificada de `ibge`, inclusive `None` (zera, RN08)."""
    _exigir_fuso("notificado_em", notificado_em)
    with conexao:
        conexao.execute(
            "INSERT OR REPLACE INTO notificacoes (ibge, ultima_classe, notificado_em) "
            "VALUES (?, ?, ?)",
            (ibge, classe, _texto_data_hora(notificado_em)),
        )
