import { describe, expect, it } from "vitest";
import type { Municipio } from "./tipos";
import { municipiosEmAlerta, nivelAviso, simular, simularMunicipio } from "./simulacao";

const municipio = (ibge: string, nome: string, efr_mm: number, indice = 0.5): Municipio => ({
  ibge,
  nome,
  limiar_mm: 200,
  fonte_limiar: "GeoRisk",
  mv_h: 24,
  dias: [
    { dia_alvo: "2026-10-02", d: 0, indice, classe: 2, efr_mm, rtotal_mm: 10, n_membros: 31, prob: { pontuais: 0, esparsos: 0, generalizados: 0 } },
    { dia_alvo: "2026-10-03", d: 1, indice: 9, classe: 7, efr_mm: 999, rtotal_mm: 10, n_membros: 31, prob: { pontuais: 0, esparsos: 0, generalizados: 0 } },
  ],
  historico: [],
  chuva_acum_mm: { "24h": 0, "48h": 0, "72h": 0, "96h": 0 },
});

const a = municipio("4200001", "A", 100, 0.6);
const b = municipio("4200002", "B", 40, 0.3);

describe("simularMunicipio (RN07)", () => {
  it("h = 24: (EfR + chuva) ÷ limiar, com o EfR do D0", () => {
    const r = simularMunicipio(a, 60, 24);
    expect(r?.chuva_efetiva_mm).toBeCloseTo(160);
    expect(r?.indice).toBeCloseTo(0.8);
  });

  it("h = 48 com MV = 24: EfR × 0,5", () => {
    expect(simularMunicipio(a, 0, 48)?.chuva_efetiva_mm).toBeCloseTo(50);
    expect(simularMunicipio(a, 0, 48)?.indice).toBeCloseTo(0.25);
  });

  it("h = 72 com MV = 24: EfR × 0,25", () => {
    expect(simularMunicipio(a, 10, 72)?.chuva_efetiva_mm).toBeCloseTo(35);
  });

  it("limita a chuva a 0–400 mm", () => {
    expect(simularMunicipio(a, 500, 24)?.chuva_efetiva_mm).toBeCloseTo(500);
    expect(simularMunicipio(a, -20, 24)?.chuva_efetiva_mm).toBeCloseTo(100);
  });

  it("sem D0 não há simulação", () => {
    expect(simularMunicipio({ ...a, dias: a.dias.slice(1) }, 10, 24)).toBeNull();
  });
});

describe("simular", () => {
  it("modo regional aplica a mesma chuva a todos", () => {
    const r = simular([a, b], { ibge: a.ibge, chuva_mm: 60, horas: 24, regional: true });
    expect(r[a.ibge]).toBeCloseTo(0.8);
    expect(r[b.ibge]).toBeCloseTo(0.5);
  });

  it("sem modo regional só o escolhido muda; os outros ficam no índice atual", () => {
    const r = simular([a, b], { ibge: a.ibge, chuva_mm: 60, horas: 24, regional: false });
    expect(r[a.ibge]).toBeCloseTo(0.8);
    expect(r[b.ibge]).toBeCloseTo(0.3);
  });

  it("nunca altera os dados carregados", () => {
    const copia = structuredClone([a, b]);
    simular([a, b], { ibge: a.ibge, chuva_mm: 400, horas: 72, regional: true });
    expect([a, b]).toEqual(copia);
  });
});

describe("nivelAviso", () => {
  it("crit, entra, continua e ok", () => {
    expect(nivelAviso(0.5, 2.6)).toBe("crit");
    expect(nivelAviso(1.2, 3)).toBe("crit");
    expect(nivelAviso(0.99, 1.0)).toBe("entra");
    expect(nivelAviso(1.0, 2.59)).toBe("continua");
    expect(nivelAviso(1.5, 0.99)).toBe("ok");
  });
});

describe("municipiosEmAlerta", () => {
  it("devolve a lista e a contagem", () => {
    expect(municipiosEmAlerta({ "4200001": 1.0, "4200002": 0.99, "4200003": 2.7 })).toEqual({
      ibges: ["4200001", "4200003"],
      total: 2,
    });
  });
});
