"""Regra de repetição do aviso do bot (RN08) e a forma da decisão.

Função pura: recebe a última classe notificada do município e o índice do dia
corrente (D0), devolve se deve avisar e qual passa a ser a última classe
notificada. Sem rede, sem banco, sem relógio — quem lê e grava a última classe
é `app.modelos.banco` (Tarefa 7), quem envia é `app.bot.avisos` (Tarefa 10).

Só o D0 entra na decisão: os dias-alvo D1–D3 são previsão e, por RN06, valor
estimado — nenhum deles dispara aviso, por alto que seja o índice.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.classificacao.classes import classe, em_alerta


@dataclass(frozen=True)
class Aviso:
    """A decisão de aviso de um município, com o que a mensagem precisa dizer.

    Produzido pelo pipeline (Tarefa 11) a partir de `decidir`, consumido por
    `app.bot.avisos` (Tarefa 10): `avisar` diz se há mensagem a enviar e
    `nova_classe` é o valor a gravar em `notificacoes` **depois** de o envio
    dar certo. `indice` e `classe` são os do D0 — os que a mensagem exibe.
    """

    ibge: str
    nome: str
    indice: float | None
    classe: int | None
    avisar: bool
    nova_classe: int | None


def decidir(
    ultima_classe: int | None, indice_d0: float | None
) -> tuple[bool, int | None]:
    """Decide se o município gera aviso e qual é a nova última classe notificada.

    - Sem índice (`None`: município sem dados nesta execução) nada é avisado e
      a última classe é **mantida** — uma falha de coleta não apaga o estado da
      regra nem gera aviso repetido na execução seguinte.
    - Índice fora de alerta (< 1,00, RN02) não avisa e **zera** a última classe,
      para que uma volta ao alerta depois disso avise de novo.
    - Em alerta, avisa quando não havia classe anterior ou quando a classe
      **subiu**. Permanecer na mesma classe não repete o aviso (RN08); descer
      de classe sem sair do alerta também não avisa, e a última classe
      notificada continua a mais alta já avisada — do contrário, oscilar entre
      duas classes mandaria uma mensagem a cada execução.
    """
    if indice_d0 is None:
        return False, ultima_classe

    if not em_alerta(indice_d0):
        return False, None

    classe_atual = classe(indice_d0)
    if ultima_classe is None or classe_atual > ultima_classe:
        return True, classe_atual

    return False, ultima_classe
