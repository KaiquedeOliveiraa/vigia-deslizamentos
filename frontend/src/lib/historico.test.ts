import { expect, it } from "vitest";
import { classe } from "./classes";
import { combinarHistorico, lerHistorico, primeiroDiaReal, type ArquivoHistorico } from "./historico";
import type { Municipio } from "./tipos";

const arq = (inicio: string, indices: (number | null)[]) => ({ schema_version: 1, fonte: "f", municipios: { "4214805": { inicio, indices } } });
const lerOk = (json: unknown): ArquivoHistorico => {
  const r = lerHistorico(json);
  if (!r.ok) throw new Error(r.erro);
  return r.dados;
};

const municipio = (): Municipio => ({
  ibge: "4214805",
  nome: "Itajaí",
  limiar_mm: 120,
  fonte_limiar: "GeoRisk",
  mv_h: 24,
  dias: [{ dia_alvo: "2026-10-21", d: 0, indice: 1, classe: 4, efr_mm: 0, rtotal_mm: 0, n_membros: 31, prob: { pontuais: 0, esparsos: 0, generalizados: 0 } }],
  historico: [
    { dia_alvo: "2026-10-19", indice: 0.2, classe: 1 },
    { dia_alvo: "2026-10-20", indice: 0.3, classe: 1 },
  ],
  chuva_acum_mm: { "24h": 0, "48h": 0, "72h": 0, "96h": 0 },
});

it("lê arquivo válido e recusa schema, campo, inicio e item inválidos", () => {
  expect(lerHistorico(arq("2026-10-15", [0.1, null])).ok).toBe(true);
  expect(lerHistorico({ ...arq("2026-10-15", [0.1]), schema_version: 2 }).ok).toBe(false);
  expect(lerHistorico({ schema_version: 1, municipios: {} }).ok).toBe(false); // sem fonte
  expect(lerHistorico(arq("15/10/2026", [0.1])).ok).toBe(false);
  expect(lerHistorico(arq("2026-10-15", [Number.NaN])).ok).toBe(false);
  expect(lerHistorico(arq("2026-10-15", ["0.1" as unknown as number])).ok).toBe(false);
});

it("combina com precedência indices.json > historico.json > reconstruído, sem D0", () => {
  const real = lerOk(arq("2026-10-18", [9, 9, 9, 9]));
  const reconstruido = lerOk(arq("2026-10-16", [5, 5, 5]));
  const h = combinarHistorico(municipio(), "2026-10-21", real, reconstruido).historico;
  expect(h).toEqual([
    { dia_alvo: "2026-10-16", indice: 5, classe: classe(5), reconstruido: true },
    { dia_alvo: "2026-10-17", indice: 5, classe: classe(5), reconstruido: true },
    { dia_alvo: "2026-10-18", indice: 9, classe: classe(9) },
    { dia_alvo: "2026-10-19", indice: 0.2, classe: 1 },
    { dia_alvo: "2026-10-20", indice: 0.3, classe: 1 },
  ]);
});

it("ignora valores nulos e municípios ausentes", () => {
  const h = combinarHistorico(municipio(), "2026-10-21", lerOk(arq("2026-10-17", [null, 0.5])), undefined).historico;
  expect(h.map((x) => x.dia_alvo)).toEqual(["2026-10-18", "2026-10-19", "2026-10-20"]);
  expect(combinarHistorico({ ...municipio(), ibge: "1" }, "2026-10-21", lerOk(arq("2026-10-17", [1]))).historico).toHaveLength(2);
});

it("primeiroDiaReal é o dia seguinte ao último reconstruído", () => {
  expect(primeiroDiaReal(lerOk(arq("2026-10-12", [0.1, 0.2, 0.3])))).toBe("2026-10-15");
  expect(primeiroDiaReal(undefined)).toBeNull();
});
