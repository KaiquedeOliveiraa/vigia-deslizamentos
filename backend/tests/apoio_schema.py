"""Apoio dos testes que validam JSON contra `docs/indices.schema.json`.

No vocabulário de formato do draft 2020-12, `format` é só anotação:
`jsonschema.validate()` sem `format_checker` explícito **não** rejeita uma
data-hora malformada. Daí `validador_estrito`, usado pelos testes do schema
(Tarefa 1) e pelos do exportador (Tarefa 9) — se cada um montasse o seu, a
validação de um poderia ficar mais fraca que a do outro sem ninguém notar.

O `FormatChecker` padrão só registra checador para `date` (stdlib); para
`date-time` não registra nada sem o pacote opcional `rfc3339-validator`, fora
da lista de dependências do projeto. Em vez de acrescentar a dependência,
registramos aqui um checador mínimo com `datetime.fromisoformat`, suficiente
para rejeitar valor obviamente malformado.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import jsonschema

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
CAMINHO_SCHEMA = RAIZ_BACKEND.parent / "docs" / "indices.schema.json"


def carregar_schema() -> dict:
    return json.loads(CAMINHO_SCHEMA.read_text(encoding="utf-8"))


def format_checker_com_date_time() -> jsonschema.FormatChecker:
    verificador = jsonschema.FormatChecker()

    @verificador.checks("date-time", raises=ValueError)
    def _verifica_date_time(valor):
        if not isinstance(valor, str):
            return True
        datetime.fromisoformat(valor)
        return True

    return verificador


def validador_estrito(schema: dict) -> jsonschema.Draft202012Validator:
    """Validator com verificação de formato (`date`, `date-time`) ativa."""
    return jsonschema.Draft202012Validator(
        schema, format_checker=format_checker_com_date_time()
    )
