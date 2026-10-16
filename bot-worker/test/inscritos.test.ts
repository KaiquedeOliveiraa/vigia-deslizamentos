import { createExecutionContext } from "cloudflare:test";
import { env } from "cloudflare:workers";
import { beforeEach, describe, expect, it } from "vitest";
import worker from "../src/index";
import { ibgesDoChat, inscrever, listarTodos, removerChat } from "../src/inscritos";

const GRUPO = -1001234567890;
const AUTH = { Authorization: `Bearer ${env.VIGIA_WORKER_SEGREDO}` };

function chamar(caminho: string, init?: RequestInit) {
  return worker.fetch(new Request(`https://w.test${caminho}`, init), env, createExecutionContext());
}

beforeEach(async () => {
  await env.DB.prepare("DELETE FROM inscritos").run();
  await inscrever(env.DB, GRUPO, ["4208203"], new Date("2026-10-15T12:34:56.789Z"));
  await inscrever(env.DB, 42, ["4208203", "4128104"], new Date("2026-10-15T12:34:56Z"));
});

describe("funções do D1", () => {
  it("grava inscrito_em sem milissegundos", async () => {
    const linha = await env.DB.prepare("SELECT inscrito_em FROM inscritos WHERE chat_id = ?")
      .bind(GRUPO)
      .first<{ inscrito_em: string }>();
    expect(linha?.inscrito_em).toBe("2026-10-15T12:34:56Z");
  });

  it("inscrever é idempotente", async () => {
    await inscrever(env.DB, 42, ["4208203"], new Date());
    expect((await ibgesDoChat(env.DB, 42)).sort()).toEqual(["4128104", "4208203"]);
  });

  it("removerChat apaga só o chat", async () => {
    await removerChat(env.DB, 42);
    expect(await ibgesDoChat(env.DB, 42)).toEqual([]);
    expect(await ibgesDoChat(env.DB, GRUPO)).toEqual(["4208203"]);
  });

  it("listarTodos devolve chat_id numérico", async () => {
    const todos = await listarTodos(env.DB);
    expect(todos).toContainEqual({ chat_id: GRUPO, ibge: "4208203" });
    expect(todos).toHaveLength(3);
  });
});

describe("GET /inscritos", () => {
  it("sem cabeçalho dá 401", async () => {
    expect((await chamar("/inscritos")).status).toBe(401);
  });

  it("com segredo errado dá 401", async () => {
    const r = await chamar("/inscritos", { headers: { Authorization: "Bearer errado" } });
    expect(r.status).toBe(401);
  });

  it("com o segredo certo dá 200 e a lista", async () => {
    const r = await chamar("/inscritos", { headers: AUTH });
    expect(r.status).toBe(200);
    const corpo = (await r.json()) as { inscritos: { chat_id: number; ibge: string }[] };
    expect(corpo.inscritos).toHaveLength(3);
    expect(corpo.inscritos).toContainEqual({ chat_id: GRUPO, ibge: "4208203" });
  });
});

describe("DELETE /inscritos/{chat_id}", () => {
  it("chat_id negativo dá 204 e a linha some", async () => {
    const r = await chamar(`/inscritos/${GRUPO}`, { method: "DELETE", headers: AUTH });
    expect(r.status).toBe(204);
    expect(await ibgesDoChat(env.DB, GRUPO)).toEqual([]);
  });

  it("chat_id inválido dá 400", async () => {
    const r = await chamar("/inscritos/abc", { method: "DELETE", headers: AUTH });
    expect(r.status).toBe(400);
  });

  it("sem autenticação dá 401 e a linha continua", async () => {
    const r = await chamar(`/inscritos/${GRUPO}`, { method: "DELETE" });
    expect(r.status).toBe(401);
    expect(await ibgesDoChat(env.DB, GRUPO)).toEqual(["4208203"]);
  });
});

describe("outras rotas", () => {
  it("GET /qualquer dá 404", async () => {
    expect((await chamar("/qualquer")).status).toBe(404);
  });
});
