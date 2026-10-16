CREATE TABLE IF NOT EXISTS inscritos (
  chat_id INTEGER NOT NULL,
  ibge TEXT NOT NULL,
  inscrito_em TEXT NOT NULL,
  PRIMARY KEY (chat_id, ibge)
);
