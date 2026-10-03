"""Testes da agregação por município e dia-alvo (Tarefa 6).

As séries de entrada são montadas à mão, com rótulos escritos literalmente,
e os valores esperados são literais — nenhum teste usa as funções de janela
da agregação para construir a própria entrada.
"""

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone

import pytest

from app.calculo.agregacao import (
    AgregacaoInvalidaError,
    acumulados,
    calcular,
    HoraAusenteError,
    RodadaInvalidaError,
    janela_efr,
    peso,
    resultado_dia,
    rotulos_efr,
    rotulos_rtotal,
    somar_rtotal,
)
from app.calculo.chuva_efetiva import efr
from app.config import Municipio, Ponto
from app.modelos.tipos import DadosMunicipio, Membro

UTC = timezone.utc


def serie(inicio: datetime, horas: int, valor: float = 0.0) -> dict[datetime, float]:
    """Série horária densa de `horas` rótulos a partir de `inicio`, todos com `valor`.

    Construída só com `timedelta`, sem tocar nas funções sob teste.
    """
    return {inicio + timedelta(hours=k): valor for k in range(horas)}


# --- rótulos das janelas ------------------------------------------------------


def test_rotulos_efr_vai_da_meia_noite_do_dia_alvo_a_169_horas_antes():
    rotulos = rotulos_efr(date(2026, 10, 1))

    assert len(rotulos) == 169
    assert rotulos[0] == datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    assert rotulos[1] == datetime(2026, 9, 30, 23, 0, tzinfo=UTC)
    assert rotulos[168] == datetime(2026, 9, 24, 0, 0, tzinfo=UTC)


def test_rotulos_rtotal_vai_de_t01_a_meia_noite_do_dia_seguinte():
    rotulos = rotulos_rtotal(date(2026, 10, 1))

    assert len(rotulos) == 24
    assert rotulos[0] == datetime(2026, 10, 1, 1, 0, tzinfo=UTC)
    assert rotulos[23] == datetime(2026, 10, 2, 0, 0, tzinfo=UTC)


def test_janelas_do_efr_e_do_rtotal_sao_adjacentes_sem_sobreposicao_nem_lacuna():
    janela_do_efr = rotulos_efr(date(2026, 10, 1))
    janela_do_rtotal = rotulos_rtotal(date(2026, 10, 1))

    assert set(janela_do_efr) & set(janela_do_rtotal) == set()
    assert min(janela_do_rtotal) - max(janela_do_efr) == timedelta(hours=1)

    todos = sorted(set(janela_do_efr) | set(janela_do_rtotal))
    assert len(todos) == 169 + 24
    assert all(
        seguinte - anterior == timedelta(hours=1)
        for anterior, seguinte in zip(todos, todos[1:])
    )


# --- janela_efr ---------------------------------------------------------------


def test_janela_efr_poe_a_hora_mais_recente_no_indice_zero():
    antecedente = serie(datetime(2026, 9, 25, 0, 0, tzinfo=UTC), 169)
    antecedente[datetime(2026, 10, 2, 0, 0, tzinfo=UTC)] = 5.0
    antecedente[datetime(2026, 10, 1, 23, 0, tzinfo=UTC)] = 1.0
    antecedente[datetime(2026, 10, 1, 0, 0, tzinfo=UTC)] = 7.0

    valores = janela_efr(
        date(2026, 10, 2), antecedente, {}, datetime(2026, 10, 2, 0, 0, tzinfo=UTC)
    )

    assert len(valores) == 169
    assert valores[0] == 5.0
    assert valores[1] == 1.0
    assert valores[24] == 7.0


def test_efr_do_dia_alvo_aplica_o_decaimento_na_ordem_certa():
    # 1 mm exatamente 24 h antes da meia-noite do dia-alvo: t=24, com MV=24 h
    # o fator é 0,5^(24/24) = 0,5. Se a janela saísse invertida, o mesmo
    # milímetro cairia em t=144 e o EfR seria 0,5^6 ≈ 0,0078.
    antecedente = serie(datetime(2026, 9, 25, 0, 0, tzinfo=UTC), 169)
    antecedente[datetime(2026, 10, 1, 0, 0, tzinfo=UTC)] = 1.0

    valores = janela_efr(
        date(2026, 10, 2), antecedente, {}, datetime(2026, 10, 2, 0, 0, tzinfo=UTC)
    )

    assert efr(valores, 24.0) == pytest.approx(0.5)


