import { describe, expect, it } from "vitest";
import { buscar, normalizar, sentido, tendencia, textoCompartilhar } from "./texto";
import { tradutor } from "../i18n";
import type { HistoricoItem } from "./tipos";

const historico = (indice: number): HistoricoItem[] => [
  { dia_alvo: "2026-09-27", indice: 0.1, classe: 1 },
  { dia_alvo: "2026-09-28", indice, classe: 4 },
];

describe("tendencia", () => {
  it("compara com o dia anterior, com folga de ±0,005", () => {
    expect(tendencia(1.34, "2026-09-29", historico(1.0))).toBe("subindo");
    expect(tendencia(0.9, "2026-09-29", historico(1.0))).toBe("descendo");
    expect(tendencia(1.004, "2026-09-29", historico(1.0))).toBe("estável");
    expect(tendencia(0.505, "2026-09-29", historico(0.5))).toBe("estável");
    expect(tendencia(0.495, "2026-09-29", historico(0.5))).toBe("estável");
    expect(tendencia(0.5051, "2026-09-29", historico(0.5))).toBe("subindo");
  });

  it("sem o dia anterior no historico, não há tendência", () => {
    expect(tendencia(1.34, "2026-09-30", historico(1.0))).toBeNull();
    expect(tendencia(1.34, "2026-09-29", [])).toBeNull();
  });

  it("o dia anterior atravessa a virada do mês", () => {
    expect(tendencia(1, "2026-10-01", [{ dia_alvo: "2026-09-30", indice: 2, classe: 5 }])).toBe("descendo");
  });
});

describe("busca", () => {
  it("ignora acento e maiúsculas", () => {
    expect(normalizar("José Boiteux")).toBe("jose boiteux");
    const lista = [{ nome: "Ibirama" }, { nome: "José Boiteux" }];
    expect(buscar(lista, "jose")).toEqual([{ nome: "José Boiteux" }]);
    expect(buscar(lista, " BOITÉUX ")).toEqual([{ nome: "José Boiteux" }]);
    expect(buscar(lista, "")).toEqual(lista);
  });
});

describe("textoCompartilhar", () => {
  it("município, classe e índice", () => {
    expect(textoCompartilhar("Ibirama", { indice: 1.3449, classe: 4 })).toBe("Ibirama — moderado (1,34)");
  });

  it("traduz o nome da classe", () => {
    expect(textoCompartilhar("Ibirama", { indice: 3, classe: 6 }, tradutor("es"))).toBe("Ibirama — muy alto (3,00)");
  });
});

describe("sentido", () => {
  it("diferença entre dois índices, com folga de ±0,005", () => {
    expect(sentido(0.006)).toBe("subindo");
    expect(sentido(-0.006)).toBe("descendo");
    expect(sentido(0.005)).toBe("estável");
    expect(sentido(-0.005)).toBe("estável");
  });
});
