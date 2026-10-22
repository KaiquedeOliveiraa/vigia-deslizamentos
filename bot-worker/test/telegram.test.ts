import { createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TEXTO_INDISPONIVEL } from "../src/bot-json";
import worker from "../src/index";
import { ibgesDoChat, inscrever, listarTodos } from "../src/inscritos";
import { escaparHtml, interpretarComando, normalizarNome, partesDoStatus, textoDoStatus } from "../src/telegram";
import type { BotJson } from "../src/tipos";
import { botJsonComGrupos, botJsonDeTeste } from "./apoio";
import fixtureReal from "./fixtures/bot.exemplo.json";

const CHAT = 777;
const GRUPO = -1001234567890;

type Envio = {
  chat_id: number;
  text: string;
  parse_mode?: string;
  reply_markup?: Record<string, unknown>;
};

let envios: Envio[];
let botJson: BotJson | null;
let statusTelegram: number;
let sendMessageExpira = false;
let sinaisSendMessage: Array<AbortSignal | null | undefined>;

function urlDe(entrada: RequestInfo | URL): string {
  if (typeof entrada === "string") return entrada;
  return entrada instanceof URL ? entrada.href : entrada.url;
}

function simularRede() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (entrada, init) => {
    const url = urlDe(entrada);
    if (url === env.BOT_JSON_URL) {
      return botJson === null
        ? new Response("erro", { status: 503 })
        : new Response(JSON.stringify(botJson), { status: 200 });
    }
    if (url.startsWith("https://api.telegram.org/") && url.endsWith("/sendMessage")) {
      sinaisSendMessage.push(init?.signal);
      if (sendMessageExpira) throw new DOMException("x", "TimeoutError");
      envios.push(JSON.parse(String(init?.body)) as Envio);
      return new Response("{}", { status: statusTelegram });
    }
    throw new Error("fetch inesperado");
  });
}

async function enviar(update: unknown, segredo: string | null = env.TELEGRAM_WEBHOOK_SEGREDO) {
  const cabecalhos: Record<string, string> = { "Content-Type": "application/json" };
  if (segredo !== null) cabecalhos["X-Telegram-Bot-Api-Secret-Token"] = segredo;
  const ctx = createExecutionContext();
  const resposta = await worker.fetch(
    new Request("https://w.test/telegram", {
      method: "POST",
      headers: cabecalhos,
      body: JSON.stringify(update),
    }),
    env,
    ctx,
  );
  await waitOnExecutionContext(ctx);
  return resposta;
}

function mensagem(texto: string, chatId = CHAT) {
  return { update_id: 1, message: { message_id: 1, chat: { id: chatId }, text: texto } };
}

const TECLADO_MUNICIPIOS = {
  keyboard: [[{ text: "Ibirama" }], [{ text: "Witmarsum" }], [{ text: "Todos" }]],
  resize_keyboard: true,
  one_time_keyboard: true,
};

beforeEach(async () => {
  envios = [];
  botJson = botJsonDeTeste();
  statusTelegram = 200;
  sendMessageExpira = false;
  sinaisSendMessage = [];
  await env.DB.prepare("DELETE FROM inscritos").run();
  simularRede();
});

afterEach(() => vi.restoreAllMocks());

describe("funções puras", () => {
  it("interpretarComando", () => {
    expect(interpretarComando("/status@VigiaDeslizamentosBot")).toEqual({ comando: "status", args: [] });
    expect(interpretarComando("/start 4206900")).toEqual({ comando: "start", args: ["4206900"] });
    expect(interpretarComando("/Simular  Foo  bar")).toEqual({ comando: "simular", args: ["Foo", "bar"] });
    expect(interpretarComando("Ibirama")).toBeNull();
  });

  it("normalizarNome", () => {
    expect(normalizarNome("  São   JOSÉ ")).toBe("sao jose");
  });

  it("escaparHtml", () => {
    expect(escaparHtml(`<b>"a"&</b>`)).toBe("&lt;b&gt;&quot;a&quot;&amp;&lt;/b&gt;");
  });
});