def test_janela_efr_usa_antecedente_ate_agora_e_previsao_depois():
    antecedente = serie(datetime(2026, 9, 25, 0, 0, tzinfo=UTC), 169, 99.0)
    previsao = serie(datetime(2026, 9, 25, 0, 0, tzinfo=UTC), 169, 77.0)
    # A hora igual a `agora_utc` ainda é antecedente; a seguinte é previsão.
    antecedente[datetime(2026, 10, 1, 12, 0, tzinfo=UTC)] = 3.0
    previsao[datetime(2026, 10, 1, 12, 0, tzinfo=UTC)] = 888.0
    antecedente[datetime(2026, 10, 1, 13, 0, tzinfo=UTC)] = 888.0
    previsao[datetime(2026, 10, 1, 13, 0, tzinfo=UTC)] = 7.0

    valores = janela_efr(
        date(2026, 10, 2), antecedente, previsao, datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    )

    assert valores[12] == 3.0
    assert valores[11] == 7.0
    assert 888.0 not in valores


def test_janela_efr_sem_uma_hora_levanta_erro_identificando_o_rotulo():
    antecedente = serie(datetime(2026, 9, 25, 0, 0, tzinfo=UTC), 169)
    del antecedente[datetime(2026, 9, 25, 0, 0, tzinfo=UTC)]

    with pytest.raises(HoraAusenteError, match="2026-09-25T00:00"):
        janela_efr(
            date(2026, 10, 2), antecedente, {}, datetime(2026, 10, 2, 0, 0, tzinfo=UTC)
        )


# --- somar_rtotal -------------------------------------------------------------


def test_somar_rtotal_soma_as_24_horas_do_dia_civil_do_dia_alvo():
    previsao = serie(datetime(2026, 10, 1, 0, 0, tzinfo=UTC), 30, 1.0)
    # Rótulo da meia-noite do próprio dia-alvo: é da janela do EfR, não entra.
    previsao[datetime(2026, 10, 1, 0, 0, tzinfo=UTC)] = 1000.0
    # Primeiro rótulo do dia seguinte: também fica fora.
    previsao[datetime(2026, 10, 2, 1, 0, tzinfo=UTC)] = 500.0

    assert somar_rtotal(date(2026, 10, 1), previsao) == pytest.approx(24.0)


def test_somar_rtotal_sem_a_meia_noite_do_dia_seguinte_levanta_erro():
    previsao = serie(datetime(2026, 10, 1, 1, 0, tzinfo=UTC), 23, 1.0)

    with pytest.raises(HoraAusenteError, match="2026-10-02T00:00"):
        somar_rtotal(date(2026, 10, 1), previsao)


# --- peso ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "atraso_h, peso_principal, peso_secundaria",
    [
        (0, 1.0, 0.8),
        (6, 5 / 6, 5 / 6 * 0.8),
        (12, 2 / 3, 2 / 3 * 0.8),
        (18, 0.5, 0.4),
        (24, 1 / 3, 1 / 3 * 0.8),
        (30, 1 / 6, 1 / 6 * 0.8),
    ],
)
def test_peso_segue_a_tabela_da_decisao_do_ensemble(atraso_h, peso_principal, peso_secundaria):
    # Rodada principal (12 UTC) e secundária (18 UTC) com o mesmo atraso.
    rodada_principal = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    rodada_secundaria = datetime(2026, 10, 1, 18, 0, tzinfo=UTC)

    assert peso(
        rodada_principal, rodada_principal + timedelta(hours=atraso_h)
    ) == pytest.approx(peso_principal)
    assert peso(
        rodada_secundaria, rodada_secundaria + timedelta(hours=atraso_h)
    ) == pytest.approx(peso_secundaria)


def test_peso_da_rodada_mais_recente_e_maior_que_o_da_anterior():
    agora = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    recente = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    anterior = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

    assert peso(recente, agora) > peso(anterior, agora)


def test_peso_da_rodada_com_assimilacao_e_maior_no_mesmo_atraso():
    principal = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
    secundaria = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
    atraso = timedelta(hours=12)

    assert peso(principal, principal + atraso) > peso(secundaria, secundaria + atraso)


def test_peso_e_zero_no_atraso_de_36_horas():
    rodada = datetime(2026, 9, 30, 0, 0, tzinfo=UTC)

    assert peso(rodada, rodada + timedelta(hours=36)) == 0.0


def test_peso_e_zero_com_atraso_acima_de_36_horas():
    rodada = datetime(2026, 9, 30, 6, 0, tzinfo=UTC)

    assert peso(rodada, rodada + timedelta(hours=48)) == 0.0


def test_peso_converte_a_rodada_para_utc_antes_de_classificar_o_horario():
    # 21:00 em UTC-3 é 00:00 UTC: rodada principal, peso 1,0 no atraso zero.
    rodada = datetime(2026, 9, 30, 21, 0, tzinfo=timezone(timedelta(hours=-3)))

    assert peso(rodada, datetime(2026, 10, 1, 0, 0, tzinfo=UTC)) == pytest.approx(1.0)


