import { classe, infoClasse } from "./classes";
import { formatarIndice } from "./formato";
import type { HistoricoItem } from "./tipos";

export type Tendencia = "subindo" | "descendo" | "estável";

const FOLGA = 0.005;

function diaAnterior(dia_alvo: string): string {
  const d = new Date(`${dia_alvo}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

/** Sentido de uma diferença entre dois índices, com folga de ±0,005. */
export function sentido(diferenca: number): Tendencia {
  // Índices têm 4 casas: arredonda a diferença para a fronteira de ±0,005 não depender de erro de ponto flutuante.
  const delta = Math.round(diferenca * 1e4) / 1e4;
  if (delta > FOLGA) return "subindo";
  if (delta < -FOLGA) return "descendo";
  return "estável";
}

/** Índice − índice do dia anterior no `historico`; `null` se esse dia não estiver lá. */
export function tendencia(indice: number, dia_alvo: string, historico: HistoricoItem[]): Tendencia | null {
  const anterior = historico.find((h) => h.dia_alvo === diaAnterior(dia_alvo));
  return anterior ? sentido(indice - anterior.indice) : null;
}

/** Minúsculas e sem acento, para a busca. */
export const normalizar = (s: string): string => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

export function buscar<T extends { nome: string }>(lista: T[], termo: string): T[] {
  const q = normalizar(termo.trim());
  return lista.filter((m) => normalizar(m.nome).includes(q));
}

/** `traduzir` recebe o nome da classe em português. */
export const textoCompartilhar = (nome: string, indice: number, traduzir = (s: string) => s): string =>
  `${nome} — ${traduzir(infoClasse(classe(indice)).nome)} (${formatarIndice(indice)})`;
