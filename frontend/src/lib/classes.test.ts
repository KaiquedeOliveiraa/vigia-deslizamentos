import { describe, expect, it } from "vitest";
// Lido do backend a cada execução: se as faixas mudarem lá, este teste acusa a diferença.
import classesPy from "../../../backend/app/classificacao/classes.py?raw";
import { CLASSE_CRITICA, CLASSES, LIMIAR_ALERTA, NAO_MONITORADO, SEM_DADOS, classe, emAlerta, infoClasse } from "./classes";

describe("paridade com backend/app/classificacao/classes.py", () => {
  it("limite inferior de cada classe igual ao do backend", () => {
    const bloco = classesPy.match(/_LIMITES_INFERIORES_POR_CLASSE = \(([\s\S]*?)^\)/m)?.[1] ?? "";
    const limites = [...bloco.matchAll(/\((\d+),\s*([\d.]+)\)/g)].map(([, n, min]) => [Number(n), Number(min)]);
    expect(limites).toHaveLength(CLASSES.length - 1);
    expect(Object.fromEntries(limites)).toEqual(Object.fromEntries(CLASSES.slice(1).map((c) => [c.numero, c.min])));
    expect(CLASSES[0].min).toBe(0);
  });

  it("mesmo gatilho de alerta (RN02)", () => {
    expect(Number(classesPy.match(/^LIMIAR_ALERTA = ([\d.]+)/m)?.[1])).toBe(LIMIAR_ALERTA);
  });
});

describe("classe", () => {
  it("usa as mesmas faixas [a, b) do backend", () => {
    expect(classe(0)).toBe(1);
    expect(classe(0.3999)).toBe(1);
    expect(classe(0.4)).toBe(2);
    expect(classe(0.7)).toBe(3);
    expect(classe(0.9999)).toBe(3);
    expect(classe(1.0)).toBe(4);
    expect(classe(1.8)).toBe(5);
    expect(classe(2.6)).toBe(6);
    expect(classe(3.4)).toBe(7);
    expect(classe(10)).toBe(7);
  });

  it("classe crítica (alerta máximo na simulação) começa em 2,60", () => {
    expect(infoClasse(CLASSE_CRITICA)).toMatchObject({ numero: 6, nome: "muito alto", min: 2.6 });
  });

  it("alerta a partir de 1,00 (RN02)", () => {
    expect(emAlerta(0.9999)).toBe(false);
    expect(emAlerta(1.0)).toBe(true);
  });
});

describe("CLASSES", () => {
  it("nome, faixa, cores e ícone de cada classe", () => {
    expect(CLASSES.map((c) => c.nome)).toEqual([
      "extremamente baixo", "muito baixo", "baixo", "moderado", "alto", "muito alto", "extremamente alto",
    ]);
    expect(CLASSES.map((c) => c.faixa)).toEqual([
      "< 0,40", "0,40 – 0,70", "0,70 – 1,00", "1,00 – 1,80", "1,80 – 2,60", "2,60 – 3,40", "≥ 3,40",
    ]);
    expect(CLASSES[3]).toMatchObject({ numero: 4, cor: "var(--c4)", corIcone: "var(--ci4)" });
    expect(CLASSES.map((c) => c.icone)).toEqual([
      "circulo-check", "circulo-check", "olho", "triangulo-exclamacao", "triangulo-exclamacao-dupla", "octogono-exclamacao", "octogono-x",
    ]);
  });

  it("hachura a partir do moderado, cruzada nas classes 6 e 7 (RN03)", () => {
    expect(CLASSES.map((c) => c.hachura)).toEqual([
      null, null, null,
      { espacamento: 16, cruzada: false },
      { espacamento: 11, cruzada: false },
      { espacamento: 8, cruzada: true },
      { espacamento: 6, cruzada: true },
    ]);
  });

  it("não monitorado e sem dados não têm classe", () => {
    expect(NAO_MONITORADO).toEqual({ nome: "não monitorado", cor: "var(--risk-nm)" });
    expect(SEM_DADOS).toEqual({ nome: "sem dados", cor: "var(--risk-nm)" });
  });
});