def test_peso_com_rodada_sem_fuso_levanta_erro():
    with pytest.raises(ValueError, match="rodada"):
        peso(datetime(2026, 10, 1, 0, 0), datetime(2026, 10, 1, 12, 0, tzinfo=UTC))


def test_peso_com_agora_utc_sem_fuso_levanta_erro():
    with pytest.raises(ValueError, match="agora_utc"):
        peso(datetime(2026, 10, 1, 0, 0, tzinfo=UTC), datetime(2026, 10, 1, 12, 0))


def test_peso_de_rodada_fora_do_horario_sinotico_levanta_erro():
    with pytest.raises(RodadaInvalidaError, match="sinótico"):
        peso(
            datetime(2026, 10, 1, 3, 0, tzinfo=UTC),
            datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        )


def test_peso_de_rodada_posterior_a_agora_utc_levanta_erro():
    with pytest.raises(RodadaInvalidaError, match="posterior"):
        peso(
            datetime(2026, 10, 1, 18, 0, tzinfo=UTC),
            datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        )


# --- agregação de um dia-alvo -------------------------------------------------

D0 = date(2026, 10, 1)
AGORA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
RODADA = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)


def municipio_de_teste(
    quantidade_de_pontos: int, limiar_mm: float = 100.0, ibge: str = "4204202"
) -> Municipio:
    return Municipio(
        ibge=ibge,
        nome="Município de Teste",
        limiar_mm=limiar_mm,
        fonte_limiar="teste",
        mv_h=24.0,
        pontos=tuple(
            Ponto(lat=-27.0 - indice, lon=-49.5) for indice in range(quantidade_de_pontos)
        ),
    )


def antecedente_de_teste(chuva_na_meia_noite: float = 0.0) -> dict[datetime, float]:
    """Horas zeradas até 2026-10-01T12:00Z, menos o rótulo `2026-10-01T00:00Z`.

    Como o fator de decaimento em t=0 é 0,5^0 = 1, o EfR do dia-alvo D0 fica
    igual, em mm, ao valor posto nesse rótulo.
    """
    serie_antecedente = serie(datetime(2026, 9, 24, 0, 0, tzinfo=UTC), 181)
    serie_antecedente[datetime(2026, 10, 1, 0, 0, tzinfo=UTC)] = chuva_na_meia_noite
    return serie_antecedente


def previsao_de_teste(rtotal: float) -> dict[datetime, float]:
    """Série de um membro com todo o `rtotal` de D0 no rótulo `2026-10-01T01:00Z`.

    Os rótulos vizinhos de fora da janela do `Rtotal` levam valores-engodo:
    uma janela deslocada por uma hora produziria um resultado absurdo.
    """
    serie_previsao = {
        datetime(2026, 9, 30, 23, 0, tzinfo=UTC): 1000.0,
        datetime(2026, 10, 1, 0, 0, tzinfo=UTC): 1000.0,
        datetime(2026, 10, 2, 1, 0, tzinfo=UTC): 1000.0,
    }
    serie_previsao.update(serie(datetime(2026, 10, 1, 1, 0, tzinfo=UTC), 24))
    serie_previsao[datetime(2026, 10, 1, 1, 0, tzinfo=UTC)] = rtotal
    return serie_previsao


def test_indice_do_dia_e_a_media_ponderada_do_maior_subindice_de_cada_membro():
    # Caso do contrato: 2 pontos x 2 membros de peso igual (mesma rodada).
    # Membro A: subíndices 1,2 e 0,8 -> 1,2. Membro B: 0,6 e 0,9 -> 0,9.
    municipio = municipio_de_teste(quantidade_de_pontos=2)
    dados = DadosMunicipio(
        ibge=municipio.ibge,
        antecedente=[antecedente_de_teste(), antecedente_de_teste()],
        membros=[
            Membro(
                modelo="gfs_global",
                rodada=RODADA,
                chuva=[previsao_de_teste(120.0), previsao_de_teste(80.0)],
            ),
            Membro(
                modelo="icon_global",
                rodada=RODADA,
                chuva=[previsao_de_teste(60.0), previsao_de_teste(90.0)],
            ),
        ],
    )

    dia = resultado_dia(municipio, dados, D0, 0, AGORA)

    assert dia.dia_alvo == D0
    assert dia.d == 0
    assert dia.n_membros == 2
    assert dia.indice == pytest.approx(1.05)
    assert dia.classe == 4
    assert dia.efr_mm == pytest.approx(0.0)
    assert dia.rtotal_mm == pytest.approx(105.0)
    assert dia.prob.pontuais == pytest.approx(0.5)
    assert dia.prob.esparsos == pytest.approx(0.0)
    assert dia.prob.generalizados == pytest.approx(0.0)


