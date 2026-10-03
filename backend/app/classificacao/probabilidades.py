"""Probabilidades complementares (pontuais, esparsos, generalizados).

Percentual, ponderado pelo peso de cada rodada, dos subíndices que superam
estritamente 1,0, 1,8 e 2,6 — informação secundária ao índice de risco,
conforme a metodologia GeoRisk. Função pura: sem rede, sem banco, sem
relógio.
"""

from __future__ import annotations

from dataclasses import dataclass

LIMIAR_PONTUAIS = 1.0
LIMIAR_ESPARSOS = 1.8
LIMIAR_GENERALIZADOS = 2.6


class ProbabilidadesInvalidasError(Exception):
    """Lista de subíndices/pesos vazia, de tamanhos diferentes ou com soma de pesos zero."""


@dataclass(frozen=True)
class Probabilidades:
    """Probabilidades complementares associadas a um índice de risco."""

    pontuais: float
    esparsos: float
    generalizados: float


def _validar_subs_e_pesos(subs: list[float], pesos: list[float]) -> None:
    if len(subs) == 0:
        raise ProbabilidadesInvalidasError("probabilidades: lista de subíndices vazia")

    if len(subs) != len(pesos):
        raise ProbabilidadesInvalidasError(
            f"probabilidades: tamanhos diferentes entre subíndices ({len(subs)}) "
            f"e pesos ({len(pesos)})"
        )

    if sum(pesos) == 0:
        raise ProbabilidadesInvalidasError("probabilidades: soma dos pesos é zero")


def _fracao_do_peso_acima_do_limiar(
    subs: list[float], pesos: list[float], limiar: float
) -> float:
    soma_pesos = sum(pesos)
    peso_acima = sum(
        peso for sub, peso in zip(subs, pesos, strict=True) if sub > limiar
    )
    return peso_acima / soma_pesos


def probabilidades(subs: list[float], pesos: list[float]) -> Probabilidades:
    """Calcula a fração do peso dos subíndices que supera, estritamente, cada
    limiar de magnitude de evento. Um valor igual ao limite não conta.

    Levanta `ProbabilidadesInvalidasError` se `subs` estiver vazia, se `subs`
    e `pesos` tiverem tamanhos diferentes, ou se a soma dos pesos for zero —
    mesma validação de `indice_ponderado` (`app.calculo.indice`).
    """
    _validar_subs_e_pesos(subs, pesos)

    return Probabilidades(
        pontuais=_fracao_do_peso_acima_do_limiar(subs, pesos, LIMIAR_PONTUAIS),
        esparsos=_fracao_do_peso_acima_do_limiar(subs, pesos, LIMIAR_ESPARSOS),
        generalizados=_fracao_do_peso_acima_do_limiar(subs, pesos, LIMIAR_GENERALIZADOS),
    )
