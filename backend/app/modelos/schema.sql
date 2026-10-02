-- Schema do banco SQLite do VIGIA: índices calculados, inscritos do bot e
-- controle de notificações (README, seção "Banco de dados"). Aplicado por
-- `app.modelos.banco.abrir`, com `CREATE TABLE IF NOT EXISTS` — sem camada de
-- migração.

-- Um cálculo (um dia-alvo, de uma execução do pipeline). `limiar_mm` registra
-- com que limiar a linha foi calculada, para que um cálculo antigo continue
-- interpretável depois de o limiar do município mudar.
CREATE TABLE IF NOT EXISTS indices (
    ibge TEXT NOT NULL,
    dia_alvo TEXT NOT NULL,
    calculado_em TEXT NOT NULL,
    indice REAL NOT NULL,
    classe INTEGER NOT NULL,
    efr_mm REAL NOT NULL,
    rtotal_mm REAL NOT NULL,
    limiar_mm REAL NOT NULL,
    n_membros INTEGER NOT NULL,
    prob_pontuais REAL NOT NULL,
    prob_esparsos REAL NOT NULL,
    prob_generalizados REAL NOT NULL,
    PRIMARY KEY (ibge, dia_alvo, calculado_em)
);

-- Um chat do Telegram inscrito nos avisos de um município (RF11, RNF05).
CREATE TABLE IF NOT EXISTS inscritos (
    chat_id INTEGER NOT NULL,
    ibge TEXT NOT NULL,
    inscrito_em TEXT NOT NULL,
    PRIMARY KEY (chat_id, ibge)
);

-- Última classe notificada de cada município, para a regra RN08 (Tarefa 8)
-- não repetir o aviso enquanto a classe não mudar. `ultima_classe` é `NULL`
-- quando o município nunca foi notificado ou saiu de alerta (zerada).
CREATE TABLE IF NOT EXISTS notificacoes (
    ibge TEXT PRIMARY KEY,
    ultima_classe INTEGER,
    notificado_em TEXT NOT NULL
);
