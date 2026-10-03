"""Gera `frontend/public/data/estacoes.json` a partir da lista do INMET.

Roda uma vez (e de novo quando a rede de estações mudar), não a cada execução
do pipeline: o arquivo é versionado no repositório, como os outros dados de
apoio do site.

    python -m scripts.gerar_estacoes            # grava no caminho do contrato
    python -m scripts.gerar_estacoes --saida /tmp/estacoes.json
    python -m scripts.gerar_estacoes --raio-km 60

Não exige token: a rota `/estacoes/T` é aberta. O que exige token é a chuva
horária, usada só na comparação de conferência (`app/coleta/inmet.py`).

**Por que o campo se chama `ibge_referencia`:** nenhuma estação automática do
INMET fica dentro dos seis municípios do projeto — a mais próxima operante está
a ~30 km — e a resposta do INMET não traz código IBGE nenhum
(`docs/decisoes/ensemble.md` §8). O código gravado é o do município **mais
próximo** dentro do raio de corte, e `distancia_km` registra a distância real. É
uma estação de referência regional, que é o papel que o README atribui ao INMET
("comparação e validação na região"), não uma estação local.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
if str(RAIZ_BACKEND) not in sys.path:
    sys.path.insert(0, str(RAIZ_BACKEND))

from app.coleta.inmet import (  # noqa: E402 — depende do sys.path acima
    CAMINHO_ESTACOES,
    RAIO_DE_CORTE_KM,
    associar_estacoes,
    buscar_estacoes_automaticas,
    estacao_em_json,
)
from app.config import carregar_municipios  # noqa: E402

CAMINHO_MUNICIPIOS = RAIZ_BACKEND / "config" / "municipios.json"


def gerar(brutas: list[dict], municipios, raio_km: float) -> list[dict]:
    """Converte a resposta do INMET nos itens do `estacoes.json`, ordenados."""
    estacoes = associar_estacoes(brutas, municipios, raio_km=raio_km)
    estacoes.sort(
        key=lambda estacao: (estacao.ibge_referencia, estacao.distancia_km)
    )
    return [estacao_em_json(estacao) for estacao in estacoes]


def gravar(itens: list[dict], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(itens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        prog="python -m scripts.gerar_estacoes", description=__doc__
    )
    analisador.add_argument("--saida", default=str(CAMINHO_ESTACOES))
    analisador.add_argument("--raio-km", type=float, default=RAIO_DE_CORTE_KM)
    argumentos = analisador.parse_args(argv)

    municipios = carregar_municipios(CAMINHO_MUNICIPIOS)
    with requests.Session() as http:
        brutas = buscar_estacoes_automaticas(http)

    itens = gerar(brutas, municipios, argumentos.raio_km)
    gravar(itens, Path(argumentos.saida))

    print(f"{len(itens)} estação(ões) gravada(s) em {argumentos.saida}")
    for item in itens:
        print(
            f"  {item['codigo']} {item['nome']} -> {item['ibge_referencia']} "
            f"({item['distancia_km']} km)"
        )
    if not itens:
        print(
            "Nenhuma estação dentro do raio: a comparação com o INMET ficará "
            "desabilitada (ver docs/decisoes/ensemble.md §8)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
