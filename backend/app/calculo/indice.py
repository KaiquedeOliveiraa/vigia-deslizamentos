"""Subíndice de risco e índice de risco ponderado, conforme a metodologia GeoRisk.

Funções puras: sem rede, sem banco, sem relógio.
"""

from __future__ import annotations


class IndicePonderadoInvalidoError(Exception):
    """Lista de subíndices/pesos vazia, de tamanhos diferentes ou com soma de pesos zero."""


def subindice(efr: float, rtotal: float, limiar: float) -> float:
    """Calcula `SubIR = (EfR + Rtotal) / Limiar` para uma rodada de previsão."""
    return (efr + rtotal) / limiar


def indice_ponderado(subs: list[float], pesos: list[float]) -> float:
    """Combina os subíndices por média ponderada: `Σ Wi·SubIRi / Σ Wi`.

    Levanta `IndicePonderadoInvalidoError` se `subs` estiver vazia, se `subs`
    e `pesos` tiverem tamanhos diferentes, ou se a soma dos pesos for zero.
    """
    if len(subs) == 0:
        raise IndicePonderadoInvalidoError("lista de subíndices vazia")

    if len(subs) != len(pesos):
        raise IndicePonderadoInvalidoError(
            f"tamanhos diferentes entre subíndices ({len(subs)}) e pesos ({len(pesos)})"
        )

    soma_pesos = sum(pesos)
    if soma_pesos == 0:
        raise IndicePonderadoInvalidoError("soma dos pesos é zero")

    soma_ponderada = sum(sub * peso for sub, peso in zip(subs, pesos))
    return soma_ponderada / soma_pesos