def test_efr_e_rtotal_exportados_vem_do_ponto_de_maior_subindice():
    # Ponto 0: (10 + 50)/100 = 0,6. Ponto 1: (30 + 100)/100 = 1,3 -> escolhido.
    municipio = municipio_de_teste(quantidade_de_pontos=2)
    dados = DadosMunicipio(
        ibge=municipio.ibge,
        antecedente=[antecedente_de_teste(10.0), antecedente_de_teste(30.0)],
        membros=[
            Membro(
                modelo="gfs_global",
                rodada=RODADA,
                chuva=[previsao_de_teste(50.0), previsao_de_teste(100.0)],
            )
        ],
    )

    dia = resultado_dia(municipio, dados, D0, 0, AGORA)

    assert dia.indice == pytest.approx(1.3)
    assert dia.efr_mm == pytest.approx(30.0)
    assert dia.rtotal_mm == pytest.approx(100.0)


def test_empate_de_subindice_entre_pontos_escolhe_o_primeiro_ponto_da_configuracao():
    # Os dois pontos dão subíndice 1,0; só a composição difere.
    municipio = municipio_de_teste(quantidade_de_pontos=2)
    dados = DadosMunicipio(
        ibge=municipio.ibge,
        antecedente=[antecedente_de_teste(50.0), antecedente_de_teste(20.0)],
        membros=[
            Membro(
                modelo="gfs_global",
                rodada=RODADA,
                chuva=[previsao_de_teste(50.0), previsao_de_teste(80.0)],
            )
        ],
    )

    dia = resultado_dia(municipio, dados, D0, 0, AGORA)

    assert dia.indice == pytest.approx(1.0)
    assert dia.efr_mm == pytest.approx(50.0)
    assert dia.rtotal_mm == pytest.approx(50.0)


def test_membro_com_peso_zero_fica_fora_do_calculo_e_da_contagem():
    municipio = municipio_de_teste(quantidade_de_pontos=2)
    rodada_descartada = datetime(2026, 9, 29, 18, 0, tzinfo=UTC)  # atraso de 42 h
    dados = DadosMunicipio(
        ibge=municipio.ibge,
        antecedente=[antecedente_de_teste(), antecedente_de_teste()],
        membros=[
            Membro(
                modelo="gfs_global",
                rodada=RODADA,
                chuva=[previsao_de_teste(120.0), previsao_de_teste(80.0)],
            ),
            Membro(
                modelo="icon_global",
                rodada=RODADA,
                chuva=[previsao_de_teste(60.0), previsao_de_teste(90.0)],
            ),
            Membro(
                modelo="ecmwf_ifs025",
                rodada=rodada_descartada,
                chuva=[previsao_de_teste(900.0), previsao_de_teste(900.0)],
            ),
        ],
    )

    dia = resultado_dia(municipio, dados, D0, 0, AGORA)

    assert dia.n_membros == 2
    assert dia.indice == pytest.approx(1.05)


def test_membro_sem_as_24_horas_do_dia_alvo_fica_fora_daquele_dia():
    municipio = municipio_de_teste(quantidade_de_pontos=1)
    previsao_incompleta = previsao_de_teste(900.0)
    del previsao_incompleta[datetime(2026, 10, 1, 7, 0, tzinfo=UTC)]
    dados = DadosMunicipio(
        ibge=municipio.ibge,
        antecedente=[antecedente_de_teste()],
        membros=[
            Membro(modelo="gfs_global", rodada=RODADA, chuva=[previsao_de_teste(120.0)]),
            Membro(modelo="icon_global", rodada=RODADA, chuva=[previsao_de_teste(90.0)]),
            Membro(modelo="ecmwf_ifs025", rodada=RODADA, chuva=[previsao_incompleta]),
        ],
    )

    dia = resultado_dia(municipio, dados, D0, 0, AGORA)

    assert dia.n_membros == 2
    assert dia.indice == pytest.approx(1.05)


def test_resultado_dia_sem_nenhum_membro_utilizavel_devolve_none():
    municipio = municipio_de_teste(quantidade_de_pontos=1)
    dados = DadosMunicipio(
        ibge=municipio.ibge, antecedente=[antecedente_de_teste()], membros=[]
    )

    assert resultado_dia(municipio, dados, D0, 0, AGORA) is None


