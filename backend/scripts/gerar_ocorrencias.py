"""Gera `frontend/public/data/ocorrencias.json` a partir do Atlas Digital de Desastres.

Roda sob demanda; o arquivo é versionado no repositório. A fonte é o CSV público
do Atlas (MIDR/Sedec, registros do S2iD, 1991–2025). Ficam só os eventos ligados
a chuva (`TIPOS`) dos municípios de `config/municipios.json`.

    python -m scripts.gerar_ocorrencias                 # baixa o CSV (~80 MB)
    python -m scripts.gerar_ocorrencias --csv atlas.csv # usa um CSV já baixado

**Atualizar:** quando o Atlas publicar uma versão nova, troque `URL_ATLAS` (a
versão está fixada no nome do arquivo) e rode de novo.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import requests

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
if str(RAIZ_BACKEND) not in sys.path:
    sys.path.insert(0, str(RAIZ_BACKEND))

from app.config import carregar_municipios  # noqa: E402 — depende do sys.path acima

URL_ATLAS = "https://atlasdigital.mdr.gov.br/arquivos/2026/BD_Atlas_1991_2025_v1.1_2026.08.06_Consolidado.csv"
CAMINHO_MUNICIPIOS = RAIZ_BACKEND / "config" / "municipios.json"
CAMINHO_SAIDA = RAIZ_BACKEND.parent / "frontend" / "public" / "data" / "ocorrencias.json"

TIPOS = {
    "Movimento de Massa": "Movimento de massa",
    "Enxurradas": "Enxurrada",
    "Inundações": "Inundação",
    "Alagamentos": "Alagamento",
    "Chuvas Intensas": "Chuva intensa",
}
STATUS = {"Reconhecido": "Reconhecido pela União", "Registro": "Registrado no S2iD"}
# coluna do Atlas, singular, plural
DANOS = (
    ("DH_MORTOS", "morto", "mortos"),
    ("DH_DESABRIGADOS", "desabrigado", "desabrigados"),
    ("DH_DESALOJADOS", "desalojado", "desalojados"),
    ("DM_Uni Habita Danificadas", "casa danificada", "casas danificadas"),
    ("DM_Uni Habita Destruidas", "casa destruída", "casas destruídas"),
)


def converter_data(texto: str) -> str | None:
    try:
        return datetime.strptime(texto.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _numero(texto: str | None) -> int:
    try:
        return int(float((texto or "").strip().replace(",", ".")))
    except ValueError:
        return 0


def resumo_danos(linha: dict) -> str:
    status = (linha.get("Status") or "").strip()
    partes = [STATUS.get(status, status)]
    for coluna, singular, plural in DANOS:
        n = _numero(linha.get(coluna))
        if n > 0:
            partes.append(f"{n} {singular if n == 1 else plural}")
    if len(partes) == 1:
        partes.append("sem danos humanos ou materiais registrados")
    return " · ".join(partes)


def ocorrencia_de(linha: dict) -> dict | None:
    tipo = TIPOS.get((linha.get("descricao_tipologia") or "").strip())
    data = converter_data(linha.get("Data_Evento") or "")
    if tipo is None or data is None:
        return None
    return {
        "ibge": linha["Cod_IBGE_Mun"].strip(),
        "data": data,
        "tipo": tipo,
        "descricao": resumo_danos(linha),
        "fonte": f"Atlas Digital de Desastres (MIDR/Sedec) · S2iD {linha.get('Protocolo_S2iD', '').strip()}",
    }


def gerar(linhas: Iterable[dict], ibges: set[str]) -> list[dict]:
    """Filtra, converte e ordena (data decrescente, ibge, protocolo)."""
    itens = []
    descartadas = 0
    for linha in linhas:
        if (linha.get("Cod_IBGE_Mun") or "").strip() not in ibges:
            continue
        if (linha.get("descricao_tipologia") or "").strip() not in TIPOS:
            continue
        item = ocorrencia_de(linha)
        if item is None:
            descartadas += 1
            continue
        itens.append((item, (linha.get("Protocolo_S2iD") or "").strip()))
    if descartadas:
        print(f"Aviso: {descartadas} registro(s) descartado(s) por data inválida.")
    # ordenações estáveis, da chave menos para a mais importante
    itens.sort(key=lambda p: p[1])
    itens.sort(key=lambda p: p[0]["ibge"])
    itens.sort(key=lambda p: p[0]["data"], reverse=True)
    return [item for item, _ in itens]


def _baixar(destino) -> None:
    with requests.get(URL_ATLAS, stream=True, timeout=120) as resposta:
        if resposta.status_code != 200:
            raise RuntimeError(f"Atlas respondeu HTTP {resposta.status_code}")
        for bloco in resposta.iter_content(1 << 20):
            destino.write(bloco)


def _gerar_de(caminho: Path, ibges: set[str]) -> list[dict]:
    with open(caminho, encoding="latin-1", newline="") as f:
        return gerar(csv.DictReader(f, delimiter=";"), ibges)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv", type=Path, help="CSV do Atlas já baixado")
    parser.add_argument("--saida", type=Path, default=CAMINHO_SAIDA)
    args = parser.parse_args(argv)

    ibges = {m.ibge for m in carregar_municipios(CAMINHO_MUNICIPIOS)}
    if args.csv:
        itens = _gerar_de(args.csv, ibges)
    else:
        with tempfile.TemporaryDirectory() as pasta:  # NamedTemporaryFile não reabre no Windows
            tmp = Path(pasta) / "atlas.csv"
            with open(tmp, "wb") as f:
                _baixar(f)
            itens = _gerar_de(tmp, ibges)

    args.saida.parent.mkdir(parents=True, exist_ok=True)
    with open(args.saida, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(itens, ensure_ascii=False, indent=2) + "\n")

    print(f"{len(itens)} ocorrências gravadas em {args.saida}")
    for rotulo, chave in (("tipo", "tipo"), ("município", "ibge")):
        print(f"Por {rotulo}:")
        for valor, n in sorted(Counter(i[chave] for i in itens).items()):
            print(f"  {valor}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
