export interface Env {
  DB: D1Database;
  TELEGRAM_TOKEN: string;
  TELEGRAM_WEBHOOK_SEGREDO: string;
  VIGIA_WORKER_SEGREDO: string;
  BOT_JSON_URL: string;
}

/** Espelha o `bot.json` gerado por `montar_bot_json` (backend). */
export type BotJson = {
  schema_version: number;
  gerado_em: string;
  municipios: { ibge: string; nome: string }[];
  textos: {
    opcao_todos: string;
    boas_vindas: string;
    boas_vindas_sugerido: Record<string, string>;
    inscricao_confirmada: Record<string, string>;
    inscricao_confirmada_todos: string;
    opcao_desconhecida: string;
    inscricoes_apagadas: string;
  };
  status: {
    cabecalho: string;
    blocos: Record<string, string>;
    separador: string;
    rodape: string;
    sem_inscricao: string;
  };
  simulacao: null | {
    mensagens: Record<string, string[]>;
    fim: string;
    municipio_invalido: string;
    pausa_s: number;
  };
};
