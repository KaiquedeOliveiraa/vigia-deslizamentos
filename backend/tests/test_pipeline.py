"""Testes do pipeline (Tarefa 11): encadeamento com dublês, sem rede.

A coleta e a publicação entram por parâmetro, com os valores de produção como
padrão; aqui são substituídas por dublês. O banco é em memória e o relógio é
injetado — nenhum teste depende do horário real.

As séries são montadas à mão, com os rótulos escritos literalmente, e o índice
de cada município é controlado pelo `rtotal` do membro: com `limiar_mm = 100` e
antecedente zerada, o subíndice é `rtotal / 100`.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.bot.regra_aviso import Aviso
from app.coleta.open_meteo import ColetaError
from app.config import Config, Municipio, Ponto
from app.exportacao.publicar import CAMINHO_NO_REPOSITORIO
from app.modelos import banco
from app.modelos.tipos import DadosMunicipio, Membro
from app.pipeline import Execucao, executar_pipeline
from tests.apoio_schema import carregar_schema, validador_estrito

UTC = timezone.utc
AGORA = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
FIM_DA_EXECUCAO = datetime(2026, 10, 1, 12, 3, 20, tzinfo=UTC)
RODADA = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)
D0 = date(2026, 10, 1)


def config_de_teste() -> Config:
    return Config(
        telegram_token="123:ABC",
        github_token_dados="ghp_x",
        github_repo="dono/repo",
        site_url="https://vigia.exemplo.org",
        db_path=":memory:",
        log_path="vigia.log",
    )


def municipio(ibge: str, nome: str) -> Municipio:
    return Municipio(
        ibge=ibge,
        nome=nome,
        limiar_mm=100.0,
        fonte_limiar="teste",
        mv_h=24.0,
        pontos=(Ponto(lat=-27.0, lon=-49.5),),
    )


IBIRAMA = municipio("4206900", "Ibirama")
DONA_EMMA = municipio("4205100", "Dona Emma")


def _serie(inicio: datetime, horas: int, valor: float = 0.0) -> dict[datetime, float]:
    return {inicio + timedelta(hours=k): valor for k in range(horas)}


def antecedente_zerada() -> dict[datetime, float]:
    """Horas zeradas de 2026-09-24T00:00Z a 2026-10-01T12:00Z (EfR = 0)."""
    return _serie(datetime(2026, 9, 24, 0, 0, tzinfo=UTC), 181)


def previsao(rtotal_d0: float) -> dict[datetime, float]:
    """96 rótulos de 2026-10-01T01:00Z a 2026-10-05T00:00Z, chuva só em D0."""
    serie = _serie(datetime(2026, 10, 1, 1, 0, tzinfo=UTC), 96)
    serie[datetime(2026, 10, 1, 1, 0, tzinfo=UTC)] = rtotal_d0
    return serie


def dados(ibge: str, rtotal_d0: float, rodada: datetime = RODADA) -> DadosMunicipio:
    """Três membros de peso igual, todos com o mesmo `rtotal` em D0."""
    return DadosMunicipio(
        ibge=ibge,
        antecedente=[antecedente_zerada()],
        membros=[
            Membro(modelo=modelo, rodada=rodada, chuva=[previsao(rtotal_d0)])
            for modelo in ("gfs_global", "ecmwf_ifs025", "icon_global")
        ],
    )


def coleta_falsa(por_ibge: dict[str, DadosMunicipio | Exception]):
    """Dublê de `coletar`: devolve ou levanta o que estiver programado por ibge."""

    def coletar(municipio_pedido, agora_utc, http, cache_rodadas=None):
        resposta = por_ibge[municipio_pedido.ibge]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    return coletar


class PublicacaoFalsa:
    """Dublê de `publicar`: guarda o conteúdo recebido e devolve o que for pedido."""

    def __init__(self, devolve: bool = True):
        self.devolve = devolve
        self.conteudos: list[bytes] = []

    def __call__(self, conteudo: bytes, config: Config, http) -> bool:
        self.conteudos.append(conteudo)
        return self.devolve

    @property
    def json_publicado(self) -> dict:
        return json.loads(self.conteudos[-1].decode("utf-8"))


def conexao():
    return banco.abrir(":memory:")


def executar(
    municipios,
    por_ibge,
    conn=None,
    publicacao=None,
    agora=AGORA,
    relogio=lambda: FIM_DA_EXECUCAO,
) -> tuple[Execucao, PublicacaoFalsa, object]:
    conn = conn if conn is not None else conexao()
    publicacao = publicacao or PublicacaoFalsa()
    execucao = executar_pipeline(
        agora,
        municipios,
        conn,
        http=object(),  # nunca usado: coleta e publicação são dublês
        config=config_de_teste(),
        relogio=relogio,
        coletar=coleta_falsa(por_ibge),
        publicar=publicacao,
    )
    return execucao, publicacao, conn


# --- caminho feliz ------------------------------------------------------------


def test_execucao_completa_calcula_grava_publica_e_devolve_os_avisos():
    execucao, publicacao, conn = executar(
        [IBIRAMA, DONA_EMMA],
        {"4206900": dados("4206900", 120.0), "4205100": dados("4205100", 30.0)},
    )

    assert [item.ibge for item in execucao.resultado.municipios] == [
        "4206900",
        "4205100",
    ]
    assert execucao.publicado is True
    assert publicacao.conteudos != []

    # Gravou os 4 dias-alvo de cada município, com o mesmo calculado_em.
    assert conn.execute("SELECT COUNT(*) FROM indices").fetchone()[0] == 8
    assert conn.execute(
        "SELECT DISTINCT calculado_em FROM indices"
    ).fetchall() == [("2026-10-01T12:03:20Z",)]

    # Ibirama: rtotal 120 / limiar 100 = 1,20 (classe 4) -> avisa.
    # Dona Emma: 0,30 (classe 1) -> nada a notificar, nem aviso nem gravação.
    assert [(aviso.ibge, aviso.avisar, aviso.nova_classe) for aviso in execucao.avisos] == [
        ("4206900", True, 4)
    ]


def test_json_publicado_e_valido_pelo_schema_do_contrato():
    _, publicacao, _ = executar(
        [IBIRAMA], {"4206900": dados("4206900", 120.0)}
    )

    validador_estrito(carregar_schema()).validate(publicacao.json_publicado)


def test_gerado_em_vem_do_relogio_injetado_e_nao_de_agora_utc():
    _, publicacao, _ = executar([IBIRAMA], {"4206900": dados("4206900", 120.0)})

    # `agora_utc` é 12:00Z (o instante de referência do cálculo); `gerado_em` é
    # o fim da execução, 12:03:20Z, lido do relógio injetado.
    assert publicacao.json_publicado["gerado_em"] == "2026-10-01T12:03:20+00:00"
    assert publicacao.json_publicado["dia_alvo_d0"] == "2026-10-01"


def test_historico_publicado_vem_do_banco():
    conn = conexao()
    conn.execute(
        "INSERT INTO indices (ibge, dia_alvo, calculado_em, indice, classe, efr_mm, "
        "rtotal_mm, limiar_mm, n_membros, prob_pontuais, prob_esparsos, "
        "prob_generalizados) VALUES "
        "('4206900', '2026-09-30', '2026-09-30T12:00:00Z', 0.8, 3, 0, 0, 100, 3, 0, 0, 0)"
    )
    conn.commit()

    _, publicacao, _ = executar(
        [IBIRAMA], {"4206900": dados("4206900", 120.0)}, conn=conn
    )

    historico = publicacao.json_publicado["municipios"][0]["historico"]
    assert historico == [{"dia_alvo": "2026-09-30", "indice": 0.8, "classe": 3}]


def test_cache_de_rodadas_e_compartilhado_pelos_municipios_da_execucao():
    caches_vistos = []

    def coletar(municipio_pedido, agora_utc, http, cache_rodadas=None):
        caches_vistos.append(cache_rodadas)
        return dados(municipio_pedido.ibge, 120.0)

    executar_pipeline(
        AGORA,
        [IBIRAMA, DONA_EMMA],
        conexao(),
        http=object(),
        config=config_de_teste(),
        relogio=lambda: FIM_DA_EXECUCAO,
        coletar=coletar,
        publicar=PublicacaoFalsa(),
    )

    assert len(caches_vistos) == 2
    assert caches_vistos[0] is not None
    assert caches_vistos[0] is caches_vistos[1]


# --- falha em um município ----------------------------------------------------


def test_falha_de_coleta_num_municipio_manda_so_ele_para_sem_dados():
    execucao, publicacao, _ = executar(
        [IBIRAMA, DONA_EMMA],
        {
            "4206900": ColetaError("município '4206900': rede esgotada"),
            "4205100": dados("4205100", 120.0),
        },
    )

    assert execucao.resultado.municipios_sem_dados == ["4206900"]
    assert [item.ibge for item in execucao.resultado.municipios] == ["4205100"]
    assert execucao.publicado is True
    assert publicacao.json_publicado["municipios_sem_dados"] == ["4206900"]


def test_falha_de_calculo_num_municipio_manda_so_ele_para_sem_dados():
    # Rodada fora dos horários sinóticos: falha de cálculo, não de coleta.
    execucao, _, _ = executar(
        [IBIRAMA, DONA_EMMA],
        {
            "4206900": dados(
                "4206900", 120.0, rodada=datetime(2026, 10, 1, 3, 0, tzinfo=UTC)
            ),
            "4205100": dados("4205100", 120.0),
        },
    )

    assert execucao.resultado.municipios_sem_dados == ["4206900"]
    assert [item.ibge for item in execucao.resultado.municipios] == ["4205100"]


def test_erro_inesperado_na_coleta_de_um_municipio_nao_derruba_a_execucao():
    execucao, _, _ = executar(
        [IBIRAMA, DONA_EMMA],
        {"4206900": RuntimeError("defeito inesperado"), "4205100": dados("4205100", 120.0)},
    )

    assert execucao.resultado.municipios_sem_dados == ["4206900"]
    assert [item.ibge for item in execucao.resultado.municipios] == ["4205100"]


# --- falha geral --------------------------------------------------------------


def test_falha_geral_nao_grava_nao_publica_e_nao_avisa():
    publicacao = PublicacaoFalsa()

    execucao, publicacao, conn = executar(
        [IBIRAMA, DONA_EMMA],
        {
            "4206900": ColetaError("sem rede"),
            "4205100": ColetaError("sem rede"),
        },
        publicacao=publicacao,
    )

    assert execucao.resultado.municipios == []
    assert execucao.resultado.municipios_sem_dados == ["4206900", "4205100"]
    assert execucao.publicado is False
    # UC06: o último JSON publicado continua no ar — nada é enviado.
    assert publicacao.conteudos == []
    assert conn.execute("SELECT COUNT(*) FROM indices").fetchone()[0] == 0
    assert execucao.avisos == []


def test_falha_geral_nao_apaga_a_classe_notificada_anterior():
    conn = conexao()
    banco.atualizar_ultima_classe_notificada(conn, "4206900", 4, AGORA)

    execucao, _, conn = executar(
        [IBIRAMA], {"4206900": ColetaError("sem rede")}, conn=conn
    )

    assert execucao.avisos == []
    assert banco.ultima_classe_notificada(conn, "4206900") == 4


# --- falha na publicação ------------------------------------------------------


def test_falha_na_publicacao_nao_impede_os_avisos():
    execucao, publicacao, conn = executar(
        [IBIRAMA],
        {"4206900": dados("4206900", 120.0)},
        publicacao=PublicacaoFalsa(devolve=False),
    )

    assert execucao.publicado is False
    assert [aviso.avisar for aviso in execucao.avisos] == [True]
    # E os dados foram gravados: a publicação é o último elo, não o primeiro.
    assert conn.execute("SELECT COUNT(*) FROM indices").fetchone()[0] == 4


# --- decisão dos avisos -------------------------------------------------------


def test_apenas_o_d0_gera_aviso_mesmo_com_d1_em_classe_alta():
    # D0 em classe 2 (0,50) e D1 em classe 6 (3,00): nenhum aviso. Os dias
    # D1–D3 são previsão (RN06) e não disparam notificação.
    antecedente = antecedente_zerada()
    serie_previsao = previsao(50.0)
    serie_previsao[datetime(2026, 10, 2, 1, 0, tzinfo=UTC)] = 300.0
    dados_do_municipio = DadosMunicipio(
        ibge="4206900",
        antecedente=[antecedente],
        membros=[
            Membro(modelo=modelo, rodada=RODADA, chuva=[dict(serie_previsao)])
            for modelo in ("gfs_global", "ecmwf_ifs025", "icon_global")
        ],
    )

    execucao, _, _ = executar([IBIRAMA], {"4206900": dados_do_municipio})

    dias = execucao.resultado.municipios[0].dias
    assert dias[0].classe == 2
    assert dias[1].classe == 6
    assert execucao.avisos == []


def test_municipio_sem_dados_sem_classe_anterior_nao_gera_aviso():
    execucao, _, _ = executar(
        [IBIRAMA, DONA_EMMA],
        {"4206900": ColetaError("sem rede"), "4205100": dados("4205100", 30.0)},
    )

    assert execucao.avisos == []


def test_segunda_execucao_na_mesma_classe_nao_gera_aviso_novo():
    conn = conexao()
    por_ibge = {"4206900": dados("4206900", 120.0)}

    primeira, _, conn = executar([IBIRAMA], por_ibge, conn=conn)
    assert [aviso.avisar for aviso in primeira.avisos] == [True]

    # O envio é que grava a classe notificada (Tarefa 10); aqui gravamos direto
    # para reproduzir o estado depois de um envio bem-sucedido.
    banco.atualizar_ultima_classe_notificada(conn, "4206900", 4, AGORA)

    segunda, _, conn = executar([IBIRAMA], por_ibge, conn=conn)

    assert segunda.avisos == []


def test_subir_de_classe_entre_execucoes_gera_aviso_novo():
    conn = conexao()
    primeira, _, conn = executar(
        [IBIRAMA], {"4206900": dados("4206900", 120.0)}, conn=conn
    )
    banco.atualizar_ultima_classe_notificada(conn, "4206900", 4, AGORA)

    segunda, _, conn = executar(
        [IBIRAMA], {"4206900": dados("4206900", 200.0)}, conn=conn
    )

    assert [(aviso.avisar, aviso.nova_classe) for aviso in segunda.avisos] == [(True, 5)]


def test_sair_de_alerta_gera_entrada_para_zerar_a_classe_sem_enviar_mensagem():
    conn = conexao()
    banco.atualizar_ultima_classe_notificada(conn, "4206900", 4, AGORA)

    execucao, _, conn = executar(
        [IBIRAMA], {"4206900": dados("4206900", 50.0)}, conn=conn
    )

    (aviso,) = execucao.avisos
    assert aviso.avisar is False
    assert aviso.nova_classe is None


def test_aviso_leva_o_nome_do_municipio_e_o_indice_do_d0():
    execucao, _, _ = executar([IBIRAMA], {"4206900": dados("4206900", 120.0)})

    (aviso,) = execucao.avisos
    assert isinstance(aviso, Aviso)
    assert aviso.nome == "Ibirama"
    assert aviso.indice == pytest.approx(1.20)
    assert aviso.classe == 4


# --- ponta a ponta ------------------------------------------------------------


def test_ponta_a_ponta_com_banco_em_memoria_e_publicacao_real_simulada():
    """Execução inteira: histórico do banco, JSON válido, avisos esperados.

    A publicação usa o `publicar` de verdade com um cliente HTTP falso, para
    que o encadeamento completo (serializar -> PUT) seja exercido.
    """
    conn = conexao()
    for dia, indice, classe_do_dia in (
        ("2026-09-29", 0.4, 2),
        ("2026-09-30", 0.8, 3),
    ):
        conn.execute(
            "INSERT INTO indices (ibge, dia_alvo, calculado_em, indice, classe, "
            "efr_mm, rtotal_mm, limiar_mm, n_membros, prob_pontuais, prob_esparsos, "
            "prob_generalizados) VALUES (?, ?, ?, ?, ?, 0, 0, 100, 3, 0, 0, 0)",
            ("4206900", dia, f"{dia}T12:00:00Z", indice, classe_do_dia),
        )
    conn.commit()
    banco.inscrever(conn, 777, "4206900", AGORA)

    class RespostaFalsa:
        def __init__(self, status_code, corpo):
            self.status_code = status_code
            self._corpo = corpo
            self.text = json.dumps(corpo)

        def json(self):
            return self._corpo

    class HttpFalso:
        def __init__(self):
            self.puts = []

        def get(self, url, **kwargs):
            return RespostaFalsa(200, {"sha": "sha_atual"})

        def put(self, url, **kwargs):
            self.puts.append((url, kwargs))
            return RespostaFalsa(200, {})

    http = HttpFalso()
    execucao = executar_pipeline(
        AGORA,
        [IBIRAMA, DONA_EMMA],
        conn,
        http=http,
        config=config_de_teste(),
        relogio=lambda: FIM_DA_EXECUCAO,
        coletar=coleta_falsa(
            {
                "4206900": dados("4206900", 120.0),
                "4205100": ColetaError("município '4205100': rede esgotada"),
            }
        ),
    )

    assert execucao.publicado is True
    (url_put, kwargs_put), = http.puts
    assert CAMINHO_NO_REPOSITORIO in url_put

    import base64

    publicado = json.loads(base64.b64decode(kwargs_put["json"]["content"]).decode("utf-8"))
    validador_estrito(carregar_schema()).validate(publicado)
    assert publicado["municipios_sem_dados"] == ["4205100"]
    assert publicado["municipios"][0]["historico"] == [
        {"dia_alvo": "2026-09-29", "indice": 0.4, "classe": 2},
        {"dia_alvo": "2026-09-30", "indice": 0.8, "classe": 3},
    ]
    assert publicado["municipios"][0]["limiar_mm"] == 100.0
    assert [dia["d"] for dia in publicado["municipios"][0]["dias"]] == [0, 1, 2, 3]

    assert [(aviso.ibge, aviso.avisar, aviso.nova_classe) for aviso in execucao.avisos] == [
        ("4206900", True, 4)
    ]
