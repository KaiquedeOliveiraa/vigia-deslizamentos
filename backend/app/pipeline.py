"""Uma execução do pipeline: coleta, cálculo, gravação, publicação e decisão dos avisos.

Síncrona de propósito: é chamada de uma thread de trabalho pelo agendador
(`app/main.py`), enquanto o bot segue atendendo no loop asyncio. O **envio** dos
avisos não acontece aqui — `executar_pipeline` devolve a lista de `Aviso` e quem
envia é `app.bot.avisos.enviar_avisos`, no loop, com o `telegram.Bot`.

Toda dependência entra por parâmetro, inclusive a função de coleta e a de
publicação: os padrões são as de produção, e os testes as substituem por dublês.

Ordem e tolerância a falhas:

1. coleta, município por município — uma falha manda **só** aquele município
   para `municipios_sem_dados`;
2. cálculo (`calcular` também isola falha de domínio por município);
3. se nenhum município foi calculado, a execução para aqui: não grava, não
   publica e não avisa. O último `indices.json` continua no ar (UC06/RNF04) e a
   última classe notificada de cada município fica intacta;
4. gravação no banco, numa transação;
5. exportação e publicação — falha aqui é registrada e **não** impede os avisos,
   inclusive se vier como exceção em vez de `False`;
6. comparação de conferência com o INMET, que só escreve no log;
7. decisão dos avisos pela RN08;
8. gravação do `bot.json` (se configurado) — falha é registrada e não para a
   execução.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.bot.regra_aviso import Aviso, decidir
from app.calculo.agregacao import Resultado, calcular
from app.coleta import inmet, open_meteo
from app.config import Config, Municipio
from app.exportacao.bot_json import montar_bot_json
from app.exportacao.exportar import montar_indices, serializar
from app.exportacao.publicar import publicar as publicar_indices
from app.modelos import banco
from app.modelos.tipos import DadosMunicipio

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Execucao:
    """O que uma execução produziu, para o chamador registrar e enviar."""

    resultado: Resultado
    publicado: bool
    avisos: list[Aviso]


def _coletar_todos(
    municipios: list[Municipio],
    agora_utc: datetime,
    http,
    coletar: Callable[..., DadosMunicipio],
) -> dict[str, DadosMunicipio]:
    """Coleta cada município, pulando os que falharem.

    O município que falha simplesmente não entra no dicionário, e `calcular` o
    manda para `municipios_sem_dados` por não ter dados — não há duas listas
    para manter em sincronia.

    `except Exception` aqui é deliberado: a coleta fala com a rede e com corpos
    de resposta de terceiros, e uma exceção inesperada num município não pode
    custar a execução dos outros cinco. O erro vai para o log com o município
    identificado. Os outros quatro do backend têm a mesma forma — absorver uma
    falha cuja alternativa seria perder um aviso ou uma execução inteira — e
    estão em `executar_pipeline` (publicação), `app.bot.avisos.enviar_avisos`
    (por município), `app.coleta.inmet.registrar_comparacao_24h` (conferência) e
    `app.main` (o job agendado).

    `cache_rodadas` é criado aqui, uma vez por execução: o horário de
    inicialização de cada modelo é o mesmo para todos os municípios.
    """
    cache_rodadas: dict[str, datetime] = {}
    coletados: dict[str, DadosMunicipio] = {}

    for municipio in municipios:
        try:
            coletados[municipio.ibge] = coletar(
                municipio, agora_utc, http, cache_rodadas=cache_rodadas
            )
        except Exception as erro:  # noqa: BLE001 — ver docstring
            _log.error(
                "coleta do município '%s' (%s) falhou: %s",
                municipio.ibge,
                municipio.nome,
                erro,
            )

    return coletados


def _decidir_avisos(
    conexao: sqlite3.Connection,
    municipios: list[Municipio],
    resultado: Resultado,
    calculado_em: datetime,
) -> list[Aviso]:
    """Aplica a RN08 a cada município e devolve só o que tem algo a fazer.

    Entram na lista os municípios que geram mensagem (`avisar = True`) e os que
    precisam de uma gravação de estado — sair de alerta zera a classe, e isso
    tem de ser persistido mesmo sem mensagem. Município em que nada muda fica de
    fora, para não gastar uma escrita por execução em cada um dos seis.

    Só o D0 entra na decisão: D1–D3 são previsão (RN06) e não disparam aviso.
    """
    d0_por_ibge = {item.ibge: item.dias[0] for item in resultado.municipios}

    avisos: list[Aviso] = []
    for municipio in municipios:
        d0 = d0_por_ibge.get(municipio.ibge)
        indice_d0 = d0.indice if d0 is not None else None
        ultima_classe = banco.ultima_classe_notificada(conexao, municipio.ibge)
        avisar, nova_classe = decidir(ultima_classe, indice_d0)

        if not avisar and nova_classe == ultima_classe:
            continue

        avisos.append(
            Aviso(
                ibge=municipio.ibge,
                nome=municipio.nome,
                indice=indice_d0,
                classe=d0.classe if d0 is not None else None,
                avisar=avisar,
                nova_classe=nova_classe,
                efr_mm=d0.efr_mm if d0 is not None else None,
                rtotal_mm=d0.rtotal_mm if d0 is not None else None,
                dia_alvo=d0.dia_alvo if d0 is not None else None,
                calculado_em=calculado_em if d0 is not None else None,
            )
        )

    return avisos


def _publicar_indices(
    resultado: Resultado,
    municipios: list[Municipio],
    conexao: sqlite3.Connection,
    config: Config,
    http,
    gerado_em: datetime,
    publicar: Callable[[bytes, Config, object], bool],
) -> bool:
    historicos = {
        item.ibge: banco.historico(
            conexao, item.ibge, resultado.dia_alvo_d0, item.limiar_mm
        )
        for item in resultado.municipios
    }
    dados = montar_indices(resultado, municipios, historicos, gerado_em)
    return publicar(serializar(dados), config, http)


def _gravar_bot_json(
    municipios: list[Municipio],
    conexao: sqlite3.Connection,
    config: Config,
    gerado_em: datetime,
) -> None:
    atuais = {
        municipio.ibge: banco.indice_atual(conexao, municipio.ibge)
        for municipio in municipios
    }
    dados = montar_bot_json(
        municipios, atuais, config.site_url, config.simulacao, gerado_em
    )
    caminho = Path(config.bot_json_path)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(serializar(dados))


def executar_pipeline(
    agora_utc: datetime,
    municipios: list[Municipio],
    conexao: sqlite3.Connection,
    http,
    config: Config,
    *,
    relogio: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    coletar: Callable[..., DadosMunicipio] = open_meteo.coletar,
    publicar: Callable[[bytes, Config, object], bool] = publicar_indices,
    comparar_com_inmet: Callable[..., None] = inmet.registrar_comparacao_24h,
) -> Execucao:
    """Roda uma execução completa e devolve o que ela produziu.

    `agora_utc` é o instante de referência do cálculo (define o D0 e os pesos das
    rodadas); `relogio()` é lido **depois** do cálculo e dá o fim da execução,
    usado como `calculado_em` no banco e `gerado_em` no JSON — o mesmo valor nos
    dois, para que o histórico e o arquivo publicado concordem.

    Não levanta exceção por falha de um município nem por falha de publicação. A
    conexão SQLite tem de ser a desta thread.
    """
    coletados = _coletar_todos(municipios, agora_utc, http, coletar)
    resultado = calcular(municipios, coletados, agora_utc)

    if not resultado.municipios:
        _log.error(
            "nenhum município calculado nesta execução (%s sem dados): "
            "nada gravado, nada publicado, nenhum aviso",
            len(resultado.municipios_sem_dados),
        )
        return Execucao(resultado=resultado, publicado=False, avisos=[])

    fim_da_execucao = relogio()
    banco.gravar_resultado(conexao, resultado, fim_da_execucao)

    # `publicar` promete nunca levantar, mas essa promessa é de um módulo e a
    # invariante é daqui: entre a gravação e a decisão dos avisos, uma exceção
    # custaria o aviso de um município em alerta pelas próximas 6 h, em
    # silêncio. A guarda torna a invariante estrutural.
    try:
        publicado = _publicar_indices(
            resultado, municipios, conexao, config, http, fim_da_execucao, publicar
        )
    except Exception:  # noqa: BLE001 — publicação nunca impede os avisos
        _log.exception("publicação falhou com exceção; a execução segue sem publicar")
        publicado = False

    # Conferência: a diferença entre a chuva medida pela estação do INMET e a
    # calculada vai para o log e não toca no índice. O `try` é redundante com o
    # tratamento interno da função, e está aqui de propósito: se a comparação
    # for trocada por outra implementação, o pipeline continua não caindo por
    # causa dela.
    try:
        comparar_com_inmet(resultado, agora_utc, http, config)
    except Exception:  # noqa: BLE001 — conferência nunca derruba a execução
        _log.exception("comparação com o INMET falhou; a execução segue")

    avisos = _decidir_avisos(conexao, municipios, resultado, fim_da_execucao)

    # Mesma razão da guarda da publicação: o `bot.json` é um extra do Worker e
    # não pode custar os avisos que já estão decididos.
    if config.bot_json_path is not None:
        try:
            _gravar_bot_json(municipios, conexao, config, fim_da_execucao)
        except Exception:  # noqa: BLE001 — bot.json nunca impede os avisos
            _log.exception("gravação do bot.json falhou; a execução segue")

    _log.info(
        "execução de %s: %s município(s) com dados, %s sem dados, publicado=%s, "
        "%s aviso(s) a tratar",
        fim_da_execucao.isoformat(),
        len(resultado.municipios),
        len(resultado.municipios_sem_dados),
        publicado,
        len(avisos),
    )
    return Execucao(resultado=resultado, publicado=publicado, avisos=avisos)
