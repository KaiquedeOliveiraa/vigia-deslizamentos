"""Textos que o bot envia. Módulo puro: sem rede, sem banco, sem relógio.

Tudo o que varia entra por parâmetro — inclusive a URL do site (que vem da
`Config`) e o `calculado_em` de cada município. Separar o texto do transporte é
o que permite verificar a RN04 e a RN05 em teste, sem Telegram nenhum.

Convenções de exibição:

- números com **vírgula** decimal e duas casas (RN05);
- data e hora no fuso de **Brasília** (`America/Sao_Paulo`), porque é o que o
  inscrito lê — o resto do sistema trabalha em UTC;
- o **dia-alvo** junto do índice (RN11), porque quando o município fica sem
  dados numa execução o índice exibido é o da execução anterior, e sem o
  dia-alvo o leitor não tem como saber a que dia ele se refere;
- todo texto de risco é **condicional** e informa que o VIGIA não emite alerta
  oficial (RN04), com o nome da classe junto do número (RN03).
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.bot.regra_aviso import Aviso
from app.classificacao.classes import nome_classe
from app.modelos.banco import IndiceAtual

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")

RESSALVA_RN04 = (
    "O VIGIA é um sistema acadêmico e não emite alerta oficial: "
    "em caso de emergência, procure a Defesa Civil."
)


def numero_br(valor: float) -> str:
    """Número com duas casas e vírgula decimal (RN05): `1.0512` -> `"1,05"`."""
    return f"{valor:.2f}".replace(".", ",")


def data_hora_brasilia(momento: datetime) -> str:
    """`datetime` aware -> `"dd/mm/aaaa HH:MM"` no fuso de Brasília."""
    return momento.astimezone(FUSO_BRASILIA).strftime("%d/%m/%Y %H:%M")


def data_br(dia: date) -> str:
    """`date` -> `"dd/mm/aaaa"`."""
    return dia.strftime("%d/%m/%Y")


def texto_do_aviso(aviso: Aviso, site_url: str) -> str:
    """Mensagem enviada quando um município entra em alerta ou sobe de classe.

    Traz município, índice (vírgula, duas casas), número e nome da classe e o
    link do site. A frase é condicional ("poderá") e termina na ressalva da
    RN04 — o aviso não afirma que vai ocorrer deslizamento, só que o índice
    atingiu a faixa.
    """
    return (
        f"⚠️ {aviso.nome} está com índice de risco {numero_br(aviso.indice)} "
        f"(classe {aviso.classe}, {nome_classe(aviso.classe)}).\n\n"
        f"O município poderá entrar em situação de risco de deslizamento nas "
        f"próximas horas. Acompanhe a situação em {site_url}\n\n"
        f"{RESSALVA_RN04}"
    )


def texto_do_status(
    situacoes: list[tuple[str, IndiceAtual | None]], site_url: str
) -> str:
    """Resposta do `/status`: a situação de cada município inscrito.

    `situacoes` é uma lista de `(nome do município, índice atual ou None)`, na
    ordem em que deve aparecer. Município sem nenhum cálculo gravado aparece
    como "sem dados" em vez de ser omitido — quem se inscreveu precisa saber
    que o município está na lista e que a informação é que falta.

    Sem nenhuma inscrição, o texto orienta a usar `/start` e não exibe índice
    nenhum, caso em que a ressalva da RN04 não se aplica.
    """
    if not situacoes:
        return (
            "Você ainda não tem municípios inscritos.\n\n"
            "Use /start para escolher os municípios que quer acompanhar."
        )

    linhas = [f"Situação dos seus municípios ({site_url}):", ""]
    for nome, atual in situacoes:
        if atual is None:
            linhas.append(f"• {nome}: sem dados")
            continue
        linhas.append(
            f"• {nome}: índice {numero_br(atual.indice)} "
            f"(classe {atual.classe}, {nome_classe(atual.classe)}) "
            f"para {data_br(atual.dia_alvo)} — "
            f"cálculo de {data_hora_brasilia(atual.calculado_em)}"
        )

    linhas.extend(["", RESSALVA_RN04])
    return "\n".join(linhas)
