"""Estações automáticas do INMET e comparação da chuva de 24 h.

Serve só para **conferência**: a diferença entre a chuva medida pela estação de
referência e a `chuva_acum_mm["24h"]` da execução vai para o log e **não** entra
no índice. Nada aqui pode interromper o pipeline.

Duas limitações vêm da Tarefa 0 (`docs/decisoes/ensemble.md` §8) e moldam este
módulo:

1. **A rota de chuva horária exige token** obtido por e-mail
   (`cadastro.act@inmet.gov.br`), confirmado por resposta real
   `"CHAVE INVÁLIDA!"`. Sem `INMET_TOKEN` no ambiente, a comparação é pulada com
   o motivo registrado — o `estacoes.json`, que não precisa de token, segue
   sendo gerado.
2. **Nenhuma estação fica dentro dos seis municípios**: a mais próxima operante
   está a ~61 km, e a resposta de `/estacoes/T` não traz código IBGE nenhum. A
   associação é, portanto, por **proximidade** do centroide, dentro de um raio de
   corte — a estação é de *referência regional*, não "do município". É por isso
   que `Estacao` carrega `distancia_km` e que o JSON a publica: sem esse número,
   uma estação a 61 km passaria por estação local na tela.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from app.calculo.agregacao import Resultado
from app.config import Config, Municipio

URL_ESTACOES = "https://apitempo.inmet.gov.br/estacoes/T"
URL_CHUVA_COM_TOKEN = (
    "https://apitempo.inmet.gov.br/token/estacao/{inicio}/{fim}/{codigo}/{token}"
)

TIMEOUT_S = 30

#: Raio máximo entre o centroide do município e a estação de referência.
#: Generoso de propósito: com um raio que exigisse a estação *dentro* do
#: município, os seis ficariam sem comparação nenhuma (`ensemble.md` §8
#: recomenda 80–100 km). Quem lê o número vê a distância real no campo
#: `distancia_km`.
RAIO_DE_CORTE_KM = 100.0

SITUACAO_OPERANTE = "Operante"
TIPO_AUTOMATICA = "Automatica"

CAMINHO_ESTACOES = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "frontend"
    / "public"
    / "data"
    / "estacoes.json"
)

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Estacao:
    """Uma estação automática do INMET e o município que ela serve de referência.

    `ibge` é o município **mais próximo** dentro do raio de corte, não
    necessariamente aquele onde a estação fica; `distancia_km` diz o quanto.
    """

    codigo: str
    nome: str
    ibge: str
    lat: float
    lon: float
    distancia_km: float


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em km pela fórmula de haversine (`R = 6371 km`).

    Haversine, e não `hypot(Δlat, Δlon) × 111`: a aproximação ingênua não corrige
    a longitude pelo cosseno da latitude e erra ~10% a -27° de latitude, o que já
    trocou a ordem de duas estações na Tarefa 0.
    """
    raio_da_terra = 6371.0
    fi1, fi2 = math.radians(lat1), math.radians(lat2)
    delta_fi = fi2 - fi1
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_fi / 2) ** 2
        + math.cos(fi1) * math.cos(fi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * raio_da_terra * math.asin(math.sqrt(a))


def _centroide(municipio: Municipio) -> tuple[float, float]:
    """O primeiro ponto da configuração — por contrato, o centroide do município."""
    primeiro = municipio.pontos[0]
    return primeiro.lat, primeiro.lon


def associar_estacoes(
    brutas: list[dict[str, Any]],
    municipios: list[Municipio],
    raio_km: float = RAIO_DE_CORTE_KM,
) -> list[Estacao]:
    """Converte a resposta de `/estacoes/T` em `Estacao`, uma por estação útil.

    Entram só as estações **automáticas** e **operantes** cujo município mais
    próximo esteja dentro de `raio_km`. Estação em pane é descartada porque a
    comparação apontaria para quem não mede nada — foi o caso de Indaial, a mais
    próxima de todas (`ensemble.md` §8).
    """
    estacoes: list[Estacao] = []

    for bruta in brutas:
        if bruta.get("CD_SITUACAO") != SITUACAO_OPERANTE:
            continue
        if bruta.get("TP_ESTACAO") != TIPO_AUTOMATICA:
            continue
        try:
            lat = float(bruta["VL_LATITUDE"])
            lon = float(bruta["VL_LONGITUDE"])
        except (KeyError, TypeError, ValueError):
            _log.warning(
                "estação '%s' sem coordenada utilizável: descartada",
                bruta.get("CD_ESTACAO"),
            )
            continue

        candidatos = [
            (distancia_km(lat, lon, *_centroide(municipio)), municipio)
            for municipio in municipios
        ]
        distancia, mais_proximo = min(candidatos, key=lambda par: par[0])
        if distancia > raio_km:
            continue

        estacoes.append(
            Estacao(
                codigo=bruta["CD_ESTACAO"],
                nome=bruta["DC_NOME"],
                ibge=mais_proximo.ibge,
                lat=lat,
                lon=lon,
                distancia_km=round(distancia, 1),
            )
        )

    return estacoes


def estacao_em_json(estacao: Estacao) -> dict[str, Any]:
    """A estação no formato do `estacoes.json` (contrato + `distancia_km`)."""
    return {
        "codigo": estacao.codigo,
        "nome": estacao.nome,
        "ibge": estacao.ibge,
        "lat": estacao.lat,
        "lon": estacao.lon,
        "distancia_km": estacao.distancia_km,
    }


def carregar_estacoes(caminho: str | Path = CAMINHO_ESTACOES) -> list[Estacao]:
    """Lê o `estacoes.json` gerado pelo script. Arquivo ausente -> lista vazia.

    Ausência não é erro: o arquivo é gerado uma vez por script, e sem ele a única
    consequência é não haver comparação com o INMET.
    """
    import json

    caminho = Path(caminho)
    if not caminho.exists():
        return []

    try:
        itens = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        _log.warning("não foi possível ler %s: %s", caminho, erro)
        return []

    return [
        Estacao(
            codigo=item["codigo"],
            nome=item["nome"],
            ibge=item["ibge"],
            lat=item["lat"],
            lon=item["lon"],
            distancia_km=item.get("distancia_km", float("nan")),
        )
        for item in itens
    ]


def buscar_estacoes_automaticas(http) -> list[dict[str, Any]]:
    """Busca a lista bruta de estações automáticas (não exige token)."""
    resposta = http.get(URL_ESTACOES, timeout=TIMEOUT_S)
    resposta.raise_for_status()
    return resposta.json()


def _somar_chuva(registros: list[dict[str, Any]]) -> float | None:
    """Soma o campo `CHUVA` dos registros, ignorando os sem valor.

    Devolve `None` quando nenhum registro tem valor: "sem medição" é diferente de
    "mediu zero", e tratar os dois como 0,0 inventaria uma comparação.
    """
    valores = []
    for registro in registros:
        bruto = registro.get("CHUVA")
        if bruto is None or bruto == "":
            continue
        try:
            valores.append(float(bruto))
        except (TypeError, ValueError):
            continue

    return sum(valores) if valores else None


def chuva_24h(http, codigo: str, fim_utc: datetime, token: str) -> float | None:
    """Chuva medida pela estação nas 24 h que terminam em `fim_utc`.

    Devolve `None` em qualquer situação em que não haja número confiável: 204 sem
    corpo (o que a API devolveu em toda combinação testada na Tarefa 0), corpo
    que não é lista (`"CHAVE INVÁLIDA!"`), nenhum registro com valor, ou falha de
    rede. Nunca levanta, e o token nunca entra em mensagem de log.
    """
    inicio = (fim_utc - timedelta(hours=24)).date().isoformat()
    fim = fim_utc.date().isoformat()
    url = URL_CHUVA_COM_TOKEN.format(
        inicio=inicio, fim=fim, codigo=codigo, token=token
    )

    try:
        resposta = http.get(url, timeout=TIMEOUT_S)
        resposta.raise_for_status()
        if resposta.status_code == 204:
            return None
        corpo = resposta.json()
    except requests.exceptions.RequestException as erro:
        _log.warning(
            "INMET: falha ao buscar a chuva da estação '%s': %s",
            codigo,
            type(erro).__name__,
        )
        return None
    except ValueError:
        _log.warning("INMET: resposta da estação '%s' não é JSON", codigo)
        return None

    if not isinstance(corpo, list):
        _log.warning(
            "INMET: resposta da estação '%s' não é uma lista de registros "
            "(token ausente ou inválido?)",
            codigo,
        )
        return None

    inicio_da_janela = fim_utc - timedelta(hours=23)
    na_janela = [
        registro
        for registro in corpo
        if (momento := _momento_do_registro(registro)) is not None
        and inicio_da_janela <= momento <= fim_utc
    ]
    return _somar_chuva(na_janela)


def _momento_do_registro(registro: dict[str, Any]) -> datetime | None:
    """`DT_MEDICAO` + `HR_MEDICAO` -> `datetime` UTC, ou `None` se ilegível.

    Os horários da API são em UTC (`ensemble.md` §8).
    """
    data = registro.get("DT_MEDICAO")
    hora = registro.get("HR_MEDICAO")
    if not data or hora is None:
        return None
    try:
        texto_hora = str(hora).zfill(4)
        return datetime.strptime(f"{data} {texto_hora}", "%Y-%m-%d %H%M").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def registrar_comparacao_24h(
    resultado: Resultado,
    agora_utc: datetime,
    http,
    config: Config,
    estacoes: list[Estacao] | None = None,
) -> None:
    """Registra no log, por município, a diferença entre medido e calculado.

    Não devolve nada e **não levanta**: é conferência, e o pipeline não pode
    cair por causa dela. Sem token do INMET ou sem estação de referência, só
    registra o motivo e volta.
    """
    try:
        estacoes = carregar_estacoes() if estacoes is None else estacoes
        if not estacoes:
            return

        if not config.inmet_token:
            _log.info(
                "comparação com o INMET pulada: INMET_TOKEN não configurado "
                "(a rota de chuva horária exige token — ensemble.md §8)"
            )
            return

        por_ibge: dict[str, Estacao] = {}
        for estacao in estacoes:
            atual = por_ibge.get(estacao.ibge)
            if atual is None or estacao.distancia_km < atual.distancia_km:
                por_ibge[estacao.ibge] = estacao

        for item in resultado.municipios:
            estacao = por_ibge.get(item.ibge)
            if estacao is None:
                continue

            calculado = item.chuva_acum_mm.get("24h")
            medido = chuva_24h(http, estacao.codigo, agora_utc, config.inmet_token)
            if medido is None:
                _log.info(
                    "comparação INMET do município '%s': estação '%s' sem medição "
                    "na janela de 24 h (calculado: %.1f mm)",
                    item.ibge,
                    estacao.codigo,
                    calculado if calculado is not None else float("nan"),
                )
                continue

            _log.info(
                "comparação INMET do município '%s': estação '%s' a %.1f km mediu "
                "%.1f mm em 24 h contra %.1f mm calculados — diferença de %.1f mm "
                "(apenas conferência, não altera o índice)",
                item.ibge,
                estacao.codigo,
                estacao.distancia_km,
                medido,
                calculado,
                medido - calculado,
            )
    except Exception:  # noqa: BLE001 — conferência não derruba o pipeline
        _log.exception("comparação com o INMET falhou; a execução segue")
