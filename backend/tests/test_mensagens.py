"""Testes dos textos do bot (Tarefa 10): puros, em português, sem rede.

Nada aqui chama o relógio: a hora de Brasília sai de um `datetime` aware
passado por parâmetro. Os textos são verificados por conteúdo (o que a RN04 e o
plano exigem que apareça), não por igualdade literal da frase inteira — assim
um ajuste de redação não quebra o teste, mas a falta de uma informação
obrigatória quebra.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.bot.inscricao import OPCAO_TODOS
from app.bot.mensagens import (
    LIMITE_MENSAGEM_TELEGRAM,
    CABECALHO_DO_STATUS,
    CORES_DA_BARRA,
    ORIENTACOES_POR_CLASSE,
    RESSALVA_RN04,
    SEPARADOR_DO_STATUS,
    TEXTO_SEM_INSCRICAO,
    barra,
    bloco_do_status,
    partes_do_status,
    rodape_do_status,
    texto_boas_vindas,
    texto_do_aviso,
    texto_do_status,
    texto_inscricao_confirmada,
)
from app.bot.regra_aviso import Aviso
from app.bot.simulacao import indices_simulados
from app.classificacao.classes import faixas_das_classes, nome_classe
from app.modelos.banco import IndiceAtual

UTC = timezone.utc
SITE_URL = "https://vigia.exemplo.org"
D0 = date(2026, 10, 1)


def aviso_de_teste(indice: float = 1.25, classe_do_aviso: int = 4) -> Aviso:
    return Aviso(
        ibge="4206900",
        nome="Ibirama",
        indice=indice,
        classe=classe_do_aviso,
        avisar=True,
        nova_classe=classe_do_aviso,
    )


# --- aviso --------------------------------------------------------------------


def test_aviso_tem_municipio_indice_com_virgula_classe_e_link_do_site():
    texto = texto_do_aviso(aviso_de_teste(), SITE_URL)

    assert "Ibirama" in texto
    assert "1,25" in texto  # vírgula decimal, duas casas (RN05)
    assert "moderado" in texto
    assert "classe 4" in texto  # o número junto do nome (RN03)
    assert SITE_URL in texto


def test_indice_do_aviso_sai_com_duas_casas_arredondadas_para_exibicao():
    assert "1,05" in texto_do_aviso(aviso_de_teste(indice=1.0512), SITE_URL)
    assert "2,00" in texto_do_aviso(aviso_de_teste(indice=2.0, classe_do_aviso=5), SITE_URL)


def test_aviso_nao_usa_ponto_decimal_no_indice():
    texto = texto_do_aviso(aviso_de_teste(indice=1.25), SITE_URL)

    assert "1.25" not in texto


def test_aviso_diz_que_nao_e_alerta_oficial():
    texto = texto_do_aviso(aviso_de_teste(), SITE_URL)

    assert "não emite alerta oficial" in texto


def test_aviso_de_classe_mais_alta_nomeia_a_classe_certa():
    texto = texto_do_aviso(aviso_de_teste(indice=3.5, classe_do_aviso=7), SITE_URL)

    assert "extremamente alto" in texto


# --- /status ------------------------------------------------------------------


def test_status_lista_cada_municipio_com_indice_classe_e_hora_de_brasilia():
    calculado_em = datetime(2026, 10, 1, 21, 30, tzinfo=UTC)  # 18:30 em Brasília
    situacoes = [
        ("Ibirama", IndiceAtual(indice=1.25, classe=4, dia_alvo=D0, calculado_em=calculado_em)),
        ("Dona Emma", IndiceAtual(indice=0.33, classe=1, dia_alvo=D0, calculado_em=calculado_em)),
    ]

    texto = texto_do_status(situacoes, SITE_URL)

    assert "Ibirama" in texto
    assert "1,25" in texto
    assert "moderado" in texto
    assert "Dona Emma" in texto
    assert "0,33" in texto
    assert "extremamente baixo" in texto
    assert "01/10/2026 18:30" in texto


def test_status_converte_para_brasilia_mesmo_virando_o_dia():
    # 2026-10-01T01:00Z é 22:00 de 30/09 em Brasília.
    situacoes = [
        (
            "Ibirama",
            IndiceAtual(
                indice=1.25,
                classe=4,
                dia_alvo=D0,
                calculado_em=datetime(2026, 10, 1, 1, 0, tzinfo=UTC),
            ),
        )
    ]

    assert "30/09/2026 22:00" in texto_do_status(situacoes, SITE_URL)


def test_status_aceita_calculado_em_em_qualquer_fuso_e_exibe_em_brasilia():
    calculado_em = datetime(2026, 10, 1, 23, 30, tzinfo=timezone(timedelta(hours=2)))
    situacoes = [
        ("Ibirama", IndiceAtual(indice=1.25, classe=4, dia_alvo=D0, calculado_em=calculado_em))
    ]

    # 2026-10-01T23:30+02:00 é 2026-10-01T21:30Z, isto é, 18:30 em Brasília.
    assert "01/10/2026 18:30" in texto_do_status(situacoes, SITE_URL)


def test_status_mostra_sem_dados_para_municipio_sem_calculo():
    texto = texto_do_status([("Witmarsum", None)], SITE_URL)

    assert "Witmarsum" in texto
    assert "ainda sem cálculo" in texto


def test_status_sem_inscricoes_orienta_a_usar_start():
    texto = texto_do_status([], SITE_URL)

    assert "/start" in texto


def test_status_tambem_diz_que_o_vigia_nao_emite_alerta_oficial():
    # RN04: toda tela (e aqui, toda mensagem) com índice informa isso.
    situacoes = [
        (
            "Ibirama",
            IndiceAtual(
                indice=1.25,
                classe=4,
                dia_alvo=D0,
                calculado_em=datetime(2026, 10, 1, 21, 30, tzinfo=UTC),
            ),
        )
    ]

    assert "não emite alerta oficial" in texto_do_status(situacoes, SITE_URL)


def test_status_sem_inscricoes_nao_precisa_do_aviso_de_alerta_oficial():
    # Sem índice exibido não há o que ressalvar; o texto fica curto e útil.
    texto = texto_do_status([], SITE_URL)

    assert RESSALVA_RN04 not in texto
    assert "sem dados" not in texto


def test_status_mostra_o_dia_alvo_do_indice_exibido():
    # RN11: o dia-alvo fica visível. Importa quando o município ficou sem dados
    # na execução corrente — o índice mostrado é o da anterior, e sem o dia-alvo
    # o leitor acha que se refere a hoje.
    situacoes = [
        (
            "Ibirama",
            IndiceAtual(
                indice=1.25,
                classe=4,
                dia_alvo=date(2026, 9, 30),
                calculado_em=datetime(2026, 10, 1, 21, 30, tzinfo=UTC),
            ),
        )
    ]

    texto = texto_do_status(situacoes, SITE_URL)

    assert "30/09/2026" in texto
    assert "01/10/2026 18:30" in texto


# --- formato HTML -------------------------------------------------------------

BARRAS_ESPERADAS = {
    1: "🟩⬜⬜⬜⬜⬜⬜",
    2: "🟩🟩⬜⬜⬜⬜⬜",
    3: "🟩🟩🟩⬜⬜⬜⬜",
    4: "🟩🟩🟩🟨⬜⬜⬜",
    5: "🟩🟩🟩🟨🟧⬜⬜",
    6: "🟩🟩🟩🟨🟧🟥⬜",
    7: "🟩🟩🟩🟨🟧🟥🟪",
}

ICONE_E_TITULO_ESPERADOS = {
    1: ("ℹ️", "Ibirama — sem alerta"),
    2: ("ℹ️", "Ibirama — sem alerta"),
    3: ("ℹ️", "Ibirama — sem alerta"),
    4: ("⚠️", "ATENÇÃO — Ibirama"),
    5: ("⚠️", "ALERTA — Ibirama"),
    6: ("🚨", "ALERTA — Ibirama"),
    7: ("🚨", "ALERTA MÁXIMO — Ibirama"),
}

CALCULADO_EM = datetime(2026, 10, 1, 21, 30, tzinfo=UTC)  # 18:30 em Brasília


def aviso_completo(numero_classe: int, nome: str = "Ibirama") -> Aviso:
    indice = dict(indices_simulados())[numero_classe]
    return Aviso(
        ibge="4206900",
        nome=nome,
        indice=indice,
        classe=numero_classe,
        avisar=True,
        nova_classe=numero_classe,
        efr_mm=42.37,
        rtotal_mm=18.5,
        dia_alvo=D0,
        calculado_em=CALCULADO_EM,
    )


@pytest.mark.parametrize("numero_classe", range(1, 8))
def test_barra_colorida_por_classe(numero_classe):
    assert barra(numero_classe) == BARRAS_ESPERADAS[numero_classe]
    assert BARRAS_ESPERADAS[numero_classe] in texto_do_aviso(
        aviso_completo(numero_classe), SITE_URL
    )


def test_ha_uma_cor_de_barra_por_classe():
    assert len(CORES_DA_BARRA) == len(faixas_das_classes())


@pytest.mark.parametrize("numero_classe", range(1, 8))
def test_icone_e_titulo_por_faixa(numero_classe):
    icone, titulo = ICONE_E_TITULO_ESPERADOS[numero_classe]
    primeira_linha = texto_do_aviso(aviso_completo(numero_classe), SITE_URL).split("\n")[0]
    assert primeira_linha == f"{icone} <b>{titulo}</b>"


@pytest.mark.parametrize("numero_classe", range(1, 8))
def test_segunda_linha_tem_nome_da_classe_e_posicao(numero_classe):
    segunda = texto_do_aviso(aviso_completo(numero_classe), SITE_URL).split("\n")[1]
    assert segunda == f"<b>Risco {nome_classe(numero_classe)}</b> · classe {numero_classe} de 7"


@pytest.mark.parametrize("numero_classe", [1, 2, 3])
def test_classes_sem_alerta_nao_dizem_que_podera_haver_risco(numero_classe):
    texto = texto_do_aviso(aviso_completo(numero_classe), SITE_URL)
    assert "poderá entrar em situação de risco" not in texto
    assert "O que fazer" not in texto
    assert "Condições normais para a chuva acumulada." in texto
    assert "📅 01/10/2026, 18:30" in texto


@pytest.mark.parametrize("numero_classe", [4, 5, 6, 7])
def test_alerta_traz_chuva_validade_orientacoes_e_emergencia(numero_classe):
    texto = texto_do_aviso(aviso_completo(numero_classe), SITE_URL)
    assert "🌧 Chuva acumulada: 42,37 mm · ☔ Previsão 24 h: 18,50 mm" in texto
    assert "📅 Válido para 01/10/2026 · cálculo às 18:30" in texto
    assert "<b>O que fazer</b>" in texto
    for orientacao in ORIENTACOES_POR_CLASSE[numero_classe]:
        assert f"• {orientacao}" in texto
    assert "• Emergência: Defesa Civil <b>199</b> · Bombeiros <b>193</b>" in texto
    assert f"🗺 Ver no mapa: {SITE_URL}" in texto
    assert texto.endswith("<i>Sistema acadêmico, não emite alerta oficial.</i>")


def test_orientacoes_por_classe():
    assert len(ORIENTACOES_POR_CLASSE[4]) == 2
    assert ORIENTACOES_POR_CLASSE[5][:2] == ORIENTACOES_POR_CLASSE[4]
    assert len(ORIENTACOES_POR_CLASSE[5]) == 3
    assert ORIENTACOES_POR_CLASSE[6] == ORIENTACOES_POR_CLASSE[7]
    assert len(ORIENTACOES_POR_CLASSE[6]) == 2


def test_alerta_sem_os_campos_do_calculo_omite_as_linhas():
    texto = texto_do_aviso(aviso_de_teste(), SITE_URL)
    assert "Chuva acumulada" not in texto
    assert "Válido para" not in texto
    assert "📊 Índice: <b>1,25</b>" in texto


def test_sem_alerta_sem_data_omite_so_a_data():
    aviso = aviso_de_teste(indice=0.5, classe_do_aviso=2)
    texto = texto_do_aviso(aviso, SITE_URL)
    assert "📊 Índice: <b>0,50</b>\n" in texto
    assert "📅" not in texto


def test_nome_do_municipio_e_url_saem_escapados():
    texto = texto_do_aviso(aviso_completo(5, nome="A<b>&C"), "https://x.org/?a=1&b=<2>")
    assert "A&lt;b&gt;&amp;C" in texto
    assert "A<b>&C" not in texto
    assert "https://x.org/?a=1&amp;b=&lt;2&gt;" in texto


def test_status_escapa_o_nome_do_municipio():
    texto = texto_do_status(
        [("A<b>&C", None), ("D&E", IndiceAtual(1.25, 4, D0, CALCULADO_EM))], SITE_URL
    )
    assert "A&lt;b&gt;&amp;C" in texto
    assert "D&amp;E" in texto


def test_status_tem_um_bloco_por_municipio_e_link_e_ressalva_uma_vez():
    situacoes = [
        ("Ibirama", IndiceAtual(2.2, 5, D0, CALCULADO_EM)),
        ("Dona Emma", IndiceAtual(0.33, 1, D0, CALCULADO_EM)),
        ("Witmarsum", None),
    ]
    texto = texto_do_status(situacoes, SITE_URL)

    assert "⚠️ <b>Ibirama</b>" in texto and "alto" in texto
    assert BARRAS_ESPERADAS[5] in texto and "2,20" in texto
    assert "ℹ️ <b>Dona Emma</b>" in texto and BARRAS_ESPERADAS[1] in texto
    assert "<b>Witmarsum</b>: ainda sem cálculo" in texto
    assert texto.count(SITE_URL) == 1
    assert texto.count("não emite alerta oficial") == 1
    assert texto.endswith("<i>Sistema acadêmico, não emite alerta oficial.</i>")


def test_nenhuma_mensagem_passa_do_limite_do_telegram():
    nome_longo = "Município " * 10
    for numero_classe in range(1, 8):
        assert len(texto_do_aviso(aviso_completo(numero_classe, nome_longo), SITE_URL)) <= 4096
    situacoes = [
        (nome_longo + str(i), IndiceAtual(3.9, 7, D0, CALCULADO_EM)) for i in range(6)
    ]
    assert len(texto_do_status(situacoes, SITE_URL)) <= 4096


# --- textos do /start, da inscrição e do /status em partes --------------------


def test_boas_vindas_sem_sugestao_orienta_os_comandos():
    texto = texto_boas_vindas(None)

    assert "/status" in texto
    assert "/parar" in texto
    assert f'"{OPCAO_TODOS}"' in texto


def test_boas_vindas_com_sugestao_cita_o_municipio():
    assert 'toque em "Ibirama"' in texto_boas_vindas("Ibirama")


def test_boas_vindas_escapa_o_nome():
    texto = texto_boas_vindas("A<B")

    assert "A&lt;B" in texto
    assert "A<B" not in texto


def test_confirmacao_lista_os_nomes_e_traz_a_ressalva():
    texto = texto_inscricao_confirmada(["Dona Emma", "Ibirama"])

    assert texto.startswith("Pronto! Você vai receber avisos de: Dona Emma, Ibirama.")
    assert RESSALVA_RN04 in texto


def test_status_e_a_juncao_das_partes():
    situacoes = [
        ("Ibirama", None),
        ("Dona Emma", IndiceAtual(
            indice=1.25, classe=4, dia_alvo=D0,
            calculado_em=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        )),
    ]
    blocos = [bloco_do_status(nome, atual) for nome, atual in situacoes]

    assert texto_do_status(situacoes, SITE_URL) == (
        CABECALHO_DO_STATUS
        + SEPARADOR_DO_STATUS
        + SEPARADOR_DO_STATUS.join(blocos)
        + SEPARADOR_DO_STATUS
        + rodape_do_status(SITE_URL)
    )


def test_status_sem_inscricao_e_o_texto_fixo():
    assert texto_do_status([], SITE_URL) == TEXTO_SEM_INSCRICAO


def _utf16(texto: str) -> int:
    return len(texto.encode("utf-16-le")) // 2


def test_partes_do_status_curto_e_igual_ao_texto():
    situacoes = [("Ibirama", None), ("Witmarsum", None)]
    assert partes_do_status(situacoes, "https://x") == [texto_do_status(situacoes, "https://x")]


def test_partes_do_status_sem_inscricao():
    assert partes_do_status([], "https://x") == [TEXTO_SEM_INSCRICAO]


def test_partes_do_status_divide_entre_blocos():
    situacoes = [(f"Município {i}", None) for i in range(27)]
    partes = partes_do_status(situacoes, "https://x", limite=200)
    assert len(partes) > 1
    assert all(_utf16(p) <= 200 for p in partes)
    blocos = [bloco_do_status(nome, None) for nome, _ in situacoes]
    juntas = "".join(partes)
    assert [juntas.find(b) for b in blocos] == sorted(juntas.find(b) for b in blocos)
    assert partes[0].startswith(CABECALHO_DO_STATUS)
    assert partes[-1].endswith(rodape_do_status("https://x"))
    assert LIMITE_MENSAGEM_TELEGRAM == 4096


def test_partes_do_status_bloco_maior_que_o_limite_e_erro():
    with pytest.raises(ValueError, match="bloco"):
        partes_do_status([("M" * 300, None)], "https://x", limite=100)
