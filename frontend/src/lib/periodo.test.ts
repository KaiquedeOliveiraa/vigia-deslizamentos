import { afterEach, expect, it, vi } from "vitest";
import { ajustarPersonalizado, eixoDoPeriodo, escreverPeriodo, lerPeriodo, limitesPersonalizado, somarDias } from "./periodo";

const D0 = "2026-10-21";

afterEach(() => vi.useRealTimers());

it("soma dias atravessando mês", () => {
  expect(somarDias("2026-03-01", -1)).toBe("2026-02-28");
});

it("monta o eixo de cada período", () => {
  const e30 = eixoDoPeriodo({ tipo: 30 }, D0);
  expect(e30).toHaveLength(30);
  expect(e30[29]).toBe(D0);
  expect(eixoDoPeriodo({ tipo: "personalizado", de: "2026-10-05", ate: "2026-10-05" }, D0)).toEqual(["2026-10-05"]);
});

it("o eixo não depende do relógio (22h30 em Brasília já é 22/10 em UTC)", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-22T01:30:00Z"));
  expect(eixoDoPeriodo({ tipo: 7 }, D0).at(-1)).toBe(D0);
});

it("limites e ajuste do personalizado", () => {
  expect(limitesPersonalizado(D0)).toEqual({ min: "2025-10-21", max: D0 });
  expect(ajustarPersonalizado("2025-01-01", "2026-12-31", D0)).toEqual({ de: "2025-10-21", ate: D0, ajustado: true });
  expect(ajustarPersonalizado("2026-10-10", "2026-10-01", D0)).toEqual({ de: "2026-10-01", ate: "2026-10-10", ajustado: true });
  expect(ajustarPersonalizado("2026-10-01", "2026-10-10", D0)).toEqual({ de: "2026-10-01", ate: "2026-10-10", ajustado: false });
  expect(ajustarPersonalizado("2026-02-30", "2026-10-10", D0)).toBeNull();
});

it("lê o período da URL", () => {
  expect(lerPeriodo("?periodo=30", D0).periodo).toEqual({ tipo: 30 });
  expect(lerPeriodo("?periodo=15", D0).periodo).toEqual({ tipo: 7 });
  expect(lerPeriodo("", D0).periodo).toEqual({ tipo: 7 });
  expect(lerPeriodo("?de=2026-10-01&ate=2026-10-10", D0)).toEqual({ periodo: { tipo: "personalizado", de: "2026-10-01", ate: "2026-10-10" }, ajustado: false });
});

it("escreve o período na URL sem perder o resto", () => {
  expect(escreverPeriodo("?municipio=4214805", { tipo: 7 })).toBe("?municipio=4214805");
  expect(escreverPeriodo("", { tipo: 7 })).toBe("");
  expect(escreverPeriodo("?municipio=1", { tipo: 30 })).toBe("?municipio=1&periodo=30");
  expect(escreverPeriodo("?periodo=30", { tipo: "personalizado", de: "2026-10-01", ate: "2026-10-10" })).toBe("?de=2026-10-01&ate=2026-10-10");
});