def test_membro_com_menos_series_que_pontos_levanta_erro_identificando_o_municipio():
    municipio = municipio_de_teste(quantidade_de_pontos=2)
    dados = DadosMunicipio(
        ibge=municipio.ibge,
        antecedente=[antecedente_de_teste(), antecedente_de_teste()],
        membros=[
            Membro(modelo="gfs_global", rodada=RODADA, chuva=[previsao_de_teste(120.0)])
        ],
    )

    with pytest.raises(AgregacaoInvalidaError, match="4204202.*gfs_global"):
        resultado_dia(municipio, dados, D0, 0, AGORA)


def test_antecedente_com_menos_series_que_pontos_levanta_erro_identificando_o_municipio():
    municipio = municipio_de_teste(quantidade_de_pontos=2)
    dados = DadosMunicipio(
        ibge=municipio.ibge,
        antecedente=[antecedente_de_teste()],
        membros=[
            Membro(
                modelo="gfs_global",
                rodada=RODADA,
                chuva=[previsao_de_teste(120.0), previsao_de_teste(80.0)],
            )
        ],
    )

    with pytest.raises(AgregacaoInvalidaError, match="4204202.*antecedente"):
        resultado_dia(municipio, dados, D0, 0, AGORA)


def test_resultado_dia_e_imutavel():
    municipio = municipio_de_teste(quantidade_de_pontos=1)
    dados = DadosMunicipio(
        ibge=municipio.ibge,
        antecedente=[antecedente_de_teste()],
        membros=[
            Membro(modelo="gfs_global", rodada=RODADA, chuva=[previsao_de_teste(120.0)])
        ],
    )

    dia = resultado_dia(municipio, dados, D0, 0, AGORA)

    with pytest.raises(FrozenInstanceError):
        dia.indice = 9.0


# --- chuva acumulada ----------------------------------------------------------


def test_acumulados_de_1mm_por_hora_dao_24_48_72_e_96():
    antecedente = serie(datetime(2026, 9, 24, 0, 0, tzinfo=UTC), 181, 1.0)

    assert acumulados([antecedente], AGORA) == {
        "24h": pytest.approx(24.0),
        "48h": pytest.approx(48.0),
        "72h": pytest.approx(72.0),
        "96h": pytest.approx(96.0),
    }


def test_acumulados_escolhem_o_ponto_de_maior_valor_em_cada_janela():
    # Ponto 0 chove só nas últimas 24 h; ponto 1 chove só antes disso.
    ponto_recente = serie(datetime(2026, 9, 24, 0, 0, tzinfo=UTC), 181)
    for hora in range(157, 181):  # 2026-09-30T13:00Z .. 2026-10-01T12:00Z
        ponto_recente[datetime(2026, 9, 24, 0, 0, tzinfo=UTC) + timedelta(hours=hora)] = 2.0
    ponto_antigo = serie(datetime(2026, 9, 24, 0, 0, tzinfo=UTC), 181, 1.0)
    for hora in range(157, 181):
        ponto_antigo[datetime(2026, 9, 24, 0, 0, tzinfo=UTC) + timedelta(hours=hora)] = 0.0

    resultado = acumulados([ponto_recente, ponto_antigo], AGORA)

    assert resultado["24h"] == pytest.approx(48.0)  # ponto 0: 24 h x 2 mm
    assert resultado["96h"] == pytest.approx(72.0)  # ponto 1: 72 h x 1 mm


def test_acumulados_param_na_ultima_hora_cheia_quando_agora_tem_minutos():
    # A série termina no rótulo 12:00Z; `agora_utc` com minutos não pode exigir
    # a hora seguinte.
    antecedente = serie(datetime(2026, 9, 24, 0, 0, tzinfo=UTC), 181, 1.0)

    assert acumulados([antecedente], datetime(2026, 10, 1, 12, 59, tzinfo=UTC))[
        "24h"
    ] == pytest.approx(24.0)


def test_acumulados_sem_uma_hora_da_janela_levanta_erro_identificando_o_rotulo():
    antecedente = serie(datetime(2026, 9, 24, 0, 0, tzinfo=UTC), 181, 1.0)
    del antecedente[datetime(2026, 9, 30, 10, 0, tzinfo=UTC)]

    with pytest.raises(HoraAusenteError, match="2026-09-30T10:00"):
        acumulados([antecedente], AGORA)


# --- calcular -----------------------------------------------------------------


