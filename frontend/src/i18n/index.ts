// Textos do site escritos em português; a chave da tradução é a própria frase (dicionário do protótipo).
// Marcadores: {M} município, {C} classe de risco (traduzida), {N} número ou data.
import { CLASSES } from "../lib/classes";
import type { Idioma } from "../lib/preferencias";
import ES from "./es.json";

export type Marcador = "M" | "C" | "N";
export type Vars = Partial<Record<Marcador, string | readonly string[]>>;
export type T = (frase: string, vars?: Vars) => string;

const DICIONARIO: Record<string, string> = ES;

// Nomes mais longos primeiro: "muito alto" antes de "alto".
const NOMES_CLASSE = CLASSES.map((c) => c.nome).sort((a, b) => b.length - a.length);
export const RE_CLASSE = new RegExp(String.raw`(?<!\p{L})(${NOMES_CLASSE.join("|")})(?!\p{L})`, "u");

/** Frase já montada por src/lib com o nome da classe dentro ("↑ moderado") → modelo com {C}. */
function comoModelo(frase: string): [string, Vars] | undefined {
  const m = RE_CLASSE.exec(frase);
  if (!m) return undefined;
  const modelo = frase.replace(RE_CLASSE, "{C}");
  return modelo in DICIONARIO ? [modelo, { C: m[1] }] : undefined;
}

function traduzir(lang: Idioma, frase: string, vars: Vars = {}): string {
  let modelo = frase;
  if (lang === "es" && !(frase in DICIONARIO) && Object.keys(vars).length === 0) {
    [modelo, vars] = comoModelo(frase) ?? [frase, vars];
  }
  const texto = lang === "es" ? (DICIONARIO[modelo] ?? modelo) : modelo;
  const filas = Object.fromEntries(Object.entries(vars).map(([k, v]) => [k, typeof v === "string" ? [v] : [...v]]));
  return texto.replace(/\{([MCN])\}/g, (marca, k: Marcador) => {
    const valor = filas[k]?.shift();
    if (valor === undefined) return marca;
    return k === "C" && lang === "es" ? (DICIONARIO[valor] ?? valor) : valor;
  });
}

export const tradutor =
  (lang: Idioma): T =>
  (frase, vars) =>
    traduzir(lang, frase, vars);

/** Parâmetro [...lang] das páginas: undefined → pt, "es" → es. */
export const idioma = (param: string | undefined): Idioma => (param === "es" ? "es" : "pt");

/** getStaticPaths das páginas: cada tela em / e em /es/. */
export const caminhosIdioma = () => [{ params: { lang: undefined } }, { params: { lang: "es" } }];

export const atributoLang = (lang: Idioma): string => (lang === "es" ? "es" : "pt-BR");
