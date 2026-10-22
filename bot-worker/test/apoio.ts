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

export function botJsonComGrupos(): BotJson {
  const bot = botJsonDeTeste();
  bot.municipios.push({ ibge: "4208500", nome: "Ituporanga" }, { ibge: "4212700", nome: "Petrolândia" });
  bot.textos.inscricao_confirmada["4208500"] = "Inscrito em Ituporanga.";
  bot.textos.inscricao_confirmada["4212700"] = "Inscrito em Petrolândia.";
  bot.status.blocos["4212700"] = "Petrolândia: baixo";
  bot.textos.boas_vindas_sugerido["4208500"] = "Bem-vindo ao VIGIA. Quer Ituporanga?";
  bot.status.blocos["4208500"] = "Ituporanga: baixo";
  bot.textos.opcao_voltar = "Voltar";
  bot.textos.boas_vindas_grupos = "Escolha a região.";
  bot.grupos = [
    { nome: "Região de Rio do Sul", municipios: ["4208203", "4128104"], opcao_todos: "Todos da Região de Rio do Sul", escolha: "Municípios de Rio do Sul.", confirmacao: "Inscrito na região de Rio do Sul." },
    { nome: "Região de Ituporanga", municipios: ["4208500", "4212700"], opcao_todos: "Todos da Região de Ituporanga", escolha: "Municípios de Ituporanga.", confirmacao: "Inscrito na região de Ituporanga." },
  ];
  return bot;
}
