"""Agregação do índice de risco por município e por dia-alvo (D0–D3).

Monta as janelas horárias de cada dia-alvo, combina os subíndices das rodadas
disponíveis pelo *time-lagged ensemble* ponderado e devolve o resultado que a
persistência e o exportador consomem. Função pura: sem rede, sem banco, sem
relógio (`agora_utc` entra por parâmetro), sem `os.environ`, sem leitura de
arquivo.

Convenção do rótulo horário (`docs/decisoes/ensemble.md` §2): o rótulo `T`
marca o **fim** da hora, isto é, cobre `[T−1h, T)`. Daí, para o dia-alvo `D`
(dia civil UTC):

- janela do EfR: 169 rótulos, `meia-noite(D) − t horas` para `t = 0..168` —
  do rótulo `D T00:00Z` (a hora que termina na meia-noite de `D`) até
  `(D−7)T00:00Z`;
- `Rtotal(D)`: os 24 rótulos `D T01:00Z` … `(D+1)T00:00Z`.

As duas janelas são **adjacentes**: o EfR termina no rótulo `D T00:00Z` e o
`Rtotal` começa no rótulo `D T01:00Z`. Nenhuma hora física é contada duas
vezes, nenhuma hora de `D` fica de fora.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from app.calculo.chuva_efetiva import efr
from app.calculo.indice import indice_ponderado, subindice
from app.classificacao.classes import classe
from app.classificacao.probabilidades import Probabilidades, probabilidades
from app.config import Municipio
from app.modelos.tipos import DadosMunicipio, Membro

HORAS_EFR = 169  # t = 0..168
HORAS_DIA = 24
DIAS_ALVO = 4  # D0, D1, D2 e D3
JANELAS_ACUMULADO_H = (24, 48, 72, 96)

#: Mínimo de membros com peso > 0 exigido em CADA dia-alvo
#: (`docs/decisoes/ensemble.md` §6): metade dos 6 membros possíveis
#: (3 modelos × 2 rodadas alcançáveis pela API pública). Tolera a perda de
#: um modelo inteiro, não a de dois. É parâmetro de metodologia, não de
#: implantação — por isso vive aqui, e não em `municipios.json` nem em
#: variável de ambiente (a RNF07 exige configuração para os parâmetros
#: *por município*).
N_MIN = 3

#: Atraso (h) em que o peso da rodada chega a zero (`ensemble.md` §5).
ATRASO_MAXIMO_H = 36

#: Rodadas com assimilação de dados pesam mais que as demais (`ensemble.md` §5).
HORAS_PRINCIPAIS = (0, 12)
HORAS_SECUNDARIAS = (6, 18)
MULTIPLICADOR_PRINCIPAL = 1.0
MULTIPLICADOR_SECUNDARIA = 0.8


class HoraAusenteError(Exception):
    """Falta uma hora da janela na série de chuva (identifica o rótulo faltante)."""


class AgregacaoInvalidaError(Exception):
    """Dados do município incompatíveis com a configuração (identifica o município)."""


class RodadaInvalidaError(Exception):
    """Rodada fora dos horários sinóticos (0/6/12/18 UTC) ou posterior a `agora_utc`."""


#: Falhas de domínio que `calcular` converte em "município sem dados", em vez
#: de deixar abortar a execução inteira: elas dizem respeito aos dados de **um**
#: município, e a Tarefa 11 exige que os outros sigam. É um conjunto nomeado de
#: propósito — `except Exception` esconderia defeito de programação.
ERROS_DE_DOMINIO = (AgregacaoInvalidaError, RodadaInvalidaError, HoraAusenteError)


def _exigir_fuso(nome: str, momento: datetime) -> None:
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError(
            f"'{nome}' precisa ser um datetime com fuso (aware); recebido sem fuso"
        )


def peso(rodada: datetime, agora_utc: datetime) -> float:
    """Peso da rodada no *time-lagged ensemble* (`docs/decisoes/ensemble.md` §5).

    `peso = max(0, 1 − atraso_h / 36) × multiplicador`, com multiplicador 1,0
    para as rodadas de 00/12 UTC (com assimilação de dados) e 0,8 para as de
    06/18 UTC. O decaimento é linear e chega a zero em 36 h de atraso — a
    partir daí (inclusive) o membro é descartado por completo, também da
    contagem de `n_membros`.

    Levanta `ValueError` se algum dos dois instantes vier sem fuso e
    `RodadaInvalidaError` se a rodada não estiver num horário sinótico ou for
    posterior a `agora_utc`.
    """
    _exigir_fuso("rodada", rodada)
    _exigir_fuso("agora_utc", agora_utc)

    hora_utc = rodada.astimezone(timezone.utc).hour
    if hora_utc in HORAS_PRINCIPAIS:
        multiplicador = MULTIPLICADOR_PRINCIPAL
    elif hora_utc in HORAS_SECUNDARIAS:
        multiplicador = MULTIPLICADOR_SECUNDARIA
    else:
        raise RodadaInvalidaError(
            f"rodada {rodada.isoformat()} não está num dos horários sinóticos "
            f"{sorted(HORAS_PRINCIPAIS + HORAS_SECUNDARIAS)} UTC"
        )

    atraso_h = (agora_utc - rodada).total_seconds() / 3600
    if atraso_h < 0:
        raise RodadaInvalidaError(
            f"rodada {rodada.isoformat()} é posterior a agora_utc {agora_utc.isoformat()}"
        )

    recencia = max(0.0, 1.0 - atraso_h / ATRASO_MAXIMO_H)
    return recencia * multiplicador


def _meia_noite_utc(dia: date) -> datetime:
    return datetime(dia.year, dia.month, dia.day, tzinfo=timezone.utc)


def rotulos_efr(dia_alvo: date) -> list[datetime]:
    """Os 169 rótulos da janela do EfR do dia-alvo, do mais recente ao mais antigo.

    O índice da lista é o próprio `t` da fórmula do EfR: índice 0 é o rótulo
    `dia_alvo T00:00Z` (t=0, sem decaimento) e índice 168 é
    `(dia_alvo − 7 dias) T00:00Z`.
    """
    meia_noite = _meia_noite_utc(dia_alvo)
    return [meia_noite - timedelta(hours=t) for t in range(HORAS_EFR)]


def rotulos_rtotal(dia_alvo: date) -> list[datetime]:
    """Os 24 rótulos que cobrem as 24 horas físicas do dia civil UTC do dia-alvo.

    Vão de `dia_alvo T01:00Z` até `(dia_alvo + 1 dia) T00:00Z` — adjacentes à
    janela do EfR, sem sobreposição.
    """
    meia_noite = _meia_noite_utc(dia_alvo)
    return [meia_noite + timedelta(hours=k) for k in range(1, HORAS_DIA + 1)]


def _valor(serie: dict[datetime, float], rotulo: datetime, janela: str) -> float:
    if rotulo not in serie:
        raise HoraAusenteError(
            f"janela {janela}: falta a hora {rotulo.isoformat()} na série de chuva"
        )
    return serie[rotulo]


def janela_efr(
    dia_alvo: date,
    antecedente: dict[datetime, float],
    previsao: dict[datetime, float],
    agora_utc: datetime,
) -> list[float]:
    """Monta a série de 169 valores que alimenta `efr()`, para um ponto.

    `antecedente` fornece as horas até `agora_utc` (inclusive) e `previsao` —
    a série do próprio membro do ensemble — as horas posteriores, porque as
    horas futuras da janela (caso de D1–D3) só existem na previsão daquele
    membro. O índice 0 é a hora mais recente (t=0), como `efr()` exige.

    Levanta `HoraAusenteError` se faltar qualquer uma das 169 horas.
    """
    return [
        _valor(antecedente if rotulo <= agora_utc else previsao, rotulo, "EfR")
        for rotulo in rotulos_efr(dia_alvo)
    ]


def somar_rtotal(dia_alvo: date, previsao: dict[datetime, float]) -> float:
    """Soma a chuva prevista pelo membro para as 24 horas do dia-alvo.

    Vem toda da série do membro: `Rtotal` é, por definição, o total previsto
    para o dia-alvo pelo respectivo modelo. Levanta `HoraAusenteError` se
    faltar qualquer uma das 24 horas.
    """
    return sum(
        _valor(previsao, rotulo, "Rtotal") for rotulo in rotulos_rtotal(dia_alvo)
    )


# --- agregação de um dia-alvo -------------------------------------------------


@dataclass(frozen=True)
class ResultadoDia:
    """Resultado de um dia-alvo — os campos do item de `dias` do contrato."""

    dia_alvo: date
    d: int
    indice: float
    classe: int
    efr_mm: float
    rtotal_mm: float
    n_membros: int
    prob: Probabilidades


@dataclass(frozen=True)
class _PontoEscolhido:
    """Subíndice de um membro e os valores do ponto que o produziu."""

    sub: float
    efr_mm: float
    rtotal_mm: float


def _validar_series(municipio: Municipio, dados: DadosMunicipio) -> None:
    """Exige uma série por ponto de cálculo, no antecedente e em cada membro.

    A ordem das séries é contrato (`app.modelos.tipos`): é por ela que o
    desempate "primeiro ponto da configuração" funciona.
    """
    quantidade_de_pontos = len(municipio.pontos)
    if len(dados.antecedente) != quantidade_de_pontos:
        raise AgregacaoInvalidaError(
            f"município '{municipio.ibge}': 'antecedente' tem "
            f"{len(dados.antecedente)} série(s) para {quantidade_de_pontos} ponto(s)"
        )
    for membro in dados.membros:
        if len(membro.chuva) != quantidade_de_pontos:
            raise AgregacaoInvalidaError(
                f"município '{municipio.ibge}': membro '{membro.modelo}' da rodada "
                f"{membro.rodada.isoformat()} tem {len(membro.chuva)} série(s) para "
                f"{quantidade_de_pontos} ponto(s)"
            )


def _ponto_de_maior_subindice(
    municipio: Municipio,
    dados: DadosMunicipio,
    membro: Membro,
    dia_alvo: date,
    agora_utc: datetime,
) -> _PontoEscolhido:
    """Subíndice do membro: o maior entre os pontos do município.

    Em caso de empate fica o **primeiro ponto da configuração**, porque `max`
    devolve o primeiro dos maiores. `efr_mm` e `rtotal_mm` são os do ponto
    escolhido — não o maior EfR nem a média entre os pontos.

    Levanta `HoraAusenteError` se faltar alguma hora das janelas deste membro.
    """
    por_ponto: list[_PontoEscolhido] = []
    for indice_ponto in range(len(municipio.pontos)):
        valores = janela_efr(
            dia_alvo,
            dados.antecedente[indice_ponto],
            membro.chuva[indice_ponto],
            agora_utc,
        )
        efr_ponto = efr(valores, municipio.mv_h)
        rtotal_ponto = somar_rtotal(dia_alvo, membro.chuva[indice_ponto])
        por_ponto.append(
            _PontoEscolhido(
                sub=subindice(efr_ponto, rtotal_ponto, municipio.limiar_mm),
                efr_mm=efr_ponto,
                rtotal_mm=rtotal_ponto,
            )
        )
    return max(por_ponto, key=lambda ponto: ponto.sub)


def resultado_dia(
    municipio: Municipio,
    dados: DadosMunicipio,
    dia_alvo: date,
    d: int,
    agora_utc: datetime,
) -> ResultadoDia | None:
    """Agrega o dia-alvo `dia_alvo` (distância `d` do D0) para um município.

    Entram no cálculo os membros com `peso > 0` cujas janelas do dia-alvo
    estejam completas; um membro sem as 24 horas do dia (ou sem alguma hora da
    janela do EfR) fica fora **só daquele dia** — `n_membros` é por dia-alvo.
    Membro com peso 0 (atraso ≥ 36 h) é removido por completo, inclusive da
    contagem (`docs/decisoes/ensemble.md` §5).

    Devolve `None` quando nenhum membro é utilizável: sem subíndice não há
    índice. A comparação com `N_MIN` é de `calcular`, que decide o município
    inteiro.
    """
    _exigir_fuso("agora_utc", agora_utc)
    _validar_series(municipio, dados)

    subs: list[float] = []
    pesos: list[float] = []
    efrs: list[float] = []
    rtotais: list[float] = []

    for membro in dados.membros:
        peso_do_membro = peso(membro.rodada, agora_utc)
        if peso_do_membro <= 0:
            continue
        try:
            escolhido = _ponto_de_maior_subindice(
                municipio, dados, membro, dia_alvo, agora_utc
            )
        except HoraAusenteError:
            continue
        subs.append(escolhido.sub)
        pesos.append(peso_do_membro)
        efrs.append(escolhido.efr_mm)
        rtotais.append(escolhido.rtotal_mm)

    if not subs:
        return None

    indice = indice_ponderado(subs, pesos)
    # `indice_ponderado` é a própria média ponderada: serve para o índice e,
    # com as mesmas listas de pesos, para o EfR e o Rtotal exportados.
    return ResultadoDia(
        dia_alvo=dia_alvo,
        d=d,
        indice=indice,
        classe=classe(indice),
        efr_mm=indice_ponderado(efrs, pesos),
        rtotal_mm=indice_ponderado(rtotais, pesos),
        n_membros=len(subs),
        prob=probabilidades(subs, pesos),
    )


# --- chuva acumulada ----------------------------------------------------------


def acumulados(
    antecedente: list[dict[datetime, float]], agora_utc: datetime
) -> dict[str, float]:
    """Chuva acumulada em 24, 48, 72 e 96 h até a última hora cheia `≤ agora_utc`.

    Só da série observada/antecedente, e no ponto de **maior valor em cada
    janela** — o ponto mais chuvoso nas últimas 24 h não é necessariamente o
    mais chuvoso nas últimas 96 h. As chaves são as do contrato
    (`chuva_acum_mm`): `"24h"`, `"48h"`, `"72h"` e `"96h"`.

    Levanta `HoraAusenteError` se faltar alguma hora de alguma das janelas.
    """
    _exigir_fuso("agora_utc", agora_utc)
    ultima_hora_cheia = agora_utc.astimezone(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    )

    acumulado_por_janela: dict[str, float] = {}
    for horas in JANELAS_ACUMULADO_H:
        janela = f"{horas}h"
        rotulos = [ultima_hora_cheia - timedelta(hours=k) for k in range(horas)]
        acumulado_por_janela[janela] = max(
            sum(_valor(serie_do_ponto, rotulo, janela) for rotulo in rotulos)
            for serie_do_ponto in antecedente
        )
    return acumulado_por_janela


# --- agregação do município ---------------------------------------------------


@dataclass(frozen=True)
class ResultadoMunicipio:
    """Resultado de um município: os quatro dias-alvo e a chuva acumulada.

    `limiar_mm` é o limiar que este cálculo usou. Viaja com o resultado porque
    a persistência (Tarefa 7) recebe só o `Resultado` e grava a coluna
    `indices.limiar_mm`, e porque é o valor que o `indices.json` precisa expor
    — tomar o limiar da configuração na hora de gravar permitiria registrar um
    limiar diferente do que entrou na conta.
    """

    ibge: str
    limiar_mm: float
    dias: tuple[ResultadoDia, ...]
    chuva_acum_mm: dict[str, float]


@dataclass(frozen=True)
class Resultado:
    """Resultado de uma execução do cálculo, para todos os municípios."""

    dia_alvo_d0: date
    municipios: list[ResultadoMunicipio]
    municipios_sem_dados: list[str]


def _dias_do_municipio(
    municipio: Municipio,
    dados_do_municipio: DadosMunicipio,
    dias_alvo: list[date],
    agora_utc: datetime,
) -> tuple[ResultadoDia, ...] | None:
    """Os quatro `ResultadoDia` do município, ou `None` se algum dia-alvo faltar.

    "Faltar" é ter menos de `N_MIN` membros utilizáveis: o contrato exige
    D0–D3 completos, não parciais, então um único dia-alvo abaixo do mínimo
    manda o município inteiro para `municipios_sem_dados`.
    """
    dias: list[ResultadoDia] = []
    for d, dia_alvo in enumerate(dias_alvo):
        dia = resultado_dia(municipio, dados_do_municipio, dia_alvo, d, agora_utc)
        if dia is None or dia.n_membros < N_MIN:
            return None
        dias.append(dia)
    return tuple(dias)


def calcular(
    municipios: list[Municipio],
    dados: dict[str, DadosMunicipio],
    agora_utc: datetime,
) -> Resultado:
    """Calcula o índice de risco de cada município para D0–D3.

    `D0` é a data **UTC** de `agora_utc` (o dia-alvo da metodologia é ancorado
    em UTC, não no horário de Brasília — limitação conhecida, registrada no
    README) e D1–D3 são os dias seguintes.

    Um município vai para `municipios_sem_dados` quando não há dados dele
    nesta execução, quando algum dos quatro dias-alvo fica com menos de
    `N_MIN` membros, ou quando o cálculo dele levanta uma das
    `ERROS_DE_DOMINIO` — a falha de um município não derruba os outros. As
    duas listas preservam a ordem da configuração.

    Função pura: `agora_utc` entra por parâmetro, nada é lido de rede, banco,
    relógio, ambiente ou arquivo.
    """
    _exigir_fuso("agora_utc", agora_utc)
    agora = agora_utc.astimezone(timezone.utc)
    dia_alvo_d0 = agora.date()
    dias_alvo = [dia_alvo_d0 + timedelta(days=d) for d in range(DIAS_ALVO)]

    com_dados: list[ResultadoMunicipio] = []
    sem_dados: list[str] = []

    for municipio in municipios:
        dados_do_municipio = dados.get(municipio.ibge)
        if dados_do_municipio is None:
            sem_dados.append(municipio.ibge)
            continue

        try:
            dias = _dias_do_municipio(municipio, dados_do_municipio, dias_alvo, agora)
            if dias is None:
                sem_dados.append(municipio.ibge)
                continue
            chuva_acum_mm = acumulados(dados_do_municipio.antecedente, agora)
        except ERROS_DE_DOMINIO:
            sem_dados.append(municipio.ibge)
            continue

        com_dados.append(
            ResultadoMunicipio(
                ibge=municipio.ibge,
                limiar_mm=municipio.limiar_mm,
                dias=dias,
                chuva_acum_mm=chuva_acum_mm,
            )
        )

    return Resultado(
        dia_alvo_d0=dia_alvo_d0,
        municipios=com_dados,
        municipios_sem_dados=sem_dados,
    )
