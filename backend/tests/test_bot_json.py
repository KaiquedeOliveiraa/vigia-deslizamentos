"""Testes do `bot.json`: os textos prontos que o Worker do Telegram lê."""

from __future__ import annotations

import dataclasses
import json
import os
import unicodedata
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path

import pytest

from app.bot.inscricao import OPCAO_TODOS
from app.bot.mensagens import (
    OPCAO_VOLTAR,
    CABECALHO_DO_STATUS,
    SEPARADOR_DO_STATUS,
    TEXTO_INSCRICOES_APAGADAS,
    TEXTO_OPCAO_DESCONHECIDA,
    TEXTO_SEM_INSCRICAO,
    bloco_do_status,
    rodape_do_status,
    texto_boas_vindas,
    texto_boas_vindas_grupos,
    texto_do_status,
    texto_inscricao_confirmada,
)
from app.bot.simulacao import (
    PAUSA_ENTRE_MENSAGENS_S,
    mensagens_da_simulacao,
    texto_de_fim,
    texto_municipio_invalido,
)
from app.config import carregar_municipios
from app.exportacao.bot_json import SCHEMA_VERSION_BOT_JSON, montar_bot_json
from app.exportacao.exportar import serializar
from app.modelos.banco import IndiceAtual

UTC = timezone.utc
GERADO_EM = datetime(2026, 10, 15, 14, 30, 5, tzinfo=UTC)
SITE = "https://vigia.exemplo.org"
MUNICIPIOS = carregar_municipios(
    Path(__file__).resolve().parent.parent / "config" / "municipios.json"
)


def atual(classe: int, indice: float) -> IndiceAtual:
    return IndiceAtual(
        indice=indice,
        classe=classe,
        dia_alvo=date(2026, 10, 15),
        calculado_em=datetime(2026, 10, 15, 12, 0, tzinfo=UTC),
    )


def atuais_de_teste() -> dict[str, IndiceAtual | None]:
    return {
        m.ibge: (atual(1 + k % 6, 0.4 + k) if k % 2 == 0 else None)
        for k, m in enumerate(MUNICIPIOS)
    }


def montar(simulacao: bool = False, atuais=None, gerado_em=GERADO_EM) -> dict:
    return montar_bot_json(
        MUNICIPIOS,
        atuais if atuais is not None else atuais_de_teste(),
        SITE,
        simulacao,
        gerado_em,
    )


def test_campos_da_raiz_e_ordem_dos_municipios():
    dados = montar()

    assert set(dados) == {
        "schema_version",
        "gerado_em",
        "municipios",
        "textos",
        "status",
        "simulacao",
        "grupos",
    }
    assert SCHEMA_VERSION_BOT_JSON == 1
    assert dados["schema_version"] == 1
    assert dados["gerado_em"] == "2026-10-15T14:30:05Z"
    assert dados["municipios"] == [
        {"ibge": m.ibge, "nome": m.nome} for m in MUNICIPIOS
    ]
    assert len(MUNICIPIOS) == 27


def test_gerado_em_com_outro_fuso_e_convertido_para_utc():
    brasilia = timezone(timedelta(hours=-3))
    dados = montar(gerado_em=datetime(2026, 10, 15, 11, 30, 5, tzinfo=brasilia))

    assert dados["gerado_em"] == "2026-10-15T14:30:05Z"


def test_textos_vem_das_funcoes_de_mensagens():
    textos = montar()["textos"]
    nomes = [m.nome for m in MUNICIPIOS]

    assert textos["opcao_todos"] == OPCAO_TODOS
    assert textos["boas_vindas"] == texto_boas_vindas(None)
    assert textos["boas_vindas_sugerido"] == {
        m.ibge: texto_boas_vindas(m.nome) for m in MUNICIPIOS
    }
    assert textos["inscricao_confirmada"] == {
        m.ibge: texto_inscricao_confirmada([m.nome]) for m in MUNICIPIOS
    }
    assert textos["inscricao_confirmada_todos"] == texto_inscricao_confirmada(nomes)
    assert textos["opcao_desconhecida"] == TEXTO_OPCAO_DESCONHECIDA
    assert textos["inscricoes_apagadas"] == TEXTO_INSCRICOES_APAGADAS


def test_campos_fixos_do_status():
    status = montar()["status"]
    atuais = atuais_de_teste()

    assert status["cabecalho"] == CABECALHO_DO_STATUS + SEPARADOR_DO_STATUS
    assert status["separador"] == SEPARADOR_DO_STATUS
    assert status["rodape"] == SEPARADOR_DO_STATUS + rodape_do_status(SITE)
    assert status["sem_inscricao"] == TEXTO_SEM_INSCRICAO
    assert status["blocos"] == {
        m.ibge: bloco_do_status(m.nome, atuais[m.ibge]) for m in MUNICIPIOS
    }


def test_status_bate_com_texto_do_status_em_todas_as_combinacoes_de_6():
    # Combinações dos 6 primeiros: 2^27 com a lista toda nunca terminaria.
    seis = MUNICIPIOS[:6]
    atuais = atuais_de_teste()
    status = montar(atuais=atuais)["status"]
    total = 0

    for tamanho in range(1, len(seis) + 1):
        for subconjunto in combinations(seis, tamanho):
            total += 1
            situacoes = [(m.nome, atuais[m.ibge]) for m in subconjunto]
            montado = (
                status["cabecalho"]
                + status["separador"].join(status["blocos"][m.ibge] for m in subconjunto)
                + status["rodape"]
            )
            assert montado == texto_do_status(situacoes, SITE)

    assert total == 63


