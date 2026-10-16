import type { BotJson } from "../src/tipos";

export function botJsonDeTeste(): BotJson {
  return {
    schema_version: 1,
    gerado_em: "2026-10-15T12:00:00Z",
    municipios: [
      { ibge: "4208203", nome: "Ibirama" },
      { ibge: "4128104", nome: "Witmarsum" },
    ],
    textos: {
      opcao_todos: "Todos",
      boas_vindas: "Bem-vindo ao VIGIA.",
      boas_vindas_sugerido: {
        "4208203": "Bem-vindo ao VIGIA. Quer Ibirama?",
        "4128104": "Bem-vindo ao VIGIA. Quer Witmarsum?",
      },
      inscricao_confirmada: {
        "4208203": "Inscrito em Ibirama.",
        "4128104": "Inscrito em Witmarsum.",
      },
      inscricao_confirmada_todos: "Inscrito em Ibirama e Witmarsum.",
      opcao_desconhecida: "Não entendi.",
      inscricoes_apagadas: "Inscrições apagadas.",
    },
    status: {
      cabecalho: "<b>Status</b>\n\n",
      blocos: { "4208203": "Ibirama: baixo", "4128104": "Witmarsum: baixo" },
      separador: "\n\n",
      rodape: "\n\nsite",
      sem_inscricao: "Sem inscrição.",
    },
    simulacao: {
      mensagens: { "4208203": ["a1", "a2"], "4128104": ["b1", "b2"] },
      fim: "Fim da simulação.",
      municipio_invalido: "Município inválido: {entrada}",
      pausa_s: 0,
    },
  };
}
