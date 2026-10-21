// Setores de risco geológico do SGB (tela Áreas de risco): leitura do GeoJSON, resumos e seleção na URL.
import type { Resultado } from "./dados";
import { NOMES } from "./municipios";

export type TipoSetor = "deslizamento" | "rastejo" | "corrida_massa" | "queda";
export type GrauSetor = "alto" | "muito_alto";

export interface Setor {
  id: string;
  ibge: string;
  centro: [number, number];
  local: string | null;
  tipo: TipoSetor;
  grau: GrauSetor;
  descricao: string | null;
  recomendacao: string | null;
  pessoas: number | null;
  moradias: number | null;
  data: string | null;
  /** Anéis do polígono em [lat, lon], prontos para o Leaflet (MultiPolygon: um item por parte). */
  aneis: [number, number][][][];
}

export interface ColecaoSetores {
  setores: Setor[];
  fonte: string;
  geradoEm: string;
}

export const ROTULO_TIPO: Record<TipoSetor, string> = {
  deslizamento: "Deslizamento",
  rastejo: "Rastejo",
  corrida_massa: "Corrida de massa",
  queda: "Queda",
};

/** Nunca "alto"/"muito alto" sozinhos: são também nomes das classes do índice de chuva. */
export const ROTULO_GRAU: Record<GrauSetor, string> = {
  alto: "risco geológico alto",
  muito_alto: "risco geológico muito alto",
};

const TIPOS = new Set(Object.keys(ROTULO_TIPO));
const GRAUS = new Set(Object.keys(ROTULO_GRAU));
const erro = (mensagem: string): Resultado<never> => ({ ok: false, erro: mensagem });
const textoOuNulo = (v: unknown) => (typeof v === "string" ? v : null);
const inteiroOuNulo = (v: unknown) => (Number.isInteger(v) ? (v as number) : null);
const inverter = (anel: [number, number][]) => anel.map(([lon, lat]) => [lat, lon] as [number, number]);

function aneisDe(g: { type?: unknown; coordinates?: unknown } | undefined): [number, number][][][] | null {
  if (g?.type === "Polygon" && Array.isArray(g.coordinates)) return [(g.coordinates as [number, number][][]).map(inverter)];
  if (g?.type === "MultiPolygon" && Array.isArray(g.coordinates))
    return (g.coordinates as [number, number][][][]).map((p) => p.map(inverter));
  return null;
}

/** Lê o setores_risco.geojson; feições inválidas são descartadas (um setor ruim não derruba a tela). */
export function lerSetores(json: unknown): Resultado<ColecaoSetores> {
  const raiz = json as { type?: unknown; features?: unknown; fonte?: unknown; gerado_em?: unknown } | null;
  if (!raiz || raiz.type !== "FeatureCollection" || !Array.isArray(raiz.features))
    return erro("setores_risco.geojson: raiz não é FeatureCollection");
  const setores: Setor[] = [];
  for (const f of raiz.features as { geometry?: { type?: unknown; coordinates?: unknown }; properties?: Record<string, unknown> }[]) {
    const p = f?.properties;
    const aneis = aneisDe(f?.geometry);
    const centro = p?.centro;
    if (
      !p || !aneis || typeof p.id !== "string" || typeof p.ibge !== "string" ||
      !TIPOS.has(p.tipo as string) || !GRAUS.has(p.grau as string) ||
      !Array.isArray(centro) || centro.length !== 2 || !centro.every(Number.isFinite) ||
      setores.some((s) => s.id === p.id)
    )
      continue;
    setores.push({
      id: p.id,
      ibge: p.ibge,
      centro: centro as [number, number],
      local: textoOuNulo(p.local),
      tipo: p.tipo as TipoSetor,
      grau: p.grau as GrauSetor,
      descricao: textoOuNulo(p.descricao),
      recomendacao: textoOuNulo(p.recomendacao),
      pessoas: inteiroOuNulo(p.pessoas),
      moradias: inteiroOuNulo(p.moradias),
      data: textoOuNulo(p.data),
      aneis,
    });
  }
  return { ok: true, dados: { setores, fonte: String(raiz.fonte ?? ""), geradoEm: String(raiz.gerado_em ?? "") } };
}

export interface Resumo {
  setores: number;
  muitoAlto: number;
  alto: number;
  pessoas: number;
  municipios: number;
  anoMin: number | null;
  anoMax: number | null;
}

/** Pessoas: só valores conhecidos ("pessoas nos setores mapeados", nunca "em risco no município"). */
export function resumo(setores: Setor[]): Resumo {
  const anos = setores.flatMap((s) => (s.data ? [Number(s.data.slice(0, 4))] : []));
  return {
    setores: setores.length,
    muitoAlto: setores.filter((s) => s.grau === "muito_alto").length,
    alto: setores.filter((s) => s.grau === "alto").length,
    pessoas: setores.reduce((soma, s) => soma + (s.pessoas ?? 0), 0),
    municipios: new Set(setores.map((s) => s.ibge)).size,
    anoMin: anos.length ? Math.min(...anos) : null,
    anoMax: anos.length ? Math.max(...anos) : null,
  };
}

/** Municípios com setores: mais setores primeiro, desempate pelo nome. */
export function porMunicipio(setores: Setor[]): { ibge: string; setores: Setor[] }[] {
  const grupos = new Map<string, Setor[]>();
  for (const s of setores) grupos.set(s.ibge, [...(grupos.get(s.ibge) ?? []), s]);
  const nome = (ibge: string) => NOMES.get(ibge) ?? ibge;
  return [...grupos]
    .map(([ibge, lista]) => ({ ibge, setores: lista }))
    .sort((a, b) => b.setores.length - a.setores.length || nome(a.ibge).localeCompare(nome(b.ibge), "pt-BR"));
}

export function lerSelecao(
  busca: string,
  setores: Setor[],
  ibgesMonitorados: ReadonlySet<string>,
): { municipio: string | null; setor: string | null } {
  const q = new URLSearchParams(busca);
  const setor = setores.find((s) => s.id === q.get("setor"));
  if (setor) return { municipio: setor.ibge, setor: setor.id };
  const m = q.get("municipio");
  return { municipio: m && ibgesMonitorados.has(m) ? m : null, setor: null };
}

export function escreverSelecao(busca: string, sel: { municipio: string | null; setor: string | null }): string {
  const q = new URLSearchParams(busca);
  q.delete("municipio");
  q.delete("setor");
  if (sel.municipio) q.set("municipio", sel.municipio);
  if (sel.setor) q.set("setor", sel.setor);
  const texto = q.toString();
  return texto ? `?${texto}` : "";
}

/** De longe e sem município escolhido: um marcador por município (os 98 setores se sobreporiam). */
export const mostrarSetoresIndividuais = (municipioSelecionado: boolean, longe: boolean): boolean => municipioSelecionado || !longe;
