"""Testes dos textos do bot (Tarefa 10): puros, em português, sem rede.

Nada aqui chama o relógio: a hora de Brasília sai de um `datetime` aware
passado por parâmetro. Os textos são verificados por conteúdo (o que a RN04 e o
plano exigem que apareça), não por igualdade literal da frase inteira — assim
um ajuste de redação não quebra o teste, mas a falta de uma informação
obrigatória quebra.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.bot.mensagens import RESSALVA_RN04, texto_do_aviso, texto_do_status
from app.bot.regra_aviso import Aviso
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


def test_aviso_e_condicional_e_diz_que_nao_e_alerta_oficial():
    texto = texto_do_aviso(aviso_de_teste(), SITE_URL)

    assert "poderá" in texto  # texto condicional (RN04)
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
    assert "sem dados" in texto


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
