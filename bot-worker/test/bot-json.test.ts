import { afterEach, describe, expect, it, vi } from "vitest";
import { carregarBotJson } from "../src/bot-json";
import { textoDoStatus } from "../src/telegram";
import type { BotJson } from "../src/tipos";
import { botJsonDeTeste } from "./apoio";
import fixture from "./fixtures/bot.exemplo.json";

const URL_TESTE = "https://exemplo.test/bot.json";

function simularFetch(resposta: Response) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(resposta);
}

afterEach(() => vi.restoreAllMocks());

describe("carregarBotJson", () => {
  it("devolve o objeto quando a resposta é 200 e válida", async () => {
    const espiao = simularFetch(new Response(JSON.stringify(botJsonDeTeste()), { status: 200 }));
    expect(await carregarBotJson(URL_TESTE)).toEqual(botJsonDeTeste());
    expect(espiao.mock.calls[0]![0]).toBe(URL_TESTE);
  });

  it("devolve null quando a resposta é 404 e registra o status", async () => {
    const erro = vi.spyOn(console, "error").mockImplementation(() => {});
    simularFetch(new Response("não achei", { status: 404 }));
    expect(await carregarBotJson(URL_TESTE)).toBeNull();
    expect(erro).toHaveBeenCalledWith(expect.stringContaining("404"));
    expect(JSON.stringify(erro.mock.calls)).not.toContain("não achei");
  });

  it("devolve null quando o corpo não é JSON", async () => {
    simularFetch(new Response("<html>", { status: 200 }));
    expect(await carregarBotJson(URL_TESTE)).toBeNull();
  });

  it("devolve null quando schema_version é diferente de 1", async () => {
    const erro = vi.spyOn(console, "error").mockImplementation(() => {});
    const v2 = { ...botJsonDeTeste(), schema_version: 2 };
    simularFetch(new Response(JSON.stringify(v2), { status: 200 }));
    expect(await carregarBotJson(URL_TESTE)).toBeNull();
    expect(erro).toHaveBeenCalledWith(expect.stringContaining("schema_version"));
  });

  it("devolve null quando o fetch falha", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("rede"));
    expect(await carregarBotJson(URL_TESTE)).toBeNull();
  });
});

// Gerada pelo backend (`test_fixture_do_worker_igual_ao_montar_bot_json`): o `tsc` confere o formato
// contra `BotJson`, e estes testes conferem que todo município tem os textos que o Worker procura.
describe("bot.exemplo.json gerado pelo backend", () => {
  const exemplo: BotJson = fixture;

  it("é aceito por carregarBotJson", async () => {
    simularFetch(new Response(JSON.stringify(exemplo), { status: 200 }));
    expect(await carregarBotJson(URL_TESTE)).toEqual(exemplo);
  });

  it("todo município tem boas-vindas, confirmação e bloco do /status", () => {
    expect(exemplo.municipios.length).toBeGreaterThan(0);
    for (const { ibge } of exemplo.municipios) {
      expect(exemplo.textos.boas_vindas_sugerido[ibge]).toEqual(expect.any(String));
      expect(exemplo.textos.inscricao_confirmada[ibge]).toEqual(expect.any(String));
      expect(exemplo.status.blocos[ibge]).toEqual(expect.any(String));
    }
  });

  it("/status com todos os municípios usa cabeçalho, blocos e rodapé", () => {
    const todos = exemplo.municipios.map((m) => m.ibge);
    const texto = textoDoStatus(exemplo, todos);
    expect(texto.startsWith(exemplo.status.cabecalho)).toBe(true);
    expect(texto.endsWith(exemplo.status.rodape)).toBe(true);
    for (const ibge of todos) expect(texto).toContain(exemplo.status.blocos[ibge]);
  });
});
