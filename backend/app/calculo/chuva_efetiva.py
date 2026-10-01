"""Chuva efetiva antecedente (EfR), conforme a metodologia GeoRisk.

Calculada sobre as 168 horas (7 dias) anteriores ao dia-alvo, com decaimento
exponencial pelo parâmetro de meia-vida da água no solo (`MV`). Função pura:
sem rede, sem banco, sem relógio.
"""

from __future__ import annotations

TAMANHO_MAXIMO_SERIE = 169  # t = 0..168


class SerieInvalidaError(Exception):
    """Série de chuva horária com valor faltando ou com mais horas que o permitido."""


def efr(chuva_horaria: list[float], mv_h: float) -> float:
    """Calcula `EfR = Σ_{t=0}^{168} Rh_t · 0,5^(t/MV)`.

    `chuva_horaria[0]` é a chuva da hora mais recente (t=0); os índices
    seguintes avançam no tempo passado (t=1, t=2, ...). Aceita até 169
    valores (t = 0..168). Série vazia resulta em `EfR = 0`. Levanta
    `SerieInvalidaError` se houver valor `None` na série ou mais de 169
    valores — nunca um resultado silencioso.
    """
    if len(chuva_horaria) > TAMANHO_MAXIMO_SERIE:
        raise SerieInvalidaError(
            f"série de chuva horária com {len(chuva_horaria)} valores, "
            f"máximo permitido é {TAMANHO_MAXIMO_SERIE}"
        )

    for t, valor in enumerate(chuva_horaria):
        if valor is None:
            raise SerieInvalidaError(
                f"série de chuva horária com valor ausente (None) em t={t}"
            )

    return sum(valor * 0.5 ** (t / mv_h) for t, valor in enumerate(chuva_horaria))