def previsao_de_quatro_dias(
    rtotal_por_dia: tuple[float, float, float, float],
) -> dict[datetime, float]:
    """Série de um membro de 2026-10-01T01:00Z a 2026-10-05T00:00Z (96 rótulos).

    O `rtotal` de cada dia-alvo fica todo no rótulo `T01:00Z` do respectivo
    dia; os demais rótulos ficam em zero.
    """
    serie_previsao = serie(datetime(2026, 10, 1, 1, 0, tzinfo=UTC), 96)
    primeiros_rotulos = (
        datetime(2026, 10, 1, 1, 0, tzinfo=UTC),
        datetime(2026, 10, 2, 1, 0, tzinfo=UTC),
        datetime(2026, 10, 3, 1, 0, tzinfo=UTC),
        datetime(2026, 10, 4, 1, 0, tzinfo=UTC),
    )
    for rotulo, rtotal in zip(primeiros_rotulos, rtotal_por_dia, strict=True):
        serie_previsao[rotulo] = rtotal
    return serie_previsao


def dados_com_tres_membros(ibge: str = "4204202") -> DadosMunicipio:
    """Três membros da mesma rodada (peso igual) com chuva só em D0."""
    return DadosMunicipio(
        ibge=ibge,
        antecedente=[antecedente_de_teste()],
        membros=[
            Membro(
                modelo="gfs_global",
                rodada=RODADA,
                chuva=[previsao_de_quatro_dias((120.0, 0.0, 0.0, 0.0))],
            ),
            Membro(
                modelo="icon_global",
                rodada=RODADA,
                chuva=[previsao_de_quatro_dias((90.0, 0.0, 0.0, 0.0))],
            ),
            Membro(
                modelo="ecmwf_ifs025",
                rodada=RODADA,
                chuva=[previsao_de_quatro_dias((60.0, 0.0, 0.0, 0.0))],
            ),
        ],
    )


def test_calcular_devolve_os_quatro_dias_alvo_a_partir_da_data_utc_de_agora():
    municipio = municipio_de_teste(quantidade_de_pontos=1)

    resultado = calcular([municipio], {municipio.ibge: dados_com_tres_membros()}, AGORA)

    assert resultado.dia_alvo_d0 == date(2026, 10, 1)
    assert resultado.municipios_sem_dados == []
    (resultado_do_municipio,) = resultado.municipios
    assert resultado_do_municipio.ibge == "4204202"
    assert [dia.d for dia in resultado_do_municipio.dias] == [0, 1, 2, 3]
    assert [dia.dia_alvo for dia in resultado_do_municipio.dias] == [
        date(2026, 10, 1),
        date(2026, 10, 2),
        date(2026, 10, 3),
        date(2026, 10, 4),
    ]
    # D0: subíndices 1,2 / 0,9 / 0,6 com peso igual -> 0,9 (classe baixo).
    assert resultado_do_municipio.dias[0].indice == pytest.approx(0.9)
    assert resultado_do_municipio.dias[0].classe == 3
    assert resultado_do_municipio.dias[0].rtotal_mm == pytest.approx(90.0)
    assert resultado_do_municipio.dias[0].n_membros == 3
    # D1–D3 sem chuva prevista e sem chuva antecedente.
    for dia in resultado_do_municipio.dias[1:]:
        assert dia.indice == pytest.approx(0.0)
        assert dia.classe == 1
        assert dia.rtotal_mm == pytest.approx(0.0)
        assert dia.n_membros == 3


def test_dia_alvo_d0_vem_da_data_utc_e_nao_do_horario_de_brasilia():
    # 2026-09-30T01:00Z é 22 h de 29/09 em Brasília: D0 é 30/09, não 29/09.
    municipio = municipio_de_teste(quantidade_de_pontos=1)
    agora = datetime(2026, 9, 30, 1, 0, tzinfo=UTC)

    resultado = calcular([municipio], {}, agora)

    assert resultado.dia_alvo_d0 == date(2026, 9, 30)


def test_municipio_ausente_do_dicionario_de_dados_vai_para_sem_dados():
    municipio = municipio_de_teste(quantidade_de_pontos=1)

    resultado = calcular([municipio], {}, AGORA)

    assert resultado.municipios == []
    assert resultado.municipios_sem_dados == ["4204202"]


def test_municipio_sem_nenhum_membro_vai_para_sem_dados():
    municipio = municipio_de_teste(quantidade_de_pontos=1)
    dados = DadosMunicipio(
        ibge=municipio.ibge, antecedente=[antecedente_de_teste()], membros=[]
    )

    resultado = calcular([municipio], {municipio.ibge: dados}, AGORA)

    assert resultado.municipios == []
    assert resultado.municipios_sem_dados == ["4204202"]


