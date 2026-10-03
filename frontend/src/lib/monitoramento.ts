// Regras da tela Monitoramento: resumo do dia, município inicial e variáveis do painel.
import { emAlerta } from "./classes";
import type { Dia, IndiceClasse, Indices, Municipio } from "./tipos";

export interface Resumo {
  emAlerta: number;
  /** Municípios monitorados, com ou sem dados (RF01: "N de M"). */
  total: number;
  /** `null` se nenhum município tem índice. */
  maior: number | null;
}

export function resumo(valores: Record<string, IndiceClasse | null>): Resumo {
  const indices = Object.values(valores).flatMap((v) => (v ? [v.indice] : []));
  return {
    emAlerta: indices.filter(emAlerta).length,
    total: Object.keys(valores).length,
    maior: indices.length ? Math.max(...indices) : null,
  };
}

/** O de maior índice no D0; se nenhum tem dados, o primeiro sem dados. */
export function municipioInicial(indices: Indices): string | undefined {
  let melhor: { ibge: string; indice: number } | undefined;
  for (const m of indices.municipios) {
    if (indices.municipios_sem_dados.includes(m.ibge)) continue;
    const indice = m.dias.find((x) => x.d === 0)?.indice;
    if (indice !== undefined && (!melhor || indice > melhor.indice)) melhor = { ibge: m.ibge, indice };
  }
  return melhor?.ibge ?? indices.municipios_sem_dados[0];
}

export interface Variaveis {
  efr_mm: number;
  limiar_mm: number;
  /** Chuva efetiva / limiar. */
  razao: number;
  /** Largura das barras (%): a chuva relativa ao limiar, até 100. */
  barra: number;
  n_membros: number;
}

export function variaveis(m: Pick<Municipio, "limiar_mm">, dia: Pick<Dia, "efr_mm" | "n_membros">): Variaveis {
  const razao = dia.efr_mm / m.limiar_mm;
  return { efr_mm: dia.efr_mm, limiar_mm: m.limiar_mm, razao, barra: Math.min(100, razao * 100), n_membros: dia.n_membros };
}
