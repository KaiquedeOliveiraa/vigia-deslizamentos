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
- toda mensagem com índice informa que o VIGIA não emite alerta oficial
  (RN04), com o nome da classe junto do número (RN03);
- a cor nunca indica o nível sozinha: a barra colorida é reforço visual, e o
  ícone de formato diferente por faixa e o nome da classe por extenso vão
  sempre junto;
- HTML do Telegram (`parse_mode=HTML`): todo texto variável passa por
  `html.escape`.
"""

from __future__ import annotations

import html
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.bot.inscricao import OPCAO_TODOS
from app.bot.regra_aviso import Aviso
from app.classificacao.classes import (
    LIMIAR_ALERTA,
    classe,
    faixas_das_classes,
    nome_classe,
)
from app.modelos.banco import IndiceAtual

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")

RESSALVA_RN04 = (
    "O VIGIA é um sistema acadêmico e não emite alerta oficial: "
    "em caso de emergência, procure a Defesa Civil."
)

#: Versão curta da RN04, no rodapé das mensagens em HTML.
RESSALVA_CURTA = "<i>Sistema acadêmico, não emite alerta oficial.</i>"

#: Cor fixa de cada posição da barra, da classe 1 à 7. Único lugar das cores.
CORES_DA_BARRA = ("🟩", "🟩", "🟩", "🟨", "🟧", "🟥", "🟪")
VAZIO_DA_BARRA = "⬜"

#: Ícone e título de cada classe. O ícone muda de **formato** entre as faixas
#: (ℹ️, ⚠️, 🚨), para que o nível não dependa só de cor.
_ICONE_E_TITULO_POR_CLASSE = {
    1: ("ℹ️", "{nome} — sem alerta"),
    2: ("ℹ️", "{nome} — sem alerta"),
    3: ("ℹ️", "{nome} — sem alerta"),
    4: ("⚠️", "ATENÇÃO — {nome}"),
    5: ("⚠️", "ALERTA — {nome}"),
    6: ("🚨", "ALERTA — {nome}"),
    7: ("🚨", "ALERTA MÁXIMO — {nome}"),
}

_ATENTO_AOS_SINAIS = (
    "Fique atento a sinais de movimento do terreno: rachaduras em paredes ou "
    "no chão, árvores e postes inclinados, portas e janelas emperrando."
)
_ACOMPANHE = "Acompanhe as atualizações da Defesa Civil."
_SAIA_DO_LOCAL = (
    "Se mora em encosta ou perto de barranco e notar rachaduras, árvores ou "
    "postes inclinados ou água barrenta saindo do terreno, saia do local e vá "
    "para um lugar seguro."
)
_SIGA_A_DEFESA_CIVIL = "Siga as orientações da Defesa Civil."

#: "O que fazer" de cada classe em alerta. Único lugar desses textos.
ORIENTACOES_POR_CLASSE = {
    4: (_ATENTO_AOS_SINAIS, _ACOMPANHE),
    5: (
        _ATENTO_AOS_SINAIS,
        _ACOMPANHE,
        "Se mora em encosta ou perto de barranco, combine com a família um "
        "plano para sair rapidamente.",
    ),
    6: (_SAIA_DO_LOCAL, _SIGA_A_DEFESA_CIVIL),
    7: (_SAIA_DO_LOCAL, _SIGA_A_DEFESA_CIVIL),
}

LINHA_EMERGENCIA = "• Emergência: Defesa Civil <b>199</b> · Bombeiros <b>193</b>"


def numero_br(valor: float) -> str:
    """Número com duas casas e vírgula decimal (RN05): `1.0512` -> `"1,05"`."""
    return f"{valor:.2f}".replace(".", ",")


def data_hora_brasilia(momento: datetime) -> str:
    """`datetime` aware -> `"dd/mm/aaaa HH:MM"` no fuso de Brasília."""
    return momento.astimezone(FUSO_BRASILIA).strftime("%d/%m/%Y %H:%M")


def hora_brasilia(momento: datetime) -> str:
    """`datetime` aware -> `"HH:MM"` no fuso de Brasília."""
    return momento.astimezone(FUSO_BRASILIA).strftime("%H:%M")


def data_br(dia: date) -> str:
    """`date` -> `"dd/mm/aaaa"`."""
    return dia.strftime("%d/%m/%Y")


def total_de_classes() -> int:
    return len(faixas_das_classes())


def sem_alerta(numero_classe: int) -> bool:
    """Classe abaixo do gatilho de notificação (RN02)."""
    return numero_classe < classe(LIMIAR_ALERTA)


def barra(numero_classe: int) -> str:
    """As `numero_classe` primeiras posições com a sua cor fixa, as demais
    vazias. Classe 4 -> `🟩🟩🟩🟨⬜⬜⬜`.
    """
    preenchidas = "".join(CORES_DA_BARRA[:numero_classe])
    return preenchidas + VAZIO_DA_BARRA * (len(CORES_DA_BARRA) - numero_classe)


def _icone_e_titulo(numero_classe: int, nome: str) -> tuple[str, str]:
    icone, modelo = _ICONE_E_TITULO_POR_CLASSE[numero_classe]
    return icone, modelo.format(nome=html.escape(nome))


def _linha_da_classe(numero_classe: int) -> str:
    return (
        f"<b>Risco {html.escape(nome_classe(numero_classe))}</b> · "
        f"classe {numero_classe} de {total_de_classes()}"
    )


def _linha_da_chuva(aviso: Aviso) -> str | None:
    partes = []
    if aviso.efr_mm is not None:
        partes.append(f"🌧 Chuva acumulada: {numero_br(aviso.efr_mm)} mm")
    if aviso.rtotal_mm is not None:
        partes.append(f"☔ Previsão 24 h: {numero_br(aviso.rtotal_mm)} mm")
    return " · ".join(partes) or None


def _linha_da_validade(aviso: Aviso) -> str | None:
    partes = []
    if aviso.dia_alvo is not None:
        partes.append(f"📅 Válido para {data_br(aviso.dia_alvo)}")
    if aviso.calculado_em is not None:
        partes.append(f"cálculo às {hora_brasilia(aviso.calculado_em)}")
    return " · ".join(partes) or None


def _texto_de_alerta(aviso: Aviso, site_url: str) -> str:
    icone, titulo = _icone_e_titulo(aviso.classe, aviso.nome)
    linhas = [
        f"{icone} <b>{titulo}</b>",
        _linha_da_classe(aviso.classe),
        barra(aviso.classe),
        "",
        f"📊 Índice: <b>{numero_br(aviso.indice)}</b>",
    ]
    for linha in (_linha_da_chuva(aviso), _linha_da_validade(aviso)):
        if linha is not None:
            linhas.append(linha)
    linhas.extend(["", "<b>O que fazer</b>"])
    linhas.extend(
        f"• {html.escape(orientacao)}"
        for orientacao in ORIENTACOES_POR_CLASSE[aviso.classe]
    )
    linhas.extend(
        [
            LINHA_EMERGENCIA,
            "",
            f"🗺 Ver no mapa: {html.escape(site_url)}",
            RESSALVA_CURTA,
        ]
    )
    return "\n".join(linhas)


def _texto_sem_alerta(aviso: Aviso) -> str:
    icone, titulo = _icone_e_titulo(aviso.classe, aviso.nome)
    linha_do_indice = f"📊 Índice: <b>{numero_br(aviso.indice)}</b>"
    if aviso.calculado_em is not None:
        data, hora = data_hora_brasilia(aviso.calculado_em).split(" ")
        linha_do_indice += f" · 📅 {data}, {hora}"
    return "\n".join(
        [
            f"{icone} <b>{titulo}</b>",
            _linha_da_classe(aviso.classe),
            barra(aviso.classe),
            linha_do_indice,
            "Condições normais para a chuva acumulada.",
        ]
    )


def texto_do_aviso(aviso: Aviso, site_url: str) -> str:
    """Mensagem de um município numa classe, em HTML do Telegram.

    Classes em alerta (4 a 7) levam índice, chuva, validade, "O que fazer",
    telefones de emergência, link do site e a ressalva da RN04. Classes abaixo
    do alerta (1 a 3), que só aparecem no `/simular`, levam o formato curto
    "sem alerta". Campo do cálculo ausente no `aviso` (`None`) tem a linha
    omitida: nada é inventado.
    """
    if sem_alerta(aviso.classe):
        return _texto_sem_alerta(aviso)
    return _texto_de_alerta(aviso, site_url)


TEXTO_OPCAO_DESCONHECIDA = (
    "Não reconheci essa opção. Use /start para ver a lista de municípios."
)

TEXTO_INSCRICOES_APAGADAS = (
    "Suas inscrições foram apagadas. Use /start quando quiser voltar."
)

TEXTO_SEM_INSCRICAO = (
    "Você ainda não tem municípios inscritos.\n\n"
    "Use /start para escolher os municípios que quer acompanhar."
)

CABECALHO_DO_STATUS = "<b>Situação dos seus municípios</b>"
SEPARADOR_DO_STATUS = "\n\n"


#: Botão que volta do teclado de uma região para o das regiões.
OPCAO_VOLTAR = "Voltar"


def rotulo_do_grupo(nome_micro: str) -> str:
    """Botão da região. "Região de" evita colidir com o município homônimo (Rio do Sul)."""
    return f"Região de {nome_micro}"


def opcao_todos_do_grupo(nome_micro: str) -> str:
    return f"Todos da {rotulo_do_grupo(nome_micro)}"


def texto_escolha_do_grupo(nome_micro: str) -> str:
    rotulo = html.escape(rotulo_do_grupo(nome_micro))
    return (
        f"Municípios da {rotulo}. Toque em um deles, em "
        f"\"{html.escape(opcao_todos_do_grupo(nome_micro))}\" ou em \"{OPCAO_VOLTAR}\"."
    )


def texto_boas_vindas_grupos() -> str:
    """`/start` sem município quando o teclado é por região."""
    return (
        "Olá! Escolha a sua região para ver os municípios, "
        f"ou toque em \"{OPCAO_TODOS}\" para acompanhar todos.\n\n"
        "Use /status para ver a situação e /parar para cancelar."
    )


def texto_boas_vindas(nome_sugerido: str | None) -> str:
    """Resposta do `/start`, em HTML. Com `nome_sugerido`, cita o município."""
    if nome_sugerido is None:
        return (
            "Olá! Escolha os municípios que quer acompanhar no VIGIA.\n\n"
            f"Toque em um município ou em \"{OPCAO_TODOS}\". "
            "Use /status para ver a situação e /parar para cancelar."
        )
    nome = html.escape(nome_sugerido)
    return (
        f"Olá! O link veio de {nome} — toque em \"{nome}\" "
        f"para se inscrever só nele, ou em \"{OPCAO_TODOS}\" "
        "para acompanhar todos.\n\n"
        "Use /status para ver a situação e /parar para cancelar."
    )


def texto_inscricao_confirmada(nomes: list[str]) -> str:
    """Confirmação da escolha no teclado, com a ressalva da RN04."""
    lista = ", ".join(html.escape(nome) for nome in nomes)
    return f"Pronto! Você vai receber avisos de: {lista}.\n\n{RESSALVA_RN04}"


def bloco_do_status(nome: str, atual: IndiceAtual | None) -> str:
    """Bloco de um município no `/status`."""
    if atual is None:
        return f"<b>{html.escape(nome)}</b>: ainda sem cálculo"
    icone, _ = _ICONE_E_TITULO_POR_CLASSE[atual.classe]
    return "\n".join(
        [
            f"{icone} <b>{html.escape(nome)}</b> · "
            f"Risco {html.escape(nome_classe(atual.classe))}",
            f"{barra(atual.classe)} classe {atual.classe} de {total_de_classes()} · "
            f"Índice <b>{numero_br(atual.indice)}</b>",
            f"📅 Válido para {data_br(atual.dia_alvo)} · "
            f"cálculo de {data_hora_brasilia(atual.calculado_em)}",
        ]
    )


def rodape_do_status(site_url: str) -> str:
    """Rodapé do `/status`: link do mapa e ressalva curta."""
    return f"🗺 Ver no mapa: {html.escape(site_url)}\n{RESSALVA_CURTA}"


def texto_do_status(
    situacoes: list[tuple[str, IndiceAtual | None]], site_url: str
) -> str:
    """Resposta do `/status`, em HTML: um bloco por município inscrito.

    `situacoes` é uma lista de `(nome do município, índice atual ou None)`, na
    ordem em que deve aparecer. Município sem nenhum cálculo gravado aparece
    como "ainda sem cálculo" em vez de ser omitido — quem se inscreveu precisa
    saber que o município está na lista e que a informação é que falta. O
    dia-alvo vai em cada bloco (RN11); o link e a ressalva da RN04, uma vez só,
    no fim.

    Sem nenhuma inscrição, devolve `TEXTO_SEM_INSCRICAO`, sem índice nenhum, caso
    em que a ressalva da RN04 não se aplica.
    """
    if not situacoes:
        return TEXTO_SEM_INSCRICAO

    blocos = [bloco_do_status(nome, atual) for nome, atual in situacoes]
    return SEPARADOR_DO_STATUS.join(
        [CABECALHO_DO_STATUS, *blocos, rodape_do_status(site_url)]
    )


#: Limite do Telegram, em unidades UTF-16 (emoji conta 2).
LIMITE_MENSAGEM_TELEGRAM = 4096


def _tamanho(texto: str) -> int:
    return len(texto.encode("utf-16-le")) // 2


def partes_do_status(
    situacoes: list[tuple[str, IndiceAtual | None]],
    site_url: str,
    limite: int = LIMITE_MENSAGEM_TELEGRAM,
) -> list[str]:
    """`texto_do_status` em mensagens de até `limite`, cortando só entre blocos.

    Conta o HTML bruto, o que superestima (as tags somem no Telegram), ou seja,
    é seguro. O cabeçalho vai na primeira parte e o rodapé na última.
    """
    if not situacoes:
        return [TEXTO_SEM_INSCRICAO]
    cabecalho = CABECALHO_DO_STATUS + SEPARADOR_DO_STATUS
    rodape = SEPARADOR_DO_STATUS + rodape_do_status(site_url)
    partes: list[str] = []
    atual, vazia = cabecalho, True
    for nome, situacao in situacoes:
        bloco = bloco_do_status(nome, situacao)
        if _tamanho(cabecalho + bloco + rodape) > limite:
            raise ValueError(f"bloco de {nome!r} sozinho passa do limite de {limite}")
        junto = atual + bloco if vazia else atual + SEPARADOR_DO_STATUS + bloco
        if not vazia and _tamanho(junto) + _tamanho(rodape) > limite:
            partes.append(atual)
            atual = bloco
        else:
            atual = junto
        vazia = False
    partes.append(atual + rodape)
    return partes
