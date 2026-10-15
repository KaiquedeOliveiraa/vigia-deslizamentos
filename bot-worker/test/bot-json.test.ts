import { afterEach, describe, expect, it, vi } from "vitest";
import { carregarBotJson } from "../src/bot-json";
import { botJsonDeTeste } from "./apoio";

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
