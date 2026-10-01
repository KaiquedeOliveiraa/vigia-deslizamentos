"""Classes de risco e gatilho de alerta, conforme a metodologia GeoRisk.

As faixas são semiabertas `[limite_inferior, limite_superior)`, sem
arredondamento. O corte entre "moderado" (4) e "alto" (5) é o único em 1,80
adotado pelo VIGIA — não há sobreposição com 1,60, diferente do manual
técnico original. Funções puras: sem rede, sem banco, sem relógio.
"""

from __future__ import annotations

#: Limite inferior (incluído) de cada classe, da mais alta para a mais baixa.
_LIMITES_INFERIORES_POR_CLASSE = (
    (7, 3.40),
    (6, 2.60),
    (5, 1.80),
    (4, 1.00),
    (3, 0.70),
    (2, 0.40),
)

CLASSE_EXTREMAMENTE_BAIXO = 1

LIMIAR_ALERTA = 1.00


def classe(indice: float) -> int:
    """Enquadra o índice de risco numa classe de 1 (extremamente baixo) a 7
    (extremamente alto), por faixas semiabertas `[a, b)`.
    """
    for numero_classe, limite_inferior in _LIMITES_INFERIORES_POR_CLASSE:
        if indice >= limite_inferior:
            return numero_classe
    return CLASSE_EXTREMAMENTE_BAIXO


def em_alerta(indice: float) -> bool:
    """Indica se o índice atinge o gatilho de notificação (classe moderado
    ou superior), isto é, índice maior ou igual a 1,00 (RN02).
    """
    return indice >= LIMIAR_ALERTA
