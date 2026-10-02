"""Publicação do `indices.json` por commit automático no repositório.

Usa a API de conteúdo do GitHub: um `PUT` em
`/repos/{dono}/{repo}/contents/frontend/public/data/indices.json` cria ou
substitui o arquivo no branch `main`, e o commit dispara o deploy do site.
Substituir exige o `sha` do blob atual, lido antes por um `GET`.

**A publicação nunca propaga exceção.** Falha de rede, token inválido ou
conflito registram o erro e devolvem `False`: o contrato de dados diz que o
erro é registrado e o pipeline continua, porque os avisos do bot não dependem
da publicação e o site segue mostrando o último JSON válido (RNF04/UC06).

O token nunca entra em mensagem de log: ele vai só no cabeçalho
`Authorization`, e o que se registra de uma resposta é o status, nunca o corpo
nem a exceção crua — o corpo de erro do GitHub pode repetir credenciais, e a
exceção de `requests` pode trazer a URL inteira (RNF06).
"""

from __future__ import annotations

import base64
import logging

import requests

from app.config import Config

CAMINHO_NO_REPOSITORIO = "frontend/public/data/indices.json"
BRANCH = "main"
URL_BASE = "https://api.github.com"
TIMEOUT_S = 30

#: Status que a API devolve quando o arquivo foi criado (201) ou atualizado (200).
STATUS_DE_SUCESSO = (200, 201)

_log = logging.getLogger(__name__)


def _url(config: Config) -> str:
    return f"{URL_BASE}/repos/{config.github_repo}/contents/{CAMINHO_NO_REPOSITORIO}"


def _cabecalhos(config: Config) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.github_token_dados}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


class _FalhaDePublicacao(Exception):
    """Falha já descrita numa mensagem segura (sem token, sem corpo de resposta)."""


def _ler_sha(config: Config, http) -> str | None:
    """`sha` do blob atual, ou `None` se o arquivo ainda não existe (404).

    Qualquer outro status é falha: tratar 401 ou 403 como "não existe" faria o
    `PUT` seguinte sair sem `sha` e, com a credencial corrigida depois,
    sobrescrever o arquivo em vez de atualizá-lo.
    """
    try:
        resposta = http.get(
            _url(config),
            headers=_cabecalhos(config),
            params={"ref": BRANCH},
            timeout=TIMEOUT_S,
        )
    except requests.exceptions.RequestException as erro:
        raise _FalhaDePublicacao(
            f"falha de transporte ao ler o arquivo atual: {type(erro).__name__}"
        ) from None

    if resposta.status_code == 404:
        return None
    if resposta.status_code != 200:
        raise _FalhaDePublicacao(
            f"leitura do arquivo atual devolveu status {resposta.status_code}"
        )
    return resposta.json().get("sha")


def _enviar(conteudo: bytes, config: Config, http, sha: str | None) -> int:
    corpo = {
        "message": "chore(dados): atualiza indices.json",
        "content": base64.b64encode(conteudo).decode("ascii"),
        "branch": BRANCH,
    }
    if sha is not None:
        corpo["sha"] = sha

    try:
        resposta = http.put(
            _url(config), headers=_cabecalhos(config), json=corpo, timeout=TIMEOUT_S
        )
    except requests.exceptions.RequestException as erro:
        raise _FalhaDePublicacao(
            f"falha de transporte ao enviar o arquivo: {type(erro).__name__}"
        ) from None

    return resposta.status_code


def publicar(conteudo: bytes, config: Config, http) -> bool:
    """Publica `conteudo` como `indices.json` no branch `main`. Devolve se deu certo.

    Lê o `sha` atual, envia o `PUT` e, se a resposta for 409 (outra escrita
    entrou no meio), lê o `sha` de novo e tenta **uma** vez. Duas execuções
    simultâneas não podem virar laço de retentativa, então o segundo conflito
    desiste.

    Nunca levanta exceção: qualquer falha é registrada e devolve `False`.
    """
    try:
        sha = _ler_sha(config, http)
        status = _enviar(conteudo, config, http, sha)

        if status == 409:
            _log.warning(
                "publicação de %s: conflito (409), relendo o sha e tentando de novo",
                CAMINHO_NO_REPOSITORIO,
            )
            sha = _ler_sha(config, http)
            status = _enviar(conteudo, config, http, sha)

        if status not in STATUS_DE_SUCESSO:
            raise _FalhaDePublicacao(f"envio devolveu status {status}")
    except _FalhaDePublicacao as falha:
        _log.error("publicação de %s falhou: %s", CAMINHO_NO_REPOSITORIO, falha)
        return False

    _log.info("publicação de %s concluída (status %s)", CAMINHO_NO_REPOSITORIO, status)
    return True
