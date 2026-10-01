"""Tipos que ligam a camada de coleta (Tarefa 5) à camada de cálculo (Tarefa 6).

Dataclasses imutáveis, sem lógica: a coleta as produz a partir das respostas
da Open-Meteo; o cálculo as consome para montar janelas de chuva efetiva
antecedente e de subíndice por rodada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Membro:
    """Um membro do ensemble: uma rodada de um modelo de previsão.

    `chuva` é uma série de chuva horária por ponto de cálculo do município,
    na mesma ordem dos pontos da configuração — essa ordem importa porque o
    cálculo usa "primeiro ponto da configuração" como critério de desempate.
    Cada série é um dicionário hora UTC (com fuso) -> chuva em mm.
    """

    modelo: str
    rodada: datetime
    chuva: list[dict[datetime, float]]


@dataclass(frozen=True)
class DadosMunicipio:
    """Dados coletados para um município numa execução do pipeline.

    `antecedente` é a chuva horária (observada, com lacunas completadas por
    previsão numérica) das horas até `agora_utc`, uma série por ponto, na
    mesma ordem dos pontos da configuração. `membros` é a lista de rodadas de
    ensemble que a coleta conseguiu obter de forma completa — um membro
    incompleto ou com rodada ausente já foi descartado antes de chegar aqui.
    """

    ibge: str
    antecedente: list[dict[datetime, float]]
    membros: list[Membro]
