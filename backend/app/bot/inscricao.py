"""Inscrição e consulta dos municípios de um chat, entre o bot e o banco.

Recebe a conexão SQLite e a lista de municípios da configuração por parâmetro;
não toca na rede nem no relógio (`agora_utc` entra por parâmetro). Quem fala com
o Telegram é só `app/bot/bot.py` — assim estas regras são testáveis com banco em
memória e nenhum dublê de API.

Privacidade (RNF05): só o identificador do chat e os códigos IBGE escolhidos são
guardados, e `/parar` apaga tudo.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from app.config import Municipio
from app.modelos import banco
from app.modelos.banco import IndiceAtual

#: Texto do botão que inscreve o chat em todos os municípios configurados.
OPCAO_TODOS = "Todos"


def opcoes_do_teclado(municipios: list[Municipio]) -> list[str]:
    """Os rótulos do teclado do `/start`: os municípios da configuração e "Todos".

    Vem da configuração, nunca de lista fixa no código: incluir um município é
    acrescentar um item em `municipios.json` (RNF07).
    """
    return [municipio.nome for municipio in municipios] + [OPCAO_TODOS]


def municipio_sugerido(
    municipios: list[Municipio], argumento: str | None
) -> Municipio | None:
    """Município indicado pelo parâmetro do `/start` (um código IBGE), se houver.

    Devolve `None` quando não há parâmetro ou quando o código não está na
    configuração — o comando segue mostrando o teclado normal, em vez de falhar
    ou de inscrever num município que o sistema não calcula. O parâmetro vem de
    um link externo (`t.me/bot?start=4206900`), então é entrada não confiável.
    """
    if not argumento:
        return None
    for municipio in municipios:
        if municipio.ibge == argumento:
            return municipio
    return None


def inscrever_escolha(
    conexao: sqlite3.Connection,
    municipios: list[Municipio],
    chat_id: int,
    escolha: str,
    agora_utc: datetime,
) -> list[str]:
    """Inscreve `chat_id` conforme o botão apertado. Devolve os `ibge` inscritos.

    `escolha` é o rótulo do teclado: o nome de um município inscreve só ele,
    `OPCAO_TODOS` inscreve todos os configurados. Um rótulo desconhecido não
    inscreve nada e devolve lista vazia — o chat pode digitar qualquer texto, e
    isso não pode virar inscrição em município nenhum.

    Repetir a mesma escolha não duplica (chave `(chat_id, ibge)` no banco).
    """
    if escolha == OPCAO_TODOS:
        escolhidos = list(municipios)
    else:
        escolhidos = [
            municipio for municipio in municipios if municipio.nome == escolha
        ]

    for municipio in escolhidos:
        banco.inscrever(conexao, chat_id, municipio.ibge, agora_utc)

    return [municipio.ibge for municipio in escolhidos]


def parar(conexao: sqlite3.Connection, chat_id: int) -> None:
    """Apaga todos os registros do chat (`/parar`, RNF05)."""
    banco.remover_inscricoes(conexao, chat_id)


def ibges_do_chat(conexao: sqlite3.Connection, chat_id: int) -> set[str]:
    """Códigos IBGE em que `chat_id` está inscrito."""
    linhas = conexao.execute(
        "SELECT ibge FROM inscritos WHERE chat_id = ?", (chat_id,)
    ).fetchall()
    return {linha[0] for linha in linhas}


def situacoes_do_chat(
    conexao: sqlite3.Connection, municipios: list[Municipio], chat_id: int
) -> list[tuple[str, IndiceAtual | None]]:
    """Situação de cada município inscrito, na ordem da configuração.

    Cada item é `(nome, índice atual ou None)` — a forma que `texto_do_status`
    consome. Município inscrito sem nenhum cálculo gravado entra com `None` em
    vez de ficar de fora: quem se inscreveu precisa ver que ele está na lista.
    """
    inscritos = ibges_do_chat(conexao, chat_id)
    return [
        (municipio.nome, banco.indice_atual(conexao, municipio.ibge))
        for municipio in municipios
        if municipio.ibge in inscritos
    ]