def test_municipio_com_menos_de_n_min_membros_vai_para_sem_dados():
    municipio = municipio_de_teste(quantidade_de_pontos=1)
    dados = dados_com_tres_membros()
    dados = DadosMunicipio(
        ibge=dados.ibge, antecedente=dados.antecedente, membros=dados.membros[:2]
    )

    resultado = calcular([municipio], {municipio.ibge: dados}, AGORA)

    assert resultado.municipios == []
    assert resultado.municipios_sem_dados == ["4204202"]


def test_um_unico_dia_alvo_abaixo_de_n_min_derruba_o_municipio_inteiro():
    municipio = municipio_de_teste(quantidade_de_pontos=1)
    # Só D3 fica abaixo de N_MIN (2 membros): D0–D2 seguem com 3.
    dados = dados_com_tres_membros()
    previsao_sem_d3 = previsao_de_quatro_dias((60.0, 0.0, 0.0, 0.0))
    del previsao_sem_d3[datetime(2026, 10, 4, 5, 0, tzinfo=UTC)]
    dados = DadosMunicipio(
        ibge=dados.ibge,
        antecedente=dados.antecedente,
        membros=[
            *dados.membros[:2],
            Membro(modelo="ecmwf_ifs025", rodada=RODADA, chuva=[previsao_sem_d3]),
        ],
    )

    resultado = calcular([municipio], {municipio.ibge: dados}, AGORA)

    assert resultado.municipios == []
    assert resultado.municipios_sem_dados == ["4204202"]


def test_n_membros_e_contado_por_dia_alvo():
    # A hora que falta (2026-10-04T05:00Z) só é usada pelo `Rtotal` de D3: as
    # janelas do EfR de D0–D3 terminam, no mais tarde, em 2026-10-04T00:00Z.
    municipio = municipio_de_teste(quantidade_de_pontos=1)
    dados = dados_com_tres_membros()
    previsao_sem_d3 = previsao_de_quatro_dias((30.0, 0.0, 0.0, 0.0))
    del previsao_sem_d3[datetime(2026, 10, 4, 5, 0, tzinfo=UTC)]
    dados = DadosMunicipio(
        ibge=dados.ibge,
        antecedente=dados.antecedente,
        membros=[
            *dados.membros,
            # Rodada de ~24 h antes do mesmo modelo (`previous_day1`).
            Membro(
                modelo="gfs_global",
                rodada=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
                chuva=[previsao_sem_d3],
            ),
        ],
    )

    resultado = calcular([municipio], {municipio.ibge: dados}, AGORA)

    (resultado_do_municipio,) = resultado.municipios
    assert [dia.n_membros for dia in resultado_do_municipio.dias] == [4, 4, 4, 3]


def test_calcular_preserva_a_ordem_da_configuracao_nas_duas_listas():
    com_dados = municipio_de_teste(quantidade_de_pontos=1, ibge="4204202")
    sem_dados = municipio_de_teste(quantidade_de_pontos=1, ibge="4208906")
    outro_com_dados = municipio_de_teste(quantidade_de_pontos=1, ibge="4209177")

    resultado = calcular(
        [com_dados, sem_dados, outro_com_dados],
        {
            com_dados.ibge: dados_com_tres_membros(com_dados.ibge),
            outro_com_dados.ibge: dados_com_tres_membros(outro_com_dados.ibge),
        },
        AGORA,
    )

    assert [item.ibge for item in resultado.municipios] == ["4204202", "4209177"]
    assert resultado.municipios_sem_dados == ["4208906"]


def test_calcular_expoe_a_chuva_acumulada_do_municipio():
    municipio = municipio_de_teste(quantidade_de_pontos=1)
    dados = dados_com_tres_membros()
    dados = DadosMunicipio(
        ibge=dados.ibge,
        antecedente=[serie(datetime(2026, 9, 24, 0, 0, tzinfo=UTC), 181, 1.0)],
        membros=dados.membros,
    )

    resultado = calcular([municipio], {municipio.ibge: dados}, AGORA)

    (resultado_do_municipio,) = resultado.municipios
    assert resultado_do_municipio.chuva_acum_mm == {
        "24h": pytest.approx(24.0),
        "48h": pytest.approx(48.0),
        "72h": pytest.approx(72.0),
        "96h": pytest.approx(96.0),
    }


def test_calcular_com_agora_utc_sem_fuso_levanta_erro():
    municipio = municipio_de_teste(quantidade_de_pontos=1)

    with pytest.raises(ValueError, match="agora_utc"):
        calcular([municipio], {}, datetime(2026, 10, 1, 12, 0))


def test_calcular_aceita_agora_utc_em_outro_fuso_e_usa_a_data_utc():
    # 2026-09-29T22:00-03:00 é 2026-09-30T01:00Z: D0 é 30/09.
    municipio = municipio_de_teste(quantidade_de_pontos=1)
    agora = datetime(2026, 9, 29, 22, 0, tzinfo=timezone(timedelta(hours=-3)))

    assert calcular([municipio], {}, agora).dia_alvo_d0 == date(2026, 9, 30)


