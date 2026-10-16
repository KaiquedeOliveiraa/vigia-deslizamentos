import { createExecutionContext, waitOnExecutionContext } from "cloudflare:test";
import { env } from "cloudflare:workers";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TEXTO_INDISPONIVEL } from "../src/bot-json";
import worker from "../src/index";
import { ibgesDoChat, inscrever, listarTodos } from "../src/inscritos";
import { escaparHtml, interpretarComando, normalizarNome } from "../src/telegram";
import type { BotJson } from "../src/tipos";
import { botJsonDeTeste } from "./apoio";

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
