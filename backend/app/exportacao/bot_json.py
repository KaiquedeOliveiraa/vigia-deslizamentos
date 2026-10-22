"""Montagem do `bot.json`: os textos prontos que o Worker do Telegram devolve.

Função pura: recebe os municípios, o índice atual de cada um, a URL do site e o
`gerado_em` — nada de rede, banco, relógio ou `os.environ`. Todo texto sai das
mesmas funções que o bot em Python usa (`app.bot.mensagens` e
`app.bot.simulacao`), de modo que o Worker nunca escreve texto do domínio.

O `/status` é montado pelo Worker a partir de pedaços: `cabecalho`, os `blocos`
dos municípios inscritos unidos por `separador`, e `rodape`. A junção reproduz
`texto_do_status` byte a byte.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.bot.inscricao import OPCAO_TODOS
from app.bot.mensagens import (
    OPCAO_VOLTAR,
    CABECALHO_DO_STATUS,
    SEPARADOR_DO_STATUS,
    TEXTO_INSCRICOES_APAGADAS,
    TEXTO_OPCAO_DESCONHECIDA,
    TEXTO_SEM_INSCRICAO,
    bloco_do_status,
    opcao_todos_do_grupo,
    rodape_do_status,
    rotulo_do_grupo,
    texto_boas_vindas,
    texto_boas_vindas_grupos,
    texto_escolha_do_grupo,
    texto_inscricao_confirmada,
)
from app.bot.simulacao import (
    PAUSA_ENTRE_MENSAGENS_S,
    mensagens_da_simulacao,
    texto_de_fim,
    texto_municipio_invalido,
)
from app.config import Municipio
from app.modelos.banco import IndiceAtual

#: Versão do contrato lido pelo Worker. Subir este número é mudança combinada
#: com o Worker.
SCHEMA_VERSION_BOT_JSON = 1

_FORMATO_DATA_HORA = "%Y-%m-%dT%H:%M:%SZ"

#: Marcador que o Worker troca pelo texto digitado em `/simular`.
_MARCADOR_DA_ENTRADA = "{entrada}"


def _data_hora_utc(nome: str, momento: datetime) -> str:
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError(
            f"'{nome}' precisa ser um datetime com fuso (aware); recebido sem fuso"
        )
    return momento.astimezone(timezone.utc).strftime(_FORMATO_DATA_HORA)


def _simulacao_em_json(municipios: list[Municipio], site_url: str) -> dict:
    mensagens = {
        municipio.ibge: mensagens_da_simulacao(municipio, site_url)
        for municipio in municipios
    }
    por_municipio = len(mensagens[municipios[0].ibge]) if municipios else 0
    return {
        "mensagens": mensagens,
        "fim": texto_de_fim(por_municipio),
        "municipio_invalido": texto_municipio_invalido(
            municipios, [_MARCADOR_DA_ENTRADA]
        ),
        "pausa_s": PAUSA_ENTRE_MENSAGENS_S,
    }


def _grupos_em_json(municipios: list[Municipio]) -> list[dict] | None:
    """Um grupo por microrregião, na ordem do código; `None` se faltar microrregião."""
    if not municipios or any(m.microrregiao is None for m in municipios):
        return None
    codigos = sorted({m.microrregiao.codigo for m in municipios})
    grupos = []
    for codigo in codigos:
        membros = [m for m in municipios if m.microrregiao.codigo == codigo]
        nome = membros[0].microrregiao.nome
        grupos.append(
            {
                "nome": rotulo_do_grupo(nome),
                "municipios": [m.ibge for m in membros],
                "opcao_todos": opcao_todos_do_grupo(nome),
                "escolha": texto_escolha_do_grupo(nome),
                "confirmacao": texto_inscricao_confirmada([m.nome for m in membros]),
            }
        )
    return grupos


def montar_bot_json(
    municipios: list[Municipio],
    atuais: dict[str, IndiceAtual | None],
    site_url: str,
    simulacao: bool,
    gerado_em: datetime,
) -> dict:
    """Dicionário do `bot.json`. `gerado_em` sem fuso levanta `ValueError`.

    `atuais` tem de trazer uma entrada por município (o valor `None` significa
    "ainda sem cálculo"); a falta da chave levanta `KeyError` com o código IBGE.
    """
    gerado_em_texto = _data_hora_utc("gerado_em", gerado_em)
    nomes = [municipio.nome for municipio in municipios]

    dados = {
        "schema_version": SCHEMA_VERSION_BOT_JSON,
        "gerado_em": gerado_em_texto,
        "municipios": [
            {"ibge": municipio.ibge, "nome": municipio.nome}
            for municipio in municipios
        ],
        "textos": {
            "opcao_todos": OPCAO_TODOS,
            "boas_vindas": texto_boas_vindas(None),
            "boas_vindas_sugerido": {
                municipio.ibge: texto_boas_vindas(municipio.nome)
                for municipio in municipios
            },
            "inscricao_confirmada": {
                municipio.ibge: texto_inscricao_confirmada([municipio.nome])
                for municipio in municipios
            },
            "inscricao_confirmada_todos": texto_inscricao_confirmada(nomes),
            "opcao_desconhecida": TEXTO_OPCAO_DESCONHECIDA,
            "inscricoes_apagadas": TEXTO_INSCRICOES_APAGADAS,
        },
        "status": {
            "cabecalho": CABECALHO_DO_STATUS + SEPARADOR_DO_STATUS,
            "blocos": {
                municipio.ibge: bloco_do_status(
                    municipio.nome, atuais[municipio.ibge]
                )
                for municipio in municipios
            },
            "separador": SEPARADOR_DO_STATUS,
            "rodape": SEPARADOR_DO_STATUS + rodape_do_status(site_url),
            "sem_inscricao": TEXTO_SEM_INSCRICAO,
        },
        "simulacao": _simulacao_em_json(municipios, site_url) if simulacao else None,
    }
    grupos = _grupos_em_json(municipios)
    if grupos is not None:
        dados["grupos"] = grupos
        dados["textos"]["opcao_voltar"] = OPCAO_VOLTAR
        dados["textos"]["boas_vindas_grupos"] = texto_boas_vindas_grupos()
    return dados
