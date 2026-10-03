import { describe, expect, it } from "vitest";
import exemplo from "../fixtures/indices.exemplo.json";
import { tradutor } from "../i18n";
import type { Indices, Municipio } from "./tipos";
import {
  avisoRegional,
  avisoSimulacao,
  faixasEscala,
  municipioDaBusca,
  nivelAviso,
  posicaoEscala,
  simular,
  simularMunicipio,
} from "./simulacao";

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
    expect(r?.classe).toBe(3);
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
    expect(r[a.ibge].indice).toBeCloseTo(0.8);
    expect(r[a.ibge].classe).toBe(3);
    expect(r[b.ibge].indice).toBeCloseTo(0.5);
  });

  it("sem modo regional só o escolhido muda; os outros ficam no índice atual", () => {
    const r = simular([a, b], { ibge: a.ibge, chuva_mm: 60, horas: 24, regional: false });
    expect(r[a.ibge].indice).toBeCloseTo(0.8);
    expect(r[b.ibge]).toEqual({ indice: 0.3, classe: 2 });
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

describe("municipioDaBusca", () => {
  const indices = exemplo as Indices;

  it("?municipio=<ibge> de um município com dados", () => {
    expect(municipioDaBusca(indices, "?municipio=4209151")).toBe("4209151");
  });

  it("sem parâmetro, desconhecido ou sem dados: o de maior índice no D0", () => {
    expect(municipioDaBusca(indices, "")).toBe("4214003");
    expect(municipioDaBusca(indices, "?municipio=123")).toBe("4214003");
    expect(municipioDaBusca({ ...indices, municipios_sem_dados: ["4209151"] }, "?municipio=4209151")).toBe("4214003");
  });
});

describe("escala de 0 a 4", () => {
  it("posição em % do índice, limitada à escala", () => {
    expect(posicaoEscala(0)).toBe(0);
    expect(posicaoEscala(1)).toBe(25);
    expect(posicaoEscala(2.6)).toBeCloseTo(65);
    expect(posicaoEscala(5)).toBe(100);
  });

  it("uma faixa por classe, do início dela ao da seguinte, somando 100 %", () => {
    const faixas = faixasEscala();
    expect(faixas.map((f) => f.numero)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(faixas[0]).toEqual({ numero: 1, largura: 10 });
    expect(faixas[3].largura).toBeCloseTo(20);
    expect(faixas[6].largura).toBeCloseTo(15);
    expect(faixas.reduce((s, f) => s + f.largura, 0)).toBeCloseTo(100);
  });
});

describe("avisoSimulacao (RN04: sempre condicional)", () => {
  const t = tradutor("pt");
  const base = { nome: "Ibirama", chuva_mm: 60, horas: 48 as const };

  it("crit: risco da classe, alerta máximo e 199", () => {
    const a = avisoSimulacao(t, { ...base, atual: 0.5, simulado: 2.7 });
    expect(a.tipo).toBe("crit");
    expect(a.titulo).toBe("Risco muito alto em Ibirama");
    expect(a.texto).toContain("poderá entrar em estado de alerta máximo");
    expect(a.texto).toContain("199");
  });

  it("entra: poderá entrar em alerta", () => {
    const a = avisoSimulacao(t, { ...base, atual: 0.8, simulado: 1.2 });
    expect(a).toEqual({
      tipo: "warn",
      titulo: "Ibirama poderá entrar em alerta",
      texto: "Se essa sua previsão se concretizar, o município poderá entrar em estado de alerta (classe moderado).",
    });
  });

  it("continua: subiria ou ficaria", () => {
    expect(avisoSimulacao(t, { ...base, atual: 1.1, simulado: 1.9 })).toEqual({
      tipo: "warn",
      titulo: "Ibirama continuaria em alerta",
      texto: "Com 60 mm em 48h o índice subiria para 1,90 (classe alto).",
    });
    expect(avisoSimulacao(t, { ...base, atual: 1.9, simulado: 1.2 }).texto).toBe("Com 60 mm em 48h o índice ficaria em 1,20 (classe moderado).");
  });

  it("ok: abaixo do nível de alerta", () => {
    expect(avisoSimulacao(t, { ...base, atual: 1.5, simulado: 0.66 })).toEqual({
      tipo: "ok",
      titulo: "Abaixo do nível de alerta",
      texto: "Com 60 mm em 48h, Ibirama ficaria na classe muito baixo (0,66).",
    });
  });

  it("traduz para o espanhol", () => {
    expect(avisoSimulacao(tradutor("es"), { ...base, atual: 0.8, simulado: 1.2 }).titulo).toBe("Ibirama podría entrar en alerta");
  });
});

describe("avisoRegional", () => {
  const t = tradutor("pt");
  const nomes = { "1": "A", "2": "B", "3": "C" };
  const valores = (v: Record<string, number>) => Object.fromEntries(Object.entries(v).map(([k, indice]) => [k, { indice, classe: 1 as const }]));

  it("lista os municípios que passariam de 1,00", () => {
    expect(avisoRegional(t, valores({ "1": 1.0, "2": 0.99, "3": 3 }), nomes)).toEqual({
      tipo: "warn",
      titulo: "Chuva regional: 2 de 3 em alerta",
      texto: "Municípios que passariam de 1,00: A, C.",
    });
  });

  it("nenhum em alerta", () => {
    expect(avisoRegional(t, valores({ "1": 0.2, "2": 0.4, "3": 0.9 }), nomes)).toEqual({
      tipo: "ok",
      titulo: "Chuva regional: 0 de 3 em alerta",
      texto: "Nenhum município passaria de 1,00.",
    });
  });
});
