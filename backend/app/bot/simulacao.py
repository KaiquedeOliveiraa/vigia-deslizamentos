"""Textos do `/simular`: a mensagem de aviso de cada classe de risco, sem chuva real.

Módulo puro: sem rede, sem banco, sem relógio. O texto de cada classe sai de
`texto_do_aviso`, a mesma função dos avisos reais — se o aviso mudar, a
simulação muda junto. O índice de cada classe vem de `faixas_das_classes`, nunca
de números escritos aqui.

A simulação só **mostra** mensagens: não decide aviso, não grava classe
notificada e não publica nada.
"""

from __future__ import annotations

import html

from app.bot.mensagens import texto_do_aviso
from app.bot.regra_aviso import Aviso
from app.classificacao.classes import faixas_das_classes
from app.config import Municipio

#: Primeira linha de toda mensagem da simulação (HTML do Telegram).
CABECALHO = "🧪 <b>SIMULAÇÃO</b>"

#: Pausa entre as mensagens, para chegarem na ordem e sem esbarrar no limite
#: de envio do Telegram. Os testes a zeram.
PAUSA_ENTRE_MENSAGENS_S = 1.0

#: Quanto a última faixa (aberta) recebe acima do seu corte.
_ACIMA_DO_ULTIMO_CORTE = 0.5


def indices_simulados() -> list[tuple[int, float]]:
    """`(classe, índice)` da menor para a maior classe: ponto médio de cada
    faixa e, na última (aberta), o último corte + 0,5.
    """
    return [
        (
            numero,
            inferior + _ACIMA_DO_ULTIMO_CORTE
            if superior is None
            else (inferior + superior) / 2,
        )
        for numero, inferior, superior in faixas_das_classes()
    ]


def municipio_pelo_nome(
    municipios: list[Municipio], palavras: list[str]
) -> Municipio | None:
    """O município cujo nome casa com `palavras` (sem diferenciar maiúsculas);
    sem palavras, o primeiro da configuração.
    """
    if not palavras:
        return municipios[0] if municipios else None
    procurado = " ".join(palavras).casefold()
    for municipio in municipios:
        if municipio.nome.casefold() == procurado:
            return municipio
    return None


def texto_municipio_invalido(municipios: list[Municipio], palavras: list[str]) -> str:
    """Resposta para um nome fora da configuração, com a lista dos válidos."""
    procurado = html.escape(" ".join(palavras))
    return (
        f"{CABECALHO}\nMunicípio \"{procurado}\" não encontrado.\n\n"
        "Municípios válidos:\n"
        + "\n".join(f"• {html.escape(municipio.nome)}" for municipio in municipios)
    )


def mensagens_da_simulacao(municipio: Municipio, site_url: str) -> list[str]:
    """Uma mensagem por classe, em ordem crescente, com o texto do aviso real.

    O `Aviso` não leva chuva, dia-alvo nem horário de cálculo: não há cálculo
    por trás da simulação, e o texto real omite essas linhas em vez de mostrar
    valores inventados.
    """
    mensagens = []
    for numero, indice in indices_simulados():
        aviso = Aviso(
            ibge=municipio.ibge,
            nome=municipio.nome,
            indice=indice,
            classe=numero,
            avisar=True,
            nova_classe=numero,
        )
        mensagens.append(f"{CABECALHO}\n{texto_do_aviso(aviso, site_url)}")
    return mensagens


def texto_de_fim(quantidade: int) -> str:
    return f"🧪 Fim da simulação: {quantidade} classes enviadas."
