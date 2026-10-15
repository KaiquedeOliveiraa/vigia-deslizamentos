"""Testes do `/simular`: pré-visualização das mensagens de cada classe de risco.

Sem rede e sem `.env`: a `Config` é montada à mão, o `Update` é um dublê que
guarda as respostas e a pausa entre mensagens é zerada.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging

import pytest
from telegram.constants import ParseMode
from telegram.ext import CommandHandler

from app.bot import bot as modulo_bot
from app.bot import simulacao
from app.bot.mensagens import texto_do_aviso
from app.bot.regra_aviso import Aviso
from app.classificacao.classes import classe, faixas_das_classes
from app.config import carregar_env
from app.modelos import banco

from tests.test_bot import (
    AGORA,
    CHAT,
    MUNICIPIOS,
    ContextoFalso,
    MensagemFalsa,
    UpdateFalso,
    config_de_teste,
)

PREFIXO = "🧪 <b>SIMULAÇÃO</b>"

AMBIENTE_MINIMO = {
    "TELEGRAM_TOKEN": "123:ABC",
    "GITHUB_TOKEN_DADOS": "ghp_x",
    "GITHUB_REPO": "dono/repo",
    "SITE_URL": "https://vigia.exemplo.org",
    "DB_PATH": ":memory:",
    "LOG_PATH": "vigia.log",
}


@pytest.fixture(autouse=True)
def sem_pausa(monkeypatch):
    monkeypatch.setattr(simulacao, "PAUSA_ENTRE_MENSAGENS_S", 0)


def comandos_registrados(aplicacao) -> set[str]:
    return {
        comando
        for handler in aplicacao.handlers[0]
        if isinstance(handler, CommandHandler)
        for comando in handler.commands
    }


def simular(conexao, args=None) -> MensagemFalsa:
    mensagem = MensagemFalsa("/simular")
    asyncio.run(
        modulo_bot.comando_simular(UpdateFalso(mensagem), ContextoFalso(conexao, args))
    )
    return mensagem


# --- ligar e desligar ---------------------------------------------------------


def test_config_sem_vigia_simulacao_fica_desligada():
    assert carregar_env(AMBIENTE_MINIMO).simulacao is False


@pytest.mark.parametrize("valor", ["0", "", "true", "sim", " 1"])
def test_config_so_liga_com_valor_exatamente_1(valor):
    ambiente = {**AMBIENTE_MINIMO, "VIGIA_SIMULACAO": valor}
    assert carregar_env(ambiente).simulacao is False


def test_config_com_vigia_simulacao_1_liga():
    ambiente = {**AMBIENTE_MINIMO, "VIGIA_SIMULACAO": "1"}
    assert carregar_env(ambiente).simulacao is True


def test_sem_simulacao_o_comando_nao_e_registrado(caplog):
    with caplog.at_level(logging.INFO, logger="app.bot.bot"):
        aplicacao = modulo_bot.construir_aplicacao(
            config_de_teste(), MUNICIPIOS, banco.abrir(":memory:"), relogio=lambda: AGORA
        )

    assert "simular" not in comandos_registrados(aplicacao)
    assert "simulação: desligada" in caplog.text


def test_com_simulacao_o_comando_e_registrado(caplog):
    config = dataclasses.replace(config_de_teste(), simulacao=True)

    with caplog.at_level(logging.INFO, logger="app.bot.bot"):
        aplicacao = modulo_bot.construir_aplicacao(
            config, MUNICIPIOS, banco.abrir(":memory:"), relogio=lambda: AGORA
        )

    assert comandos_registrados(aplicacao) == {"start", "status", "parar", "simular"}
    assert "simulação: comando /simular HABILITADO" in caplog.text


# --- índices escolhidos -------------------------------------------------------


def test_um_indice_por_classe_em_ordem_crescente():
    numeros = [numero for numero, _ in simulacao.indices_simulados()]
    assert numeros == sorted(numero for numero, _, _ in faixas_das_classes())


def test_cada_indice_cai_dentro_da_faixa_da_propria_classe():
    faixas = {numero: (inf, sup) for numero, inf, sup in faixas_das_classes()}
    for numero, indice in simulacao.indices_simulados():
        inferior, superior = faixas[numero]
        assert inferior <= indice
        assert superior is None or indice < superior
        assert classe(indice) == numero


def test_indice_e_ponto_medio_e_ultima_faixa_e_corte_mais_meio():
    faixas = faixas_das_classes()
    indices = dict(simulacao.indices_simulados())
    for numero, inferior, superior in faixas[:-1]:
        assert indices[numero] == pytest.approx((inferior + superior) / 2)
    ultimo_numero, ultimo_corte, _ = faixas[-1]
    assert indices[ultimo_numero] == pytest.approx(ultimo_corte + 0.5)


# --- o comando ----------------------------------------------------------------


def test_simular_envia_uma_mensagem_por_classe_e_a_de_fim():
    mensagem = simular(banco.abrir(":memory:"))

    n_classes = len(faixas_das_classes())
    assert len(mensagem.respostas) == n_classes + 1
    for texto in mensagem.respostas[:-1]:
        assert texto.startswith(PREFIXO + "\n")
    assert mensagem.respostas[-1] == f"🧪 Fim da simulação: {n_classes} classes enviadas."


def test_mensagens_seguem_ordem_crescente_e_usam_o_texto_do_aviso_real():
    mensagem = simular(banco.abrir(":memory:"))

    for texto, (numero, indice) in zip(mensagem.respostas, simulacao.indices_simulados()):
        aviso = Aviso("4205100", "Dona Emma", indice, numero, True, numero)
        assert texto == f"{PREFIXO}\n" + texto_do_aviso(aviso, config_de_teste().site_url)


def test_classes_abaixo_do_alerta_usam_o_formato_sem_alerta():
    mensagem = simular(banco.abrir(":memory:"))

    for texto, (_, indice) in zip(mensagem.respostas, simulacao.indices_simulados()):
        assert ("sem alerta" in texto) == (indice < 1.0)
        assert "Em operação real" not in texto
        assert "[SIMULAÇÃO]" not in texto


def test_todo_envio_do_simular_usa_parse_mode_html():
    mensagem = simular(banco.abrir(":memory:"))
    assert mensagem.parse_modes == [ParseMode.HTML] * len(mensagem.respostas)


def test_municipio_invalido_tambem_usa_html_e_escapa_o_nome():
    mensagem = simular(banco.abrir(":memory:"), args=["<x>&"])
    assert mensagem.parse_modes == [ParseMode.HTML]
    assert "&lt;x&gt;&amp;" in mensagem.respostas[0]


def test_mensagens_vao_so_para_o_chat_de_origem():
    """Tudo sai por `reply_text` da mensagem recebida; o bot não é usado."""

    class BotQueNaoPodeSerUsado:
        def __getattr__(self, nome):
            raise AssertionError(f"bot.{nome} não deveria ser chamado")

    conn = banco.abrir(":memory:")
    banco.inscrever(conn, 999, "4205100", AGORA)
    contexto = ContextoFalso(conn)
    contexto.bot = BotQueNaoPodeSerUsado()
    mensagem = MensagemFalsa("/simular", chat_id=CHAT)

    asyncio.run(modulo_bot.comando_simular(UpdateFalso(mensagem), contexto))

    assert len(mensagem.respostas) == len(faixas_das_classes()) + 1


def test_simular_nao_grava_nada_no_banco():
    conn = banco.abrir(":memory:")
    banco.inscrever(conn, CHAT, "4205100", AGORA)
    banco.atualizar_ultima_classe_notificada(conn, "4205100", 4, AGORA)
    antes = conn.total_changes

    simular(conn)

    assert conn.total_changes == antes
    assert banco.ultima_classe_notificada(conn, "4205100") == 4
    assert banco.ultima_classe_notificada(conn, "4206900") is None


def test_simular_com_nome_usa_o_municipio_informado():
    mensagem = simular(banco.abrir(":memory:"), args=["ibirama"])

    assert all("Ibirama" in texto for texto in mensagem.respostas[:-1])


def test_simular_com_nome_composto():
    municipios = MUNICIPIOS
    alvo = simulacao.municipio_pelo_nome(municipios, ["dona", "EMMA"])
    assert alvo is not None and alvo.nome == "Dona Emma"


def test_municipio_inexistente_devolve_a_lista_de_validos():
    mensagem = simular(banco.abrir(":memory:"), args=["Blumenau"])

    assert len(mensagem.respostas) == 1
    resposta = mensagem.respostas[0]
    assert resposta.startswith(PREFIXO)
    assert "Blumenau" in resposta
    assert "Dona Emma" in resposta and "Ibirama" in resposta
