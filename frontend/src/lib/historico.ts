// Histórico longo: historico.json (pipeline) e historico_reconstruido.json (estimativa), combinados com o indices.json.
import { classe } from "./classes";
import { erro, type Resultado } from "./dados";
import { somarDias } from "./periodo";
import type { HistoricoItem, Municipio } from "./tipos";

const SCHEMA_VERSION = 1;

export interface ArquivoHistorico {
  fonte: string;
  municipios: Record<string, { inicio: string; indices: (number | null)[] }>;
}

const dataValida = (v: unknown): boolean => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v));

/** Campos extras (limiar_mm, mv_h do reconstruído) são aceitos e ignorados. */
export function lerHistorico(json: unknown): Resultado<ArquivoHistorico> {
  const raiz = json as (Partial<ArquivoHistorico> & { schema_version?: unknown }) | null;
  if (raiz?.schema_version !== SCHEMA_VERSION) return erro(`historico: schema_version desconhecido (${String(raiz?.schema_version)})`);
  if (typeof raiz.fonte !== "string") return erro('historico: falta o campo "fonte"');
  if (typeof raiz.municipios !== "object" || raiz.municipios === null) return erro('historico: falta o campo "municipios"');
  for (const [ibge, m] of Object.entries(raiz.municipios)) {
    if (!dataValida(m?.inicio)) return erro(`historico: inicio inválido em ${ibge}`);
    if (!Array.isArray(m.indices) || m.indices.some((x) => x !== null && !(typeof x === "number" && Number.isFinite(x))))
      return erro(`historico: indices inválidos em ${ibge}`);
  }
  return { ok: true, dados: raiz as ArquivoHistorico };
}

function itensDe(arq: ArquivoHistorico | undefined, ibge: string, reconstruido: boolean): HistoricoItem[] {
  const m = arq?.municipios[ibge];
  if (!m) return [];
  return m.indices.flatMap((indice, i) =>
    indice === null
      ? []
      : [{ dia_alvo: somarDias(m.inicio, i), indice, classe: classe(indice), ...(reconstruido && { reconstruido: true as const }) }],
  );
}

/** Precedência: indices.json > historico.json > reconstruído. Dias a partir do D0 saem (o D0 vem de `dias`). */
export function combinarHistorico(m: Municipio, d0: string, real?: ArquivoHistorico, reconstruido?: ArquivoHistorico): Municipio {
  const porDia = new Map<string, HistoricoItem>();
  for (const item of [...itensDe(reconstruido, m.ibge, true), ...itensDe(real, m.ibge, false), ...m.historico]) porDia.set(item.dia_alvo, item);
  const historico = [...porDia.values()].filter((x) => x.dia_alvo < d0).sort((a, b) => a.dia_alvo.localeCompare(b.dia_alvo));
  return { ...m, historico };
}

/** Dia seguinte ao último dia com dado em qualquer município do reconstruído. */
export function primeiroDiaReal(reconstruido?: ArquivoHistorico): string | null {
  let ultimo: string | null = null;
  for (const m of Object.values(reconstruido?.municipios ?? {})) {
    const k = m.indices.findLastIndex((x) => x !== null);
    if (k < 0) continue;
    const dia = somarDias(m.inicio, k);
    if (!ultimo || dia > ultimo) ultimo = dia;
  }
  return ultimo && somarDias(ultimo, 1);
}