describe("POST /telegram", () => {
  it("segredo errado ou ausente: 401 e nenhum envio", async () => {
    expect((await enviar(mensagem("/start"), "errado")).status).toBe(401);
    expect((await enviar(mensagem("/start"), null)).status).toBe(401);
    expect(envios).toEqual([]);
  });

  it("figurinha e edited_message: 200 sem envio", async () => {
    const figurinha = { update_id: 1, message: { message_id: 1, chat: { id: CHAT }, sticker: {} } };
    const editada = { update_id: 2, edited_message: { message_id: 1, chat: { id: CHAT }, text: "/start" } };
    expect((await enviar(figurinha)).status).toBe(200);
    expect((await enviar(editada)).status).toBe(200);
    expect(envios).toEqual([]);
  });

  it("/start", async () => {
    expect((await enviar(mensagem("/start"))).status).toBe(200);
    expect(envios).toEqual([
      { chat_id: CHAT, text: "Bem-vindo ao VIGIA.", parse_mode: "HTML", reply_markup: TECLADO_MUNICIPIOS },
    ]);
  });

  it("/start com município sugerido", async () => {
    await enviar(mensagem("/start 4128104"));
    expect(envios[0]!.text).toBe("Bem-vindo ao VIGIA. Quer Witmarsum?");
    expect(envios[0]!.reply_markup).toEqual(TECLADO_MUNICIPIOS);
  });

  it("/start com código desconhecido usa a boas-vindas padrão", async () => {
    await enviar(mensagem("/start 9999999"));
    expect(envios[0]!.text).toBe("Bem-vindo ao VIGIA.");
  });

  it("nome exato de município inscreve e remove o teclado", async () => {
    await enviar(mensagem("Ibirama"));
    expect(envios).toEqual([
      { chat_id: CHAT, text: "Inscrito em Ibirama.", parse_mode: "HTML", reply_markup: { remove_keyboard: true } },
    ]);
    expect(await ibgesDoChat(env.DB, CHAT)).toEqual(["4208203"]);
  });

  it("inscrição repetida não duplica a linha", async () => {
    await enviar(mensagem("Ibirama"));
    await enviar(mensagem("Ibirama"));
    expect(await ibgesDoChat(env.DB, CHAT)).toEqual(["4208203"]);
  });

  it("Todos inscreve nos dois municípios", async () => {
    await enviar(mensagem("Todos"));
    expect(envios[0]!.text).toBe("Inscrito em Ibirama e Witmarsum.");
    expect(envios[0]!.reply_markup).toEqual({ remove_keyboard: true });
    expect((await ibgesDoChat(env.DB, CHAT)).sort()).toEqual(["4128104", "4208203"]);
  });

  it("grupo com chat_id negativo se inscreve", async () => {
    await enviar(mensagem("Witmarsum", GRUPO));
    expect(envios[0]!.chat_id).toBe(GRUPO);
    expect(await ibgesDoChat(env.DB, GRUPO)).toEqual(["4128104"]);
  });

  it("/status sem inscrição", async () => {
    await enviar(mensagem("/status"));
    expect(envios).toEqual([{ chat_id: CHAT, text: "Sem inscrição.", parse_mode: "HTML" }]);
  });

  it("/status com 1 inscrito", async () => {
    await inscrever(env.DB, CHAT, ["4128104"], new Date());
    await enviar(mensagem("/status"));
    expect(envios[0]!.text).toBe("<b>Status</b>\n\nWitmarsum: baixo\n\nsite");
    expect(envios[0]!.reply_markup).toBeUndefined();
  });

  it("/status com 2 inscritos segue a ordem de municipios", async () => {
    await inscrever(env.DB, CHAT, ["4128104"], new Date());
    await inscrever(env.DB, CHAT, ["4208203"], new Date());
    await enviar(mensagem("/status"));
    expect(envios[0]!.text).toBe("<b>Status</b>\n\nIbirama: baixo\n\nWitmarsum: baixo\n\nsite");
  });

  it("/status ignora ibge fora do bot.json", async () => {
    await inscrever(env.DB, CHAT, ["1111111", "4208203"], new Date());
    await enviar(mensagem("/status"));
    expect(envios[0]!.text).toBe("<b>Status</b>\n\nIbirama: baixo\n\nsite");
  });

  it("/status só com ibge desconhecido cai em sem_inscricao", async () => {
    await inscrever(env.DB, CHAT, ["1111111"], new Date());
    await enviar(mensagem("/status"));
    expect(envios[0]!.text).toBe("Sem inscrição.");
  });

  it("/status@NomeDoBot responde como /status", async () => {
    await enviar(mensagem("/status@VigiaDeslizamentosBot"));
    expect(envios[0]!.text).toBe("Sem inscrição.");
  });

  it("/parar apaga o chat", async () => {
    await inscrever(env.DB, CHAT, ["4208203"], new Date());
    await inscrever(env.DB, 5, ["4208203"], new Date());
    await enviar(mensagem("/parar"));
    expect(envios).toEqual([
      { chat_id: CHAT, text: "Inscrições apagadas.", parse_mode: "HTML", reply_markup: { remove_keyboard: true } },
    ]);
    expect(await listarTodos(env.DB)).toEqual([{ chat_id: 5, ibge: "4208203" }]);
  });

  it("/simular sem argumento usa o primeiro município", async () => {
    await enviar(mensagem("/simular"));
    expect(envios.map((e) => e.text)).toEqual(["a1", "a2", "Fim da simulação."]);
    expect(envios.every((e) => e.parse_mode === "HTML" && e.reply_markup === undefined)).toBe(true);
  });

  it("/simular witmarsum (minúsculas)", async () => {
    await enviar(mensagem("/simular witmarsum"));
    expect(envios.map((e) => e.text)).toEqual(["b1", "b2", "Fim da simulação."]);
  });

  it("/simular com nome inválido escapa a entrada", async () => {
    await enviar(mensagem("/simular <b>X</b>"));
    expect(envios.map((e) => e.text)).toEqual(["Município inválido: &lt;b&gt;X&lt;/b&gt;"]);
  });

  it("/simular com simulacao null cai em opcao_desconhecida", async () => {
    botJson = { ...botJsonDeTeste(), simulacao: null };
    await enviar(mensagem("/simular"));
    expect(envios).toEqual([
      { chat_id: CHAT, text: "Não entendi.", parse_mode: "HTML", reply_markup: TECLADO_MUNICIPIOS },
    ]);
  });

  it("outro comando e outro texto: opcao_desconhecida com teclado", async () => {
    await enviar(mensagem("/xyz"));
    await enviar(mensagem("blá"));
    expect(envios.map((e) => e.text)).toEqual(["Não entendi.", "Não entendi."]);
    expect(envios.every((e) => JSON.stringify(e.reply_markup) === JSON.stringify(TECLADO_MUNICIPIOS))).toBe(true);
  });

  it("bot.json indisponível: TEXTO_INDISPONIVEL sem teclado", async () => {
    botJson = null;
    await enviar(mensagem("/start"));
    expect(envios).toEqual([{ chat_id: CHAT, text: TEXTO_INDISPONIVEL, parse_mode: "HTML" }]);
  });

  it("sendMessage com 500: webhook responde 200 e o log não traz o chat_id", async () => {
    statusTelegram = 500;
    const erro = vi.spyOn(console, "error").mockImplementation(() => {});
    const resposta = await enviar(mensagem("/status", 424242));
    expect(resposta.status).toBe(200);
    expect(erro).toHaveBeenCalled();
    expect(JSON.stringify(erro.mock.calls)).not.toContain("424242");
    expect(JSON.stringify(erro.mock.calls)).not.toContain(env.TELEGRAM_TOKEN);
  });

  it("sendMessage com timeout: usa sinal de cancelamento, responde 200 e o log não traz o chat_id", async () => {
    sendMessageExpira = true;
    const erro = vi.spyOn(console, "error").mockImplementation(() => {});
    const resposta = await enviar(mensagem("/status", 424242));
    expect(resposta.status).toBe(200);
    expect(sinaisSendMessage).toHaveLength(1);
    expect(sinaisSendMessage[0]).toBeInstanceOf(AbortSignal);
    expect(erro).toHaveBeenCalled();
    expect(JSON.stringify(erro.mock.calls)).toContain("TimeoutError");
    expect(JSON.stringify(erro.mock.calls)).not.toContain("424242");
    expect(JSON.stringify(erro.mock.calls)).not.toContain(env.TELEGRAM_TOKEN);
  });
});

