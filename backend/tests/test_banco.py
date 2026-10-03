"""Testes da persistência em SQLite (Tarefa 7): índices calculados, inscritos
do bot e controle de notificações.

A maioria dos testes usa banco em memória (`abrir(":memory:")`); só o teste de
concorrência usa arquivo temporário (`tmp_path`). Os casos de borda de
`historico()` inserem linhas direto com SQL, com `dia_alvo` e `calculado_em`
escritos literalmente — não usam `gravar_resultado()` para montar a própria
entrada.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

import pytest

from app.calculo.agregacao import Resultado, ResultadoDia, ResultadoMunicipio
from app.classificacao.probabilidades import Probabilidades
from app.modelos import banco

UTC = timezone.utc


def _conexao() -> sqlite3.Connection:
    return banco.abrir(":memory:")


# --- abrir e schema -----------------------------------------------------------


def test_abrir_cria_as_tres_tabelas():
    conexao = _conexao()

    tabelas = {
        linha[0]
        for linha in conexao.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    assert {"indices", "inscritos", "notificacoes"} <= tabelas


def test_abrir_e_idempotente_sobre_o_mesmo_arquivo(tmp_path):
    caminho = str(tmp_path / "vigia.sqlite3")

    primeira = banco.abrir(caminho)
    primeira.close()
    segunda = banco.abrir(caminho)  # não pode falhar por tabela já existir
    segunda.close()


# --- gravar_resultado -----------------------------------------------------


def _resultado_de_um_municipio(ibge: str = "4202404") -> Resultado:
    """Um `Resultado` com um município e dois dias-alvo (D0 e D1).

    Valores inventados, só para exercitar a gravação — os literais importam
    apenas para conferir que cada coluna chegou ao banco com o valor certo.
    """
    dias = (
        ResultadoDia(
            dia_alvo=date(2026, 10, 1),
            d=0,
            indice=1.05,
            classe=4,
            efr_mm=52.0,
            rtotal_mm=105.0,
            n_membros=4,
            prob=Probabilidades(pontuais=0.5, esparsos=0.25, generalizados=0.0),
        ),
        ResultadoDia(
            dia_alvo=date(2026, 10, 2),
            d=1,
            indice=0.60,
            classe=3,
            efr_mm=30.0,
            rtotal_mm=40.0,
            n_membros=3,
            prob=Probabilidades(pontuais=0.0, esparsos=0.0, generalizados=0.0),
        ),
    )
    return Resultado(
        dia_alvo_d0=date(2026, 10, 1),
        municipios=[
            ResultadoMunicipio(
                ibge=ibge, limiar_mm=250.0, dias=dias, chuva_acum_mm={"24h": 10.0}
            )
        ],
        municipios_sem_dados=[],
    )


def test_gravar_resultado_grava_uma_linha_por_dia_alvo_com_os_valores_do_resultado():
    conexao = _conexao()
    resultado = _resultado_de_um_municipio()
    calculado_em = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)

    banco.gravar_resultado(conexao, resultado, calculado_em)

    linhas = conexao.execute(
        "SELECT ibge, dia_alvo, calculado_em, indice, classe, efr_mm, rtotal_mm, "
        "n_membros, prob_pontuais, prob_esparsos, prob_generalizados "
        "FROM indices ORDER BY dia_alvo"
    ).fetchall()

    assert linhas == [
        (
            "4202404",
            "2026-10-01",
            "2026-10-01T06:00:00Z",
            1.05,
            4,
            52.0,
            105.0,
            4,
            0.5,
            0.25,
            0.0,
        ),
        (
            "4202404",
            "2026-10-02",
            "2026-10-01T06:00:00Z",
            0.60,
            3,
            30.0,
            40.0,
            3,
            0.0,
            0.0,
            0.0,
        ),
    ]


def test_gravar_resultado_grava_o_limiar_usado_no_calculo():
    # A coluna `limiar_mm` existe para registrar com que limiar cada linha foi
    # calculada; gravá-la como NULL perderia essa informação logo na execução
    # em que ela importa.
    conexao = _conexao()

    banco.gravar_resultado(
        conexao, _resultado_de_um_municipio(), datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
    )

    limiares = [
        linha[0]
        for linha in conexao.execute("SELECT limiar_mm FROM indices").fetchall()
    ]
    assert limiares == [250.0, 250.0]


def test_gravar_resultado_repetido_com_mesmo_calculado_em_nao_duplica_linhas():
    conexao = _conexao()
    resultado = _resultado_de_um_municipio()
    calculado_em = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)

    banco.gravar_resultado(conexao, resultado, calculado_em)
    banco.gravar_resultado(conexao, resultado, calculado_em)

    quantidade = conexao.execute("SELECT COUNT(*) FROM indices").fetchone()[0]
    assert quantidade == 2  # dois dias-alvo, não quatro


def test_gravar_resultado_com_calculado_em_sem_fuso_levanta_erro():
    conexao = _conexao()
    resultado = _resultado_de_um_municipio()

    with pytest.raises(ValueError):
        banco.gravar_resultado(conexao, resultado, datetime(2026, 10, 1, 6, 0))


# --- historico --------------------------------------------------------------


def _inserir_calculo(
    conexao: sqlite3.Connection,
    ibge: str,
    dia_alvo: str,
    calculado_em: str,
    indice: float,
    classe: int,
) -> None:
    """Insere uma linha em `indices` direto por SQL, com literais.

    Usado só para montar os casos de borda de `historico()`, para não
    depender de `gravar_resultado()` (testaria as duas funções juntas).
    """
    conexao.execute(
        "INSERT INTO indices (ibge, dia_alvo, calculado_em, indice, classe, "
        "efr_mm, rtotal_mm, limiar_mm, n_membros, prob_pontuais, prob_esparsos, "
        "prob_generalizados) VALUES (?, ?, ?, ?, ?, 0, 0, 250, 1, 0, 0, 0)",
        (ibge, dia_alvo, calculado_em, indice, classe),
    )
    conexao.commit()


def test_historico_pega_o_calculo_de_maior_calculado_em_do_mesmo_dia_alvo():
    conexao = _conexao()
    _inserir_calculo(conexao, "4202404", "2026-09-30", "2026-09-30T06:00:00Z", 1.0, 4)
    _inserir_calculo(conexao, "4202404", "2026-09-30", "2026-09-30T12:00:00Z", 1.5, 5)

    resultado = banco.historico(conexao, "4202404", date(2026, 10, 1))

    assert resultado == [banco.ItemHistorico(date(2026, 9, 30), 1.5, 5)]


def test_historico_ignora_dia_alvo_sem_nenhum_calculo():
    conexao = _conexao()
    _inserir_calculo(conexao, "4202404", "2026-09-28", "2026-09-28T06:00:00Z", 0.5, 2)
    # 2026-09-29 não tem nenhuma linha: tem de ficar fora, sem buraco nem nulo
    _inserir_calculo(conexao, "4202404", "2026-09-30", "2026-09-30T06:00:00Z", 0.8, 3)

    resultado = banco.historico(conexao, "4202404", date(2026, 10, 1), dias=3)

    assert resultado == [
        banco.ItemHistorico(date(2026, 9, 28), 0.5, 2),
        banco.ItemHistorico(date(2026, 9, 30), 0.8, 3),
    ]


def test_historico_nao_inclui_d0():
    conexao = _conexao()
    dia_alvo_d0 = date(2026, 10, 1)
    _inserir_calculo(conexao, "4202404", "2026-10-01", "2026-10-01T06:00:00Z", 1.0, 4)

    resultado = banco.historico(conexao, "4202404", dia_alvo_d0)

    assert resultado == []


def test_historico_nao_inclui_dia_futuro_ao_d0():
    conexao = _conexao()
    dia_alvo_d0 = date(2026, 10, 1)
    _inserir_calculo(conexao, "4202404", "2026-10-02", "2026-10-01T06:00:00Z", 1.0, 4)

    resultado = banco.historico(conexao, "4202404", dia_alvo_d0)

    assert resultado == []


def test_historico_vai_do_mais_antigo_ao_mais_recente():
    conexao = _conexao()
    _inserir_calculo(conexao, "4202404", "2026-09-29", "2026-09-29T06:00:00Z", 0.3, 2)
    _inserir_calculo(conexao, "4202404", "2026-09-30", "2026-09-30T06:00:00Z", 0.4, 2)

    resultado = banco.historico(conexao, "4202404", date(2026, 10, 1))

    assert resultado == [
        banco.ItemHistorico(date(2026, 9, 29), 0.3, 2),
        banco.ItemHistorico(date(2026, 9, 30), 0.4, 2),
    ]


def test_historico_borda_d0_menos_15_entra_d0_menos_16_nao_entra():
    conexao = _conexao()
    dia_alvo_d0 = date(2026, 10, 16)
    _inserir_calculo(conexao, "4202404", "2026-10-01", "2026-10-01T06:00:00Z", 0.1, 1)  # D0 - 15
    _inserir_calculo(conexao, "4202404", "2026-09-30", "2026-09-30T06:00:00Z", 0.2, 1)  # D0 - 16

    resultado = banco.historico(conexao, "4202404", dia_alvo_d0)

    assert resultado == [banco.ItemHistorico(date(2026, 10, 1), 0.1, 1)]


def test_historico_nao_mistura_municipios():
    conexao = _conexao()
    _inserir_calculo(conexao, "4202404", "2026-09-30", "2026-09-30T06:00:00Z", 1.0, 4)
    _inserir_calculo(conexao, "4205407", "2026-09-30", "2026-09-30T06:00:00Z", 2.0, 6)

    resultado = banco.historico(conexao, "4202404", date(2026, 10, 1))

    assert resultado == [banco.ItemHistorico(date(2026, 9, 30), 1.0, 4)]


# --- indice_atual -------------------------------------------------------------


def test_indice_atual_devolve_o_d0_do_calculo_mais_recente():
    conexao = _conexao()
    # execução mais antiga: D0 e D1
    _inserir_calculo(conexao, "4202404", "2026-10-01", "2026-10-01T00:00:00Z", 1.0, 4)
    _inserir_calculo(conexao, "4202404", "2026-10-02", "2026-10-01T00:00:00Z", 0.5, 2)
    # execução mais recente: D0 e D1 (o D0 muda de dia-alvo)
    _inserir_calculo(conexao, "4202404", "2026-10-02", "2026-10-01T06:00:00Z", 1.8, 5)
    _inserir_calculo(conexao, "4202404", "2026-10-03", "2026-10-01T06:00:00Z", 0.9, 3)

    atual = banco.indice_atual(conexao, "4202404")

    assert atual == banco.IndiceAtual(
        indice=1.8,
        classe=5,
        dia_alvo=date(2026, 10, 2),
        calculado_em=datetime(2026, 10, 1, 6, 0, tzinfo=UTC),
    )


def test_indice_atual_devolve_none_sem_nenhum_calculo():
    conexao = _conexao()

    assert banco.indice_atual(conexao, "4202404") is None


# --- inscrições ---------------------------------------------------------------


def test_inscrever_e_depois_listar_inscritos_do_municipio():
    conexao = _conexao()
    agora = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

    banco.inscrever(conexao, 111, "4202404", agora)
    banco.inscrever(conexao, 222, "4202404", agora)
    banco.inscrever(conexao, 333, "4205407", agora)  # outro município

    assert banco.listar_inscritos(conexao, "4202404") == [111, 222]
    assert banco.listar_inscritos(conexao, "4205407") == [333]


def test_inscrever_duas_vezes_o_mesmo_chat_e_municipio_nao_duplica():
    conexao = _conexao()
    agora = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)

    banco.inscrever(conexao, 111, "4202404", agora)
    banco.inscrever(conexao, 111, "4202404", agora)

    assert banco.listar_inscritos(conexao, "4202404") == [111]


def test_remover_inscricoes_apaga_todas_as_inscricoes_do_chat_e_so_as_dele():
    conexao = _conexao()
    agora = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    banco.inscrever(conexao, 111, "4202404", agora)
    banco.inscrever(conexao, 111, "4205407", agora)
    banco.inscrever(conexao, 222, "4202404", agora)

    banco.remover_inscricoes(conexao, 111)

    assert banco.listar_inscritos(conexao, "4202404") == [222]
    assert banco.listar_inscritos(conexao, "4205407") == []


def test_inscrever_com_inscrito_em_sem_fuso_levanta_erro():
    conexao = _conexao()

    with pytest.raises(ValueError):
        banco.inscrever(conexao, 111, "4202404", datetime(2026, 10, 1, 12, 0))


# --- última classe notificada (notificacoes) -----------------------------


def test_ultima_classe_notificada_e_none_quando_nunca_notificado():
    conexao = _conexao()

    assert banco.ultima_classe_notificada(conexao, "4202404") is None


def test_atualizar_e_depois_ler_a_ultima_classe_notificada():
    conexao = _conexao()
    quando = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)

    banco.atualizar_ultima_classe_notificada(conexao, "4202404", 4, quando)

    assert banco.ultima_classe_notificada(conexao, "4202404") == 4


def test_atualizar_ultima_classe_notificada_substitui_o_valor_anterior():
    conexao = _conexao()
    quando = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
    banco.atualizar_ultima_classe_notificada(conexao, "4202404", 4, quando)

    banco.atualizar_ultima_classe_notificada(
        conexao, "4202404", 5, datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    )

    assert banco.ultima_classe_notificada(conexao, "4202404") == 5


def test_atualizar_ultima_classe_notificada_para_none_zera_a_classe():
    conexao = _conexao()
    quando = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
    banco.atualizar_ultima_classe_notificada(conexao, "4202404", 5, quando)

    banco.atualizar_ultima_classe_notificada(
        conexao, "4202404", None, datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    )

    # None aqui não pode ser confundido com "nunca notificado": é uma classe
    # zerada de propósito (RN08, Tarefa 8), mas o valor lido é o mesmo (None)
    # — a distinção não importa para quem lê, só para quem escreve.
    assert banco.ultima_classe_notificada(conexao, "4202404") is None


def test_atualizar_ultima_classe_notificada_com_notificado_em_sem_fuso_levanta_erro():
    conexao = _conexao()

    with pytest.raises(ValueError):
        banco.atualizar_ultima_classe_notificada(
            conexao, "4202404", 4, datetime(2026, 10, 1, 6, 0)
        )


# --- concorrência (WAL) ---------------------------------------------------


def test_uma_conexao_grava_enquanto_outra_le_sem_bloquear(tmp_path):
    """Uma conexão grava enquanto outra mantém uma leitura aberta no mesmo
    arquivo, sem "database is locked" — é o que o `PRAGMA journal_mode=WAL`
    de `abrir()` garante (README/brief): bot e pipeline têm conexões
    próprias ao mesmo arquivo e não podem travar um ao outro.

    `conexao_leitura` abre uma transação e lê, sem comitar: mantém um lock de
    leitura aberto no modo antigo (`rollback journal`). Em seguida,
    `conexao_escrita` grava e comita — com `busy_timeout=0`, para que um
    eventual bloqueio vire erro imediato em vez de uma espera de até 30 s
    (o `timeout=30` de `abrir()`), o que tornaria o teste lento sem WAL em
    vez de demonstrar o problema.
    """
    caminho = str(tmp_path / "vigia.sqlite3")
    conexao_leitura = banco.abrir(caminho)
    conexao_escrita = banco.abrir(caminho)
    conexao_escrita.execute("PRAGMA busy_timeout=0")

    conexao_leitura.execute("BEGIN")
    conexao_leitura.execute("SELECT chat_id FROM inscritos").fetchall()

    try:
        banco.inscrever(
            conexao_escrita, 111, "4202404", datetime(2026, 10, 1, 6, 0, tzinfo=UTC)
        )
    finally:
        conexao_leitura.commit()
        conexao_leitura.close()
        conexao_escrita.close()

    conexao_conferencia = banco.abrir(caminho)
    try:
        assert conexao_conferencia.execute(
            "SELECT chat_id FROM inscritos"
        ).fetchall() == [(111,)]
    finally:
        conexao_conferencia.close()


# --- versão do schema ---------------------------------------------------------


def test_abrir_marca_a_versao_do_schema_num_banco_novo(tmp_path):
    caminho = str(tmp_path / "vigia.sqlite3")

    conexao = banco.abrir(caminho)

    assert conexao.execute("PRAGMA user_version").fetchone()[0] == banco.VERSAO_SCHEMA


def test_abrir_num_banco_de_versao_mais_nova_levanta_em_vez_de_gravar_errado(tmp_path):
    # Sem esta checagem, `CREATE TABLE IF NOT EXISTS` passa batido num banco
    # fora de versão e a falha só aparece na primeira gravação — dentro do
    # `except Exception` do job agendado, isto é, o pipeline pararia de gravar e
    # de avisar a cada 6 h com nada no log além de um traceback genérico.
    caminho = str(tmp_path / "vigia.sqlite3")
    conexao = banco.abrir(caminho)
    conexao.execute(f"PRAGMA user_version = {banco.VERSAO_SCHEMA + 1}")
    conexao.commit()
    conexao.close()

    with pytest.raises(banco.SchemaIncompativelError, match="versão"):
        banco.abrir(caminho)


def test_versao_zero_e_aceita_como_banco_novo_ou_anterior_ao_versionamento():
    # `PRAGMA user_version` nasce em 0; um banco criado antes desta checagem
    # também está em 0 e tem o schema corrente, então 0 não é incompatível.
    assert banco.versao_compativel(0) is True


def test_a_versao_corrente_e_aceita():
    assert banco.versao_compativel(banco.VERSAO_SCHEMA) is True


def test_versao_diferente_da_corrente_nao_e_compativel():
    # Serve para os dois lados: banco mais novo que o código (downgrade) e, a
    # partir da próxima versão do schema, banco mais antigo sem migração.
    assert banco.versao_compativel(banco.VERSAO_SCHEMA + 1) is False
    assert banco.versao_compativel(99) is False


def test_mensagem_do_schema_incompativel_nomeia_as_duas_versoes(tmp_path):
    caminho = str(tmp_path / "vigia.sqlite3")
    conexao = banco.abrir(caminho)
    conexao.execute(f"PRAGMA user_version = {banco.VERSAO_SCHEMA + 1}")
    conexao.commit()
    conexao.close()

    with pytest.raises(banco.SchemaIncompativelError) as erro:
        banco.abrir(caminho)

    mensagem = str(erro.value)
    assert str(banco.VERSAO_SCHEMA + 1) in mensagem
    assert str(banco.VERSAO_SCHEMA) in mensagem


def test_indice_atual_traz_o_dia_alvo_do_d0():
    # O `/status` exibe o dia-alvo junto do índice (RN11): quando o município
    # fica sem dados numa execução, o índice mostrado é o da execução anterior,
    # e sem o dia-alvo o leitor não sabe a que dia ele se refere.
    conexao = _conexao()
    _inserir_calculo(conexao, "4206900", "2026-10-01", "2026-10-01T06:00:00Z", 1.25, 4)
    _inserir_calculo(conexao, "4206900", "2026-10-02", "2026-10-01T06:00:00Z", 0.5, 2)

    atual = banco.indice_atual(conexao, "4206900")

    assert atual.dia_alvo == date(2026, 10, 1)
