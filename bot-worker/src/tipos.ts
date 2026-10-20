export interface Env {
  DB: D1Database;
  TELEGRAM_TOKEN: string;
  TELEGRAM_WEBHOOK_SEGREDO: string;
  VIGIA_WORKER_SEGREDO: string;
  BOT_JSON_URL: string;
}

export type Grupo = {
  nome: string;
  municipios: string[];
  opcao_todos: string;
  escolha: string;
  confirmacao: string;
};

/** Espelha o `bot.json` gerado por `montar_bot_json` (backend). */
export type BotJson = {
  schema_version: number;
  gerado_em: string;
  municipios: { ibge: string; nome: string }[];
  grupos?: Grupo[];
  textos: {
    opcao_todos: string;
    boas_vindas: string;
    boas_vindas_sugerido: Record<string, string>;
    inscricao_confirmada: Record<string, string>;
    inscricao_confirmada_todos: string;
    opcao_desconhecida: string;
    inscricoes_apagadas: string;
    opcao_voltar?: string;
    boas_vindas_grupos?: string;
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