const teclado = (linhas: string[][]) => ({
  keyboard: linhas.map((l) => l.map((text) => ({ text }))),
  resize_keyboard: true,
  one_time_keyboard: true,
});

describe("com grupos", () => {
  beforeEach(() => {
    botJson = botJsonComGrupos();
  });

  it("/start mostra as regiões e Todos", async () => {
    await enviar(mensagem("/start"));
    expect(envios[0]!.text).toBe("Escolha a região.");
    expect(envios[0]!.reply_markup).toEqual(teclado([["Região de Rio do Sul"], ["Região de Ituporanga"], ["Todos"]]));
  });

  it("/start com sugerido põe o município na primeira linha", async () => {
    await enviar(mensagem("/start 4208500"));
    expect(envios[0]!.text).toBe("Bem-vindo ao VIGIA. Quer Ituporanga?");
    expect(envios[0]!.reply_markup).toEqual(
      teclado([["Ituporanga"], ["Região de Rio do Sul"], ["Região de Ituporanga"], ["Todos"]]),
    );
  });

  it("região mostra os municípios em duas colunas, Todos da região e Voltar", async () => {
    await enviar(mensagem("Região de Rio do Sul"));
    expect(envios[0]!.text).toBe("Municípios de Rio do Sul.");
    expect(envios[0]!.reply_markup).toEqual(
      teclado([["Ibirama", "Witmarsum"], ["Todos da Região de Rio do Sul"], ["Voltar"]]),
    );
    expect(await ibgesDoChat(env.DB, CHAT)).toEqual([]);
  });

  it("Todos da região inscreve só nela", async () => {
    await enviar(mensagem("Todos da Região de Rio do Sul"));
    expect(envios[0]!.text).toBe("Inscrito na região de Rio do Sul.");
    expect((await ibgesDoChat(env.DB, CHAT)).sort()).toEqual(["4128104", "4208203"]);
  });

  it("Todos inscreve em todos", async () => {
    await enviar(mensagem("Todos"));
    expect((await ibgesDoChat(env.DB, CHAT)).sort()).toEqual(["4128104", "4208203", "4208500", "4212700"]);
  });

  it("Voltar e opção desconhecida mostram as regiões", async () => {
    await enviar(mensagem("Voltar"));
    await enviar(mensagem("qualquer coisa"));
    for (const e of envios) {
      expect(e.reply_markup).toEqual(teclado([["Região de Rio do Sul"], ["Região de Ituporanga"], ["Todos"]]));
    }
  });

  it("nome digitado sem acento e em minúsculas inscreve", async () => {
    await enviar(mensagem("  PETROLANDIA "));
    expect(await ibgesDoChat(env.DB, CHAT)).toEqual(["4212700"]);
  });

  it("inscrito antigo continua com os seus", async () => {
    await inscrever(env.DB, CHAT, ["4208203"], new Date());
    await enviar(mensagem("/status"));
    expect(envios[0]!.text).toContain("Ibirama: baixo");
    expect(envios[0]!.text).not.toContain("Ituporanga");
  });
});

