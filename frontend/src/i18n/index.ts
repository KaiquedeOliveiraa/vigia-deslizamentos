// Textos do site escritos em português; a chave da tradução é a própria frase (dicionário do protótipo).
// Marcadores: {M} município, {C} classe de risco (traduzida), {N} número ou data.
import { CLASSES } from "../lib/classes";
import type { Idioma } from "../lib/preferencias";
import EN from "./en.json";
import ES from "./es.json";

export type Marcador = "M" | "C" | "N";
export type Vars = Partial<Record<Marcador, string | readonly string[]>>;
export type T = (frase: string, vars?: Vars) => string;

const DICIONARIOS: Record<Exclude<Idioma, "pt">, Record<string, string>> = { es: ES, en: EN };

// Nomes mais longos primeiro: "muito alto" antes de "alto".
const NOMES_CLASSE = CLASSES.map((c) => c.nome).sort((a, b) => b.length - a.length);
export const RE_CLASSE = new RegExp(String.raw`(?<!\p{L})(${NOMES_CLASSE.join("|")})(?!\p{L})`, "u");

/** Frase já montada por src/lib com o nome da classe dentro ("↑ moderado") → modelo com {C}. */
function comoModelo(frase: string, dicionario: Record<string, string>): [string, Vars] | undefined {
  const m = RE_CLASSE.exec(frase);
  if (!m) return undefined;
  const modelo = frase.replace(RE_CLASSE, "{C}");
  return modelo in dicionario ? [modelo, { C: m[1] }] : undefined;
}

function traduzir(lang: Idioma, frase: string, vars: Vars = {}): string {
  const dicionario = lang === "pt" ? undefined : DICIONARIOS[lang];
  let modelo = frase;
  if (dicionario && !(frase in dicionario) && Object.keys(vars).length === 0) {
    [modelo, vars] = comoModelo(frase, dicionario) ?? [frase, vars];
  }
  const texto = dicionario?.[modelo] ?? modelo;
  const filas = Object.fromEntries(Object.entries(vars).map(([k, v]) => [k, typeof v === "string" ? [v] : [...v]]));
  return texto.replace(/\{([MCN])\}/g, (marca, k: Marcador) => {
    const valor = filas[k]?.shift();
    if (valor === undefined) return marca;
    return k === "C" && dicionario ? (dicionario[valor] ?? valor) : valor;
  });
}

export const tradutor =
  (lang: Idioma): T =>
  (frase, vars) =>
    traduzir(lang, frase, vars);

/** Parâmetro [...lang] das páginas: undefined → pt, "es" → es, "en" → en. */
export const idioma = (param: string | undefined): Idioma => (param === "es" || param === "en" ? param : "pt");

/** getStaticPaths das páginas: cada tela em /, /es/ e /en/. */
export const caminhosIdioma = () => [{ params: { lang: undefined } }, { params: { lang: "es" } }, { params: { lang: "en" } }];

export const atributoLang = (lang: Idioma): string => (lang === "pt" ? "pt-BR" : lang);
