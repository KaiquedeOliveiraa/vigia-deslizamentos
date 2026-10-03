// RN07: simulação "E se chover…?" a partir das condições do D0. Nunca altera os dados carregados.
import { classe, emAlerta } from "./classes";
import type { Municipio } from "./tipos";

export type Horas = 24 | 48 | 72;

export const CHUVA_MAX_MM = 400;

export interface Simulacao {
  /** EfR do D0 decaído pela meia-vida até o fim do período, somado à chuva informada. */
  chuva_efetiva_mm: number;
  indice: number;
}

export interface Cenario {
  ibge: string;
  chuva_mm: number;
  horas: Horas;
  regional: boolean;
}

export type NivelAviso = "crit" | "entra" | "continua" | "ok";

const limitar = (mm: number): number => Math.min(Math.max(mm, 0), CHUVA_MAX_MM);

export function simularMunicipio(m: Municipio, chuva_mm: number, horas: Horas): Simulacao | null {
  const d0 = m.dias.find((d) => d.d === 0);
  if (!d0) return null;
  const chuva_efetiva_mm = d0.efr_mm * 0.5 ** ((horas - 24) / m.mv_h) + limitar(chuva_mm);
  return { chuva_efetiva_mm, indice: chuva_efetiva_mm / m.limiar_mm };
}

/** Índice por IBGE: simulado para o escolhido (ou todos, se regional); atual do D0 para os demais. */
export function simular(municipios: Municipio[], c: Cenario): Record<string, number> {
  const valores: Record<string, number> = {};
  for (const m of municipios) {
    const simulado = c.regional || m.ibge === c.ibge ? simularMunicipio(m, c.chuva_mm, c.horas) : null;
    const indice = simulado?.indice ?? m.dias.find((d) => d.d === 0)?.indice;
    if (indice !== undefined) valores[m.ibge] = indice;
  }
  return valores;
}

export function nivelAviso(atual: number, simulado: number): NivelAviso {
  if (classe(simulado) >= 6) return "crit";
  if (!emAlerta(simulado)) return "ok";
  return emAlerta(atual) ? "continua" : "entra";
}

export function municipiosEmAlerta(valores: Record<string, number>): { ibges: string[]; total: number } {
  const ibges = Object.keys(valores).filter((ibge) => emAlerta(valores[ibge]));
  return { ibges, total: ibges.length };
}