it("sem grupos, um botão de região antigo cai em opcao_desconhecida sem inscrever", async () => {
  await enviar(mensagem("Região de Rio do Sul"));
  expect(envios[0]!.text).toBe("Não entendi.");
  expect(envios[0]!.reply_markup).toEqual(TECLADO_MUNICIPIOS);
  expect(await ibgesDoChat(env.DB, CHAT)).toEqual([]);
});

it("partesDoStatus corta só entre blocos e respeita o limite", () => {
  const bot = botJsonDeTeste();
  const ibges: string[] = [];
  for (let i = 0; i < 27; i++) {
    const ibge = String(4200000 + i);
    bot.municipios.push({ ibge, nome: `M${i}` });
    bot.status.blocos[ibge] = `Bloco ${i} ${"x".repeat(40)}`;
    ibges.push(ibge);
  }
  const partes = partesDoStatus(bot, ibges, 200);
  expect(partes.length).toBeGreaterThan(1);
  expect(partes.every((p) => p.length <= 200)).toBe(true);
  expect(partes[0]!.startsWith(bot.status.cabecalho)).toBe(true);
  expect(partes.at(-1)!.endsWith(bot.status.rodape)).toBe(true);
  for (let i = 0; i < 27; i++) expect(partes.join("")).toContain(`Bloco ${i} `);
});

it("partesDoStatus com uma parte é igual ao textoDoStatus", () => {
  const bot = botJsonDeTeste();
  const ibges = bot.municipios.map((m) => m.ibge);
  expect(partesDoStatus(bot, ibges)).toEqual([textoDoStatus(bot, ibges)]);
});

it("partesDoStatus: bloco sozinho maior que o limite é erro", () => {
  const bot = botJsonDeTeste();
  expect(() => partesDoStatus(bot, [bot.municipios[0]!.ibge], 10)).toThrow(/bloco/);
});

describe("fixture real (gerada pelo backend com os 27)", () => {
  const real = fixtureReal as unknown as BotJson;

  it("/status de quem assina os 27: partes de até 4096 e nenhum bloco cortado", () => {
    const ibges = real.municipios.map((m) => m.ibge);
    const partes = partesDoStatus(real, ibges);
    expect(partes.every((p) => p.length <= 4096)).toBe(true);
    const juntas = partes.join("");
    for (const ibge of ibges) expect(juntas).toContain(real.status.blocos[ibge]!);
  });

  it("rótulos de botão únicos pela normalizarNome do Worker", () => {
    const rotulos = [
      ...real.municipios.map((m) => m.nome),
      real.textos.opcao_todos,
      real.textos.opcao_voltar ?? "",
      ...(real.grupos ?? []).flatMap((g) => [g.nome, g.opcao_todos]),
    ].map(normalizarNome);
    expect(new Set(rotulos).size).toBe(rotulos.length);
  });
});
