"""Montagem do `indices.json` publicado para o site (contrato de dados).

Funções puras: `montar_indices` recebe o resultado do cálculo, a configuração
dos municípios, os históricos lidos do banco e o `gerado_em` — nada de rede,
banco, relógio ou `os.environ`. `serializar` transforma o dicionário em bytes
UTF-8, que é o que a publicação (`app.exportacao.publicar`) envia.

O site é o único consumidor deste arquivo, e o schema que ele usa está em
`docs/indices.schema.json`: qualquer campo novo entra lá antes de entrar aqui.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from app.calculo.agregacao import Resultado, ResultadoDia, ResultadoMunicipio
from app.config import Municipio
from app.modelos.banco import ItemHistorico

#: Versão do contrato (`docs/contratos-de-dados.md`). O site recusa um valor
#: desconhecido em vez de exibir dados parciais, então subir este número é
#: mudança combinada com o frontend.
SCHEMA_VERSION = 1


def _exigir_fuso(nome: str, momento: datetime) -> None:
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError(
            f"'{nome}' precisa ser um datetime com fuso (aware); recebido sem fuso"
        )


def _dia_em_json(dia: ResultadoDia) -> dict:
    return {
        "dia_alvo": dia.dia_alvo.isoformat(),
        "d": dia.d,
        "indice": dia.indice,
        "classe": dia.classe,
        "efr_mm": dia.efr_mm,
        "rtotal_mm": dia.rtotal_mm,
        "n_membros": dia.n_membros,
        "prob": {
            "pontuais": dia.prob.pontuais,
            "esparsos": dia.prob.esparsos,
            "generalizados": dia.prob.generalizados,
        },
    }


def _historico_em_json(itens: list[ItemHistorico]) -> list[dict]:
    return [
        {
            "dia_alvo": item.dia_alvo.isoformat(),
            "indice": item.indice,
            "classe": item.classe,
        }
        for item in itens
    ]


def _municipio_em_json(
    resultado_do_municipio: ResultadoMunicipio,
    municipio: Municipio,
    historico: list[ItemHistorico],
) -> dict:
    return {
        "ibge": municipio.ibge,
        "nome": municipio.nome,
        "limiar_mm": resultado_do_municipio.limiar_mm,
        "fonte_limiar": municipio.fonte_limiar,
        "mv_h": municipio.mv_h,
        "dias": [_dia_em_json(dia) for dia in resultado_do_municipio.dias],
        "historico": _historico_em_json(historico),
        "chuva_acum_mm": dict(resultado_do_municipio.chuva_acum_mm),
    }


def montar_indices(
    resultado: Resultado,
    municipios: list[Municipio],
    historicos: dict[str, list[ItemHistorico]],
    gerado_em: datetime,
) -> dict:
    """Monta o dicionário do `indices.json` a partir do resultado da execução.

    `limiar_mm` vem do resultado (o limiar que entrou na conta); `nome`,
    `fonte_limiar` e `mv_h` vêm da configuração. Um município no resultado sem
    entrada em `municipios` levanta `KeyError` com o código IBGE: seria um item
    incompleto publicado em silêncio.

    `historicos` é indexado por `ibge`; município sem histórico sai com lista
    vazia, que é o caso normal nas primeiras execuções. A ordem dos itens é a
    recebida do banco (do mais antigo para o mais recente, Tarefa 7) — este
    módulo não reordena nada.

    Levanta `ValueError` se `gerado_em` vier sem fuso.
    """
    _exigir_fuso("gerado_em", gerado_em)
    por_ibge = {municipio.ibge: municipio for municipio in municipios}

    itens = []
    for resultado_do_municipio in resultado.municipios:
        ibge = resultado_do_municipio.ibge
        if ibge not in por_ibge:
            raise KeyError(
                f"município '{ibge}' está no resultado mas não na configuração"
            )
        itens.append(
            _municipio_em_json(
                resultado_do_municipio, por_ibge[ibge], historicos.get(ibge, [])
            )
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "gerado_em": gerado_em.astimezone(timezone.utc).isoformat(),
        "dia_alvo_d0": resultado.dia_alvo_d0.isoformat(),
        "municipios_sem_dados": list(resultado.municipios_sem_dados),
        "municipios": itens,
    }


def serializar(dados: dict) -> bytes:
    """Serializa o dicionário em bytes UTF-8, prontos para publicação.

    `ensure_ascii=False` para os acentos saírem legíveis no arquivo versionado
    (José Boiteux, Presidente Getúlio) em vez de escapes `\\uXXXX`, e quebra de
    linha final para o diff do commit automático não marcar
    "no newline at end of file" em toda publicação.
    """
    return (json.dumps(dados, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
