// Período do gráfico de evolução: 7 dias, 30 dias ou um intervalo personalizado (até 1 ano), na URL.
export type Periodo = { tipo: 7 | 30 } | { tipo: "personalizado"; de: string; ate: string };

export const somarDias = (dia: string, n: number): string =>
  new Date(Date.parse(`${dia}T00:00:00Z`) + n * 86_400_000).toISOString().slice(0, 10);

/** Data AAAA-MM-DD existente (a ida e volta recusa 2026-02-30). */
const dataValida = (d: string): boolean => /^\d{4}-\d{2}-\d{2}$/.test(d) && !Number.isNaN(Date.parse(d)) && somarDias(d, 0) === d;

function dias(de: string, ate: string): string[] {
  const n = (Date.parse(ate) - Date.parse(de)) / 86_400_000 + 1;
  return Array.from({ length: n }, (_, i) => somarDias(de, i));
}

/** Os dias do período, do mais antigo ao mais recente; 7 e 30 terminam no D0. */
export const eixoDoPeriodo = (p: Periodo, d0: string): string[] =>
  p.tipo === "personalizado" ? dias(p.de, p.ate) : dias(somarDias(d0, 1 - p.tipo), d0);

/** O personalizado vai de um ano antes do D0 até o D0. */
export function limitesPersonalizado(d0: string): { min: string; max: string } {
  const [a, m, d] = d0.split("-");
  return { min: `${Number(a) - 1}-${m}-${d}`, max: d0 };
}

/** Troca a ordem e corta nos limites; `null` se alguma data não existe. */
export function ajustarPersonalizado(de: string, ate: string, d0: string): { de: string; ate: string; ajustado: boolean } | null {
  if (!dataValida(de) || !dataValida(ate)) return null;
  const { min, max } = limitesPersonalizado(d0);
  const corta = (d: string) => (d < min ? min : d > max ? max : d);
  const [a, b] = de <= ate ? [de, ate] : [ate, de];
  const novoDe = corta(a);
  const novoAte = corta(b);
  return { de: novoDe, ate: novoAte, ajustado: novoDe !== de || novoAte !== ate };
}

export function lerPeriodo(busca: string, d0: string): { periodo: Periodo; ajustado: boolean } {
  const q = new URLSearchParams(busca);
  const aj = ajustarPersonalizado(q.get("de") ?? "", q.get("ate") ?? "", d0);
  if (aj) return { periodo: { tipo: "personalizado", de: aj.de, ate: aj.ate }, ajustado: aj.ajustado };
  return { periodo: { tipo: q.get("periodo") === "30" ? 30 : 7 }, ajustado: false };
}

export function escreverPeriodo(busca: string, p: Periodo): string {
  const q = new URLSearchParams(busca);
  q.delete("periodo");
  q.delete("de");
  q.delete("ate");
  if (p.tipo === 30) q.set("periodo", "30");
  if (p.tipo === "personalizado") {
    q.set("de", p.de);
    q.set("ate", p.ate);
  }
  const texto = q.toString();
  return texto ? `?${texto}` : "";
}
