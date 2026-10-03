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
  ocorrenciasDoMunicipio,
  separarPorDados,
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

  it("dia sem n_membros (mostrado na tela) → erro", () => {
    const sem = copia(indices) as { municipios: { dias: Record<string, unknown>[] }[] };
    delete sem.municipios[0].dias[0].n_membros;
    expect(lerIndices(sem)).toEqual({ ok: false, erro: expect.stringContaining("n_membros") });
  });

  it("municipios ou dias que não são listas → erro, sem lançar", () => {
    expect(lerIndices({ ...copia(indices), municipios: {} }).ok).toBe(false);
    const dias = copia(indices) as { municipios: Record<string, unknown>[] };
    dias.municipios[0].dias = "x";
    expect(lerIndices(dias).ok).toBe(false);
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

describe("separarPorDados", () => {
  const base = indices as Indices;
  const nomes = [
    { ibge: "4200009", nome: "Witmarsum" },
    { ibge: base.municipios[1].ibge, nome: base.municipios[1].nome },
  ];

  it("municípios com D0 de um lado; os de municipios_sem_dados (com o nome) e os sem D0 do outro", () => {
    const semD0 = { ...base.municipios[1], dias: base.municipios[1].dias.filter((d) => d.d !== 0) };
    const d: Indices = { ...base, municipios_sem_dados: ["4200009"], municipios: [base.municipios[0], semD0] };
    const r = separarPorDados(d, nomes);
    expect(r.comDados.map((m) => m.ibge)).toEqual([base.municipios[0].ibge]);
    expect(r.semDados).toEqual([
      { ibge: "4200009", nome: "Witmarsum" },
      { ibge: semD0.ibge, nome: semD0.nome },
    ]);
  });

  it("código sem nome conhecido aparece pelo código", () => {
    expect(separarPorDados({ ...base, municipios_sem_dados: ["4299999"] }, nomes).semDados).toEqual([{ ibge: "4299999", nome: "4299999" }]);
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

describe("ocorrenciasDoMunicipio", () => {
  it("só as do município, da mais recente para a mais antiga", () => {
    const o = (ibge: string, data: string) => ({ ibge, data, tipo: "deslizamento", descricao: "", fonte: "S2iD" });
    const lista = [o("1", "2020-01-05"), o("2", "2024-01-01"), o("1", "2023-10-06"), o("1", "2021-07-30")];
    expect(ocorrenciasDoMunicipio(lista, "1").map((x) => x.data)).toEqual(["2023-10-06", "2021-07-30", "2020-01-05"]);
    expect(ocorrenciasDoMunicipio(lista, "3")).toEqual([]);
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
