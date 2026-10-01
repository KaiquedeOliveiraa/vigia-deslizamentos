"""Testes de carregamento de configuração: municípios, ambiente e schema do indices.json."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from app.config import (
    Config,
    ConfiguracaoInvalidaError,
    Municipio,
    Ponto,
    carregar_env,
    carregar_municipios,
)

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
CAMINHO_MUNICIPIOS = RAIZ_BACKEND / "config" / "municipios.json"
CAMINHO_SCHEMA = RAIZ_BACKEND.parent / "docs" / "indices.schema.json"


# --- carregar_municipios -----------------------------------------------------


def test_carregar_municipios_retorna_todos_os_municipios_configurados():
    municipios = carregar_municipios(CAMINHO_MUNICIPIOS)

    assert len(municipios) == 6
    ibges = {municipio.ibge for municipio in municipios}
    assert len(ibges) == 6  # nenhum código repetido

    for municipio in municipios:
        assert isinstance(municipio, Municipio)
        assert len(municipio.ibge) == 7 and municipio.ibge.isdigit()
        assert municipio.limiar_mm > 0
        assert municipio.mv_h > 0
        assert len(municipio.pontos) >= 1
        for ponto in municipio.pontos:
            assert isinstance(ponto, Ponto)


def test_municipio_e_imutavel():
    municipios = carregar_municipios(CAMINHO_MUNICIPIOS)

    with pytest.raises(Exception):
        municipios[0].nome = "Outro nome"


def _escrever_municipios(tmp_path: Path, dados) -> Path:
    caminho = tmp_path / "municipios.json"
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return caminho


def test_campo_faltando_levanta_erro_com_nome_do_campo(tmp_path):
    dados = [
        {
            "ibge": "4205100",
            "nome": "Dona Emma",
            "fonte_limiar": "GeoRisk, limiar hipotético padrão",
            "mv_h": 24,
            "pontos": [{"lat": -26.9887, "lon": -49.7781}],
            # "limiar_mm" ausente de propósito
        }
    ]
    caminho = _escrever_municipios(tmp_path, dados)

    with pytest.raises(ConfiguracaoInvalidaError, match="limiar_mm"):
        carregar_municipios(caminho)


def test_ibge_repetido_levanta_erro(tmp_path):
    municipio_base = {
        "ibge": "4205100",
        "nome": "Dona Emma",
        "limiar_mm": 250,
        "fonte_limiar": "GeoRisk, limiar hipotético padrão",
        "mv_h": 24,
        "pontos": [{"lat": -26.9887, "lon": -49.7781}],
    }
    dados = [municipio_base, dict(municipio_base, nome="Duplicado")]
    caminho = _escrever_municipios(tmp_path, dados)

    with pytest.raises(ConfiguracaoInvalidaError, match="4205100"):
        carregar_municipios(caminho)


def test_limiar_mm_nao_positivo_levanta_erro(tmp_path):
    dados = [
        {
            "ibge": "4205100",
            "nome": "Dona Emma",
            "limiar_mm": 0,
            "fonte_limiar": "GeoRisk, limiar hipotético padrão",
            "mv_h": 24,
            "pontos": [{"lat": -26.9887, "lon": -49.7781}],
        }
    ]
    caminho = _escrever_municipios(tmp_path, dados)

    with pytest.raises(ConfiguracaoInvalidaError, match="limiar_mm"):
        carregar_municipios(caminho)


def test_sem_nenhum_ponto_levanta_erro(tmp_path):
    dados = [
        {
            "ibge": "4205100",
            "nome": "Dona Emma",
            "limiar_mm": 250,
            "fonte_limiar": "GeoRisk, limiar hipotético padrão",
            "mv_h": 24,
            "pontos": [],
        }
    ]
    caminho = _escrever_municipios(tmp_path, dados)

    with pytest.raises(ConfiguracaoInvalidaError, match="pontos"):
        carregar_municipios(caminho)


# --- carregar_env -------------------------------------------------------------

AMBIENTE_VALIDO = {
    "TELEGRAM_TOKEN": "token-telegram-123",
    "GITHUB_TOKEN_DADOS": "token-github-456",
    "GITHUB_REPO": "usuario/repo",
    "SITE_URL": "https://exemplo.org",
    "DB_PATH": "/var/dados/vigia.db",
    "LOG_PATH": "/var/log/vigia.log",
}


def test_carregar_env_com_todas_variaveis_retorna_config():
    config = carregar_env(AMBIENTE_VALIDO)

    assert isinstance(config, Config)
    assert config.TELEGRAM_TOKEN == "token-telegram-123"
    assert config.GITHUB_TOKEN_DADOS == "token-github-456"
    assert config.GITHUB_REPO == "usuario/repo"
    assert config.SITE_URL == "https://exemplo.org"
    assert config.DB_PATH == "/var/dados/vigia.db"
    assert config.LOG_PATH == "/var/log/vigia.log"


def test_carregar_env_sem_variavel_obrigatoria_levanta_erro_com_seu_nome_sem_vazar_outro_valor():
    ambiente = dict(AMBIENTE_VALIDO)
    ambiente["GITHUB_TOKEN_DADOS"] = "segredo-de-outra-variavel-que-nao-pode-vazar"
    del ambiente["TELEGRAM_TOKEN"]

    with pytest.raises(ConfiguracaoInvalidaError) as excinfo:
        carregar_env(ambiente)

    mensagem = str(excinfo.value)
    assert "TELEGRAM_TOKEN" in mensagem
    assert "segredo-de-outra-variavel-que-nao-pode-vazar" not in mensagem


# --- docs/indices.schema.json --------------------------------------------------


def _carregar_schema():
    return json.loads(CAMINHO_SCHEMA.read_text(encoding="utf-8"))


EXEMPLO_MINIMO_VALIDO = {
    "schema_version": 1,
    "gerado_em": "2026-09-30T12:00:00Z",
    "dia_alvo_d0": "2026-09-30",
    "municipios_sem_dados": [],
    "municipios": [
        {
            "ibge": "4205100",
            "nome": "Dona Emma",
            "limiar_mm": 250,
            "fonte_limiar": "GeoRisk, limiar hipotético padrão",
            "mv_h": 24,
            "dias": [
                {
                    "dia_alvo": "2026-09-30",
                    "d": 0,
                    "indice": 1.05,
                    "classe": 4,
                    "efr_mm": 12.3,
                    "rtotal_mm": 45.6,
                    "n_membros": 4,
                    "prob": {"pontuais": 0.8, "esparsos": 0.2, "generalizados": 0.0},
                }
            ],
            "historico": [{"dia_alvo": "2026-09-29", "indice": 0.9, "classe": 3}],
            "chuva_acum_mm": {"24h": 10.0, "48h": 20.0, "72h": 30.0, "96h": 40.0},
        }
    ],
}


def test_schema_aceita_exemplo_minimo_valido():
    schema = _carregar_schema()
    jsonschema.validate(instance=EXEMPLO_MINIMO_VALIDO, schema=schema)


def test_schema_rejeita_exemplo_sem_dia_alvo_d0():
    schema = _carregar_schema()
    exemplo = copy.deepcopy(EXEMPLO_MINIMO_VALIDO)
    del exemplo["dia_alvo_d0"]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=exemplo, schema=schema)


def test_schema_rejeita_schema_version_diferente_de_1():
    schema = _carregar_schema()
    exemplo = copy.deepcopy(EXEMPLO_MINIMO_VALIDO)
    exemplo["schema_version"] = 2

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=exemplo, schema=schema)


def test_schema_rejeita_classe_fora_da_faixa_de_1_a_7():
    schema = _carregar_schema()
    exemplo = copy.deepcopy(EXEMPLO_MINIMO_VALIDO)
    exemplo["municipios"][0]["dias"][0]["classe"] = 8

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=exemplo, schema=schema)


def test_schema_rejeita_probabilidade_fora_da_faixa_de_0_a_1():
    schema = _carregar_schema()
    exemplo = copy.deepcopy(EXEMPLO_MINIMO_VALIDO)
    exemplo["municipios"][0]["dias"][0]["prob"]["pontuais"] = 1.5

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=exemplo, schema=schema)


def test_schema_rejeita_chuva_acum_mm_sem_a_chave_96h():
    schema = _carregar_schema()
    exemplo = copy.deepcopy(EXEMPLO_MINIMO_VALIDO)
    del exemplo["municipios"][0]["chuva_acum_mm"]["96h"]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=exemplo, schema=schema)
