import { describe, expect, it } from "vitest";
import contatos from "../fixtures/contatos.exemplo.json";
import estacoes from "../fixtures/estacoes.exemplo.json";
import indices from "../fixtures/indices.exemplo.json";
import ocorrencias from "../fixtures/ocorrencias.exemplo.json";
import {
  carregar,
  desatualizado,
  estadoMunicipio,
  lerContatos,
  lerEstacoes,
  lerIndices,
  lerOcorrencias,
} from "./dados";
import type { Indices } from "./tipos";

const copia = <T>(v: T): T => structuredClone(v);

describe("lerIndices", () => {
  it("JSON válido → objeto tipado", () => {
    const r = lerIndices(indices);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.dados.municipios[0].dias[0].indice).toBeCloseTo(1.3448);
  });

  it("schema_version desconhecido → erro, sem dados parciais", () => {
    const r = lerIndices({ ...copia(indices), schema_version: 2 });
    expect(r).toEqual({ ok: false, erro: expect.stringContaining("schema_version") });
  });

  it("campo usado ausente → erro", () => {
    const sem = copia(indices) as { municipios: Record<string, unknown>[] };
    delete sem.municipios[0].dias;
    expect(lerIndices(sem).ok).toBe(false);
    expect(lerIndices(null).ok).toBe(false);
  });
});

describe("desatualizado (RN12)", () => {
  const gerado = "2026-09-29T06:00:00-03:00";
  it("12 h exatas → falso", () => {
    expect(desatualizado(gerado, new Date("2026-09-29T18:00:00-03:00"))).toBe(false);
  });
  it("12 h e 1 min → verdadeiro", () => {
    expect(desatualizado(gerado, new Date("2026-09-29T18:01:00-03:00"))).toBe(true);
  });
});

describe("estadoMunicipio", () => {
  const base = indices as Indices;
  it("município em municipios_sem_dados → sem dados", () => {
    const d: Indices = { ...base, municipios_sem_dados: ["4206900"], municipios: base.municipios.slice(1) };
    expect(estadoMunicipio(d, "4206900")).toEqual({ estado: "sem dados" });
  });
  it("município com dados → devolve o item", () => {
    expect(estadoMunicipio(base, "4206900")).toEqual({ estado: "ok", municipio: base.municipios[0] });
  });
});

describe("listas", () => {
  it("contatos.json: só itens com verificado: true (RN09)", () => {
    const r = lerContatos(contatos);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.dados.length).toBeGreaterThan(0);
      expect(r.dados.length).toBeLessThan(contatos.length);
      expect(r.dados.every((c) => c.verificado)).toBe(true);
    }
  });

  it("estacoes.json: lê ibge_referencia e distancia_km", () => {
    const r = lerEstacoes(estacoes);
    expect(r.ok && r.dados[0]).toMatchObject({ ibge_referencia: "4206900", distancia_km: 76.3 });
    expect(lerEstacoes([{ codigo: "A868", nome: "ITAJAI", lat: 0, lon: 0 }]).ok).toBe(false);
  });

  it("ocorrencias.json: lista válida; raiz que não é lista → erro", () => {
    expect(lerOcorrencias(ocorrencias)).toEqual({ ok: true, dados: ocorrencias });
    expect(lerOcorrencias({}).ok).toBe(false);
  });
});

describe("carregar", () => {
  const resposta = (corpo: unknown, status = 200) => async () => new Response(JSON.stringify(corpo), { status });

  it("busca em urlDados e devolve o resultado da leitura", async () => {
    let pedida = "";
    const buscar = async (url: string) => {
      pedida = url;
      return new Response(JSON.stringify(contatos));
    };
    const r = await carregar("contatos.json", lerContatos, buscar);
    expect(pedida).toMatch(/\/contatos\.json$/);
    expect(r.ok).toBe(true);
  });

  it("HTTP com erro → erro", async () => {
    expect(await carregar("indices.json", lerIndices, resposta({}, 404))).toEqual({
      ok: false,
      erro: expect.stringContaining("404"),
    });
  });

  it("falha de rede ou JSON inválido → erro, sem lançar", async () => {
    const r1 = await carregar("indices.json", lerIndices, async () => {
      throw new TypeError("offline");
    });
    const r2 = await carregar("indices.json", lerIndices, async () => new Response("<html>"));
    expect(r1.ok).toBe(false);
    expect(r2.ok).toBe(false);
  });
});
