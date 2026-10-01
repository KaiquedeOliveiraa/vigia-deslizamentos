"""Carregamento da configuração do VIGIA: parâmetros por município e variáveis de ambiente.

Nenhuma outra parte do sistema lê `os.environ` diretamente — só `app/main.py`
(Tarefa 11), que repassa o mapeamento para `carregar_env`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

CAMPOS_MUNICIPIO = ("ibge", "nome", "limiar_mm", "fonte_limiar", "mv_h", "pontos")
CAMPOS_PONTO = ("lat", "lon")

#: Nome da variável de ambiente -> nome do atributo correspondente em `Config`.
ATRIBUTO_POR_VARIAVEL = {
    "TELEGRAM_TOKEN": "telegram_token",
    "GITHUB_TOKEN_DADOS": "github_token_dados",
    "GITHUB_REPO": "github_repo",
    "SITE_URL": "site_url",
    "DB_PATH": "db_path",
    "LOG_PATH": "log_path",
}

VARIAVEIS_OBRIGATORIAS = tuple(ATRIBUTO_POR_VARIAVEL)


class ConfiguracaoInvalidaError(Exception):
    """Configuração de município ou de ambiente mal formada ou incompleta."""


@dataclass(frozen=True)
class Ponto:
    """Um ponto de cálculo dentro do município, em graus decimais."""

    lat: float
    lon: float


@dataclass(frozen=True)
class Municipio:
    """Parâmetros de um município, lidos de `backend/config/municipios.json`."""

    ibge: str
    nome: str
    limiar_mm: float
    fonte_limiar: str
    mv_h: float
    pontos: tuple[Ponto, ...]


@dataclass(frozen=True)
class Config:
    """Variáveis de ambiente obrigatórias para rodar o backend."""

    telegram_token: str
    github_token_dados: str
    github_repo: str
    site_url: str
    db_path: str
    log_path: str


def _identificador(item: dict, indice: int) -> str:
    ibge = item.get("ibge")
    return f"'{ibge}'" if ibge is not None else f"índice {indice}"


def _ponto_a_partir_de(bruto: dict, identificador: str, indice_ponto: int) -> Ponto:
    for campo in CAMPOS_PONTO:
        if campo not in bruto:
            raise ConfiguracaoInvalidaError(
                f"município {identificador}: ponto {indice_ponto}: "
                f"campo obrigatório ausente: '{campo}'"
            )
    return Ponto(lat=float(bruto["lat"]), lon=float(bruto["lon"]))


def _municipio_a_partir_de(item: dict, indice: int, ibges_vistos: set[str]) -> Municipio:
    identificador = _identificador(item, indice)

    for campo in CAMPOS_MUNICIPIO:
        if campo not in item:
            raise ConfiguracaoInvalidaError(
                f"município {identificador}: campo obrigatório ausente: '{campo}'"
            )

    ibge = item["ibge"]
    if not (isinstance(ibge, str) and len(ibge) == 7 and ibge.isdigit()):
        raise ConfiguracaoInvalidaError(
            f"município {identificador}: 'ibge' deve ter 7 dígitos, recebido: {ibge!r}"
        )
    if ibge in ibges_vistos:
        raise ConfiguracaoInvalidaError(f"código ibge repetido: '{ibge}'")
    ibges_vistos.add(ibge)

    limiar_mm = item["limiar_mm"]
    if not (isinstance(limiar_mm, (int, float)) and not isinstance(limiar_mm, bool) and limiar_mm > 0):
        raise ConfiguracaoInvalidaError(
            f"município '{ibge}': 'limiar_mm' deve ser maior que zero, recebido: {limiar_mm!r}"
        )

    mv_h = item["mv_h"]
    if not (isinstance(mv_h, (int, float)) and not isinstance(mv_h, bool) and mv_h > 0):
        raise ConfiguracaoInvalidaError(
            f"município '{ibge}': 'mv_h' deve ser maior que zero, recebido: {mv_h!r}"
        )

    pontos_brutos = item["pontos"]
    if not isinstance(pontos_brutos, list) or len(pontos_brutos) == 0:
        raise ConfiguracaoInvalidaError(
            f"município '{ibge}': 'pontos' deve ter ao menos um ponto"
        )

    pontos = tuple(
        _ponto_a_partir_de(ponto_bruto, f"'{ibge}'", indice_ponto)
        for indice_ponto, ponto_bruto in enumerate(pontos_brutos)
    )

    return Municipio(
        ibge=ibge,
        nome=item["nome"],
        limiar_mm=limiar_mm,
        fonte_limiar=item["fonte_limiar"],
        mv_h=mv_h,
        pontos=pontos,
    )


def carregar_municipios(caminho: str | Path) -> list[Municipio]:
    """Lê `municipios.json` e devolve a lista de `Municipio` validados.

    Levanta `ConfiguracaoInvalidaError` se faltar campo obrigatório, se `ibge`
    não tiver 7 dígitos, se `limiar_mm` ou `mv_h` não forem positivos, se não
    houver ao menos um ponto, ou se houver `ibge` repetido.
    """
    bruto = json.loads(Path(caminho).read_text(encoding="utf-8"))

    ibges_vistos: set[str] = set()
    return [
        _municipio_a_partir_de(item, indice, ibges_vistos)
        for indice, item in enumerate(bruto)
    ]


def carregar_env(ambiente: Mapping[str, str]) -> Config:
    """Monta a `Config` a partir de um mapeamento (nunca lido de `os.environ` aqui).

    Levanta `ConfiguracaoInvalidaError` com o nome da variável ausente, e nunca
    com o valor de outra variável.
    """
    valores = {}
    for nome_variavel, atributo in ATRIBUTO_POR_VARIAVEL.items():
        if nome_variavel not in ambiente:
            raise ConfiguracaoInvalidaError(
                f"variável de ambiente obrigatória ausente: '{nome_variavel}'"
            )
        valores[atributo] = ambiente[nome_variavel]

    return Config(**valores)