def test_resultado_e_resultado_municipio_sao_imutaveis():
    municipio = municipio_de_teste(quantidade_de_pontos=1)

    resultado = calcular([municipio], {municipio.ibge: dados_com_tres_membros()}, AGORA)

    with pytest.raises(FrozenInstanceError):
        resultado.dia_alvo_d0 = date(2026, 1, 1)
    with pytest.raises(FrozenInstanceError):
        resultado.municipios[0].ibge = "0000000"


# --- isolamento de falhas por município ---------------------------------------


def test_resultado_municipio_carrega_o_limiar_usado_no_calculo():
    # O `limiar_mm` é coluna da tabela `indices` (Tarefa 7) e campo do
    # `indices.json` (Tarefa 9): precisa viajar com o resultado, porque quem
    # grava recebe só o `Resultado`, não a configuração.
    municipio = municipio_de_teste(quantidade_de_pontos=1, limiar_mm=250.0)

    resultado = calcular([municipio], {municipio.ibge: dados_com_tres_membros()}, AGORA)

    assert resultado.municipios[0].limiar_mm == 250.0


def test_rodada_fora_do_horario_sinotico_isola_so_aquele_municipio():
    # Uma rodada inválida num município não pode derrubar a execução dos
    # outros cinco: a Tarefa 11 exige que falha de cálculo mande o município
    # para `municipios_sem_dados` e os demais sigam.
    bom = municipio_de_teste(quantidade_de_pontos=1, ibge="4204202")
    ruim = municipio_de_teste(quantidade_de_pontos=1, ibge="4206900")
    dados_ruins = DadosMunicipio(
        ibge=ruim.ibge,
        antecedente=[antecedente_de_teste()],
        membros=[
            Membro(
                modelo="gfs_global",
                rodada=datetime(2026, 10, 1, 3, 0, tzinfo=UTC),  # 03 UTC não é sinótico
                chuva=[previsao_de_quatro_dias((120.0, 0.0, 0.0, 0.0))],
            )
        ],
    )

    resultado = calcular(
        [bom, ruim],
        {
            bom.ibge: dados_com_tres_membros(ibge=bom.ibge),
            ruim.ibge: dados_ruins,
        },
        AGORA,
    )

    assert [item.ibge for item in resultado.municipios] == [bom.ibge]
    assert resultado.municipios_sem_dados == [ruim.ibge]


def test_serie_antecedente_incompleta_deixa_o_municipio_sem_dados():
    # Toda hora da janela de acumulado também pertence a alguma janela de EfR
    # (D0..D3 cobrem 2026-09-24T00:00Z..2026-10-04T00:00Z), então uma lacuna
    # no antecedente descarta todos os membros antes de `acumulados()` ser
    # alcançado: o município sai por `n_membros = 0`, não por exceção. O teste
    # fixa esse caminho; a exceção isolada é a dos dois testes vizinhos.
    bom = municipio_de_teste(quantidade_de_pontos=1, ibge="4204202")
    ruim = municipio_de_teste(quantidade_de_pontos=1, ibge="4206900")
    antecedente_curto = antecedente_de_teste()
    del antecedente_curto[datetime(2026, 9, 28, 5, 0, tzinfo=UTC)]
    dados_ruins = DadosMunicipio(
        ibge=ruim.ibge,
        antecedente=[antecedente_curto],
        membros=dados_com_tres_membros(ibge=ruim.ibge).membros,
    )

    resultado = calcular(
        [bom, ruim],
        {
            bom.ibge: dados_com_tres_membros(ibge=bom.ibge),
            ruim.ibge: dados_ruins,
        },
        AGORA,
    )

    assert [item.ibge for item in resultado.municipios] == [bom.ibge]
    assert resultado.municipios_sem_dados == [ruim.ibge]


def test_series_em_quantidade_errada_isolam_so_aquele_municipio():
    bom = municipio_de_teste(quantidade_de_pontos=1, ibge="4204202")
    ruim = municipio_de_teste(quantidade_de_pontos=2, ibge="4206900")

    resultado = calcular(
        [bom, ruim],
        {
            bom.ibge: dados_com_tres_membros(ibge=bom.ibge),
            ruim.ibge: dados_com_tres_membros(ibge=ruim.ibge),  # só 1 série, 2 pontos
        },
        AGORA,
    )

    assert [item.ibge for item in resultado.municipios] == [bom.ibge]
    assert resultado.municipios_sem_dados == [ruim.ibge]
