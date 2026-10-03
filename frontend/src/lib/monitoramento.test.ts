import { describe, expect, it } from "vitest";
import exemplo from "../fixtures/indices.exemplo.json";
import { municipioInicial, resumo, variaveis } from "./monitoramento";
import type { Indices } from "./tipos";

const indices = exemplo as Indices;

describe("resumo", () => {
  it("conta os em alerta (≥ 1,00) entre todos os monitorados e acha o maior índice", () => {
    expect(resumo({ a: 1, b: 0.9999, c: 1.924, d: null })).toEqual({ emAlerta: 2, total: 4, maior: 1.924 });
  });

  it("sem nenhum índice: maior = null", () => {
    expect(resumo({ a: null })).toEqual({ emAlerta: 0, total: 1, maior: null });
  });
});

describe("municipioInicial", () => {
  it("o de maior índice no D0", () => {
    expect(municipioInicial(indices)).toBe("4214003");
  });

  it("ignora os sem dados; se nenhum tem dados, o primeiro sem dados", () => {
    expect(municipioInicial({ ...indices, municipios_sem_dados: ["4214003"] })).toBe("4206900");
    expect(municipioInicial({ ...indices, municipios: [], municipios_sem_dados: ["4205100"] })).toBe("4205100");
  });
});

describe("variaveis", () => {
  it("chuva, limiar, razão e barra relativa ao limiar", () => {
    const v = variaveis({ limiar_mm: 100 }, { efr_mm: 60, n_membros: 20 });
    expect(v).toEqual({ efr_mm: 60, limiar_mm: 100, razao: 0.6, barra: 60, n_membros: 20 });
  });

  it("barra limitada a 100 %", () => {
    expect(variaveis({ limiar_mm: 50 }, { efr_mm: 80, n_membros: 20 }).barra).toBe(100);
  });
});