def test_status_sem_inscricao_bate_com_texto_do_status_vazio():
    assert montar()["status"]["sem_inscricao"] == texto_do_status([], SITE)


def test_bloco_de_municipio_sem_calculo():
    atuais = {m.ibge: atual(3, 1.0) for m in MUNICIPIOS}
    primeiro = MUNICIPIOS[0]
    atuais[primeiro.ibge] = None

    blocos = montar(atuais=atuais)["status"]["blocos"]

    assert "ainda sem cálculo" in blocos[primeiro.ibge]
    assert "ainda sem cálculo" not in blocos[MUNICIPIOS[1].ibge]


def test_simulacao_nula_quando_desligada():
    assert montar(simulacao=False)["simulacao"] is None


def test_simulacao_preenchida_quando_ligada():
    simulacao = montar(simulacao=True)["simulacao"]

    assert simulacao["mensagens"] == {
        m.ibge: mensagens_da_simulacao(m, SITE) for m in MUNICIPIOS
    }
    por_municipio = len(mensagens_da_simulacao(MUNICIPIOS[0], SITE))
    assert por_municipio > 0
    assert simulacao["fim"] == texto_de_fim(por_municipio)
    assert simulacao["pausa_s"] == PAUSA_ENTRE_MENSAGENS_S
    assert "{entrada}" in simulacao["municipio_invalido"]
    assert simulacao["municipio_invalido"] == texto_municipio_invalido(
        MUNICIPIOS, ["{entrada}"]
    )


def test_gerado_em_sem_fuso_levanta():
    with pytest.raises(ValueError, match="gerado_em"):
        montar(gerado_em=datetime(2026, 10, 15, 14, 30, 5))


@pytest.mark.parametrize("simulacao", [False, True])
def test_resultado_e_serializavel(simulacao):
    dados = montar(simulacao=simulacao)

    assert json.loads(serializar(dados)) == dados


#: Exemplo que os testes do Worker leem (`bot-worker/test/bot-json.test.ts`): sai
#: de `montar_bot_json`, então um campo renomeado aqui quebra os dois lados.
FIXTURE_DO_WORKER = (
    Path(__file__).resolve().parents[2] / "bot-worker" / "test" / "fixtures" / "bot.exemplo.json"
)


def test_fixture_do_worker_igual_ao_montar_bot_json():
    # Com a simulação ligada, para o Worker ver também o formato do objeto `simulacao`.
    esperado = montar(simulacao=True)
    if os.environ.get("VIGIA_REGERAR_FIXTURES") == "1":
        FIXTURE_DO_WORKER.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE_DO_WORKER.write_bytes(serializar(esperado))

    # Compara o JSON lido, não os bytes: o git pode trocar a quebra de linha no Windows.
    assert json.loads(FIXTURE_DO_WORKER.read_text(encoding="utf-8")) == esperado, (
        "bot.exemplo.json desatualizado: rode `VIGIA_REGERAR_FIXTURES=1 pytest "
        "tests/test_bot_json.py` e commite o arquivo"
    )


def _norm(texto: str) -> str:
    sem = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return " ".join(sem.lower().split())


def test_grupos_na_ordem_do_codigo_da_microrregiao():
    dados = montar()
    grupos = dados["grupos"]
    assert [g["nome"] for g in grupos] == ["Região de Rio do Sul", "Região de Ituporanga"]
    assert sum(len(g["municipios"]) for g in grupos) == 27
    ordem = [m["ibge"] for m in dados["municipios"]]
    for g in grupos:
        assert g["municipios"] == [i for i in ordem if i in set(g["municipios"])]
        assert g["opcao_todos"] == f"Todos da {g['nome']}"


def test_textos_de_grupo():
    dados = montar()
    assert dados["textos"]["opcao_voltar"] == OPCAO_VOLTAR
    assert dados["textos"]["boas_vindas_grupos"] == texto_boas_vindas_grupos()
    ituporanga = dados["grupos"][1]
    nomes = {m["ibge"]: m["nome"] for m in dados["municipios"]}
    assert ituporanga["confirmacao"] == texto_inscricao_confirmada([nomes[i] for i in ituporanga["municipios"]])


def test_rotulos_de_botao_unicos_no_bot_json_inteiro():
    dados = montar()
    rotulos = [m["nome"] for m in dados["municipios"]]
    rotulos += [dados["textos"]["opcao_todos"], dados["textos"]["opcao_voltar"]]
    for g in dados["grupos"]:
        rotulos += [g["nome"], g["opcao_todos"]]
    normalizados = [_norm(r) for r in rotulos]
    assert len(normalizados) == len(set(normalizados))


def test_sem_microrregiao_nao_ha_grupos():
    sem = [dataclasses.replace(m, microrregiao=None) for m in MUNICIPIOS]
    dados = montar_bot_json(sem, {m.ibge: None for m in sem}, SITE, False, GERADO_EM)
    assert "grupos" not in dados
    assert "opcao_voltar" not in dados["textos"]
    assert "boas_vindas_grupos" not in dados["textos"]
