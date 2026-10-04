import { describe, expect, it } from "vitest";
import { tradutor } from "../i18n";
import { abaPorTecla, progressoMochila, secaoAtiva } from "./cartilha";

const pt = tradutor("pt");
const es = tradutor("es");

describe("mochila de emergência", () => {
  it("conta os itens e enche a barra", () => {
    expect(progressoMochila(pt, 0, 8)).toEqual({ pct: 0, contagem: "0 de 8", mensagem: "itens na mochila", pronta: false });
    expect(progressoMochila(pt, 2, 8)).toMatchObject({ pct: 25, contagem: "2 de 8", pronta: false });
  });

  it("com todos os itens: Mochila pronta!", () => {
    expect(progressoMochila(pt, 8, 8)).toEqual({ pct: 100, contagem: "8 de 8", mensagem: "Mochila pronta!", pronta: true });
    expect(progressoMochila(es, 8, 8).mensagem).toBe("¡Mochila lista!");
    expect(progressoMochila(es, 3, 8).mensagem).toBe("ítems en la mochila");
  });
});

describe("abas Antes / Durante / Depois", () => {
  it("setas andam em círculo; Home e End vão às pontas", () => {
    expect(abaPorTecla(0, "ArrowRight", 3)).toBe(1);
    expect(abaPorTecla(2, "ArrowRight", 3)).toBe(0);
    expect(abaPorTecla(0, "ArrowLeft", 3)).toBe(2);
    expect(abaPorTecla(1, "Home", 3)).toBe(0);
    expect(abaPorTecla(0, "End", 3)).toBe(2);
  });

  it("outras teclas não mudam a aba", () => {
    expect(abaPorTecla(1, "Enter", 3)).toBeNull();
    expect(abaPorTecla(1, "ArrowDown", 3)).toBeNull();
  });
});

describe("seção visível na navegação por âncoras", () => {
  it("última seção cujo topo já passou do limite", () => {
    expect(secaoAtiva([10, 600, 1200, 1800], 70, false)).toBe(0);
    expect(secaoAtiva([-700, -100, 60, 700], 70, false)).toBe(2);
  });

  it("antes da primeira seção, a primeira; no fim da rolagem, a última", () => {
    expect(secaoAtiva([300, 900], 70, false)).toBe(0);
    expect(secaoAtiva([-900, -300, 200, 500], 70, true)).toBe(3);
  });
});
