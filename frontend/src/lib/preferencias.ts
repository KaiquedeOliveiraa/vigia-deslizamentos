// Preferências do usuário (RF13), guardadas no navegador quando ele deixa.

export type Idioma = "pt" | "es";
export type Tema = "auto" | "light" | "dark" | "contraste";
export type Paleta = "geo" | "acc";

export interface Preferencias {
  lang: Idioma;
  theme: Tema;
  pal: Paleta;
}

/** Mesma chave do script inline do Base.astro, que aplica tema e paleta antes da pintura. */
export const CHAVE = "vigia-pref";

export const PADRAO: Preferencias = { lang: "pt", theme: "auto", pal: "geo" };

const VALIDOS: { [K in keyof Preferencias]: readonly Preferencias[K][] } = {
  lang: ["pt", "es"],
  theme: ["auto", "light", "dark", "contraste"],
  pal: ["geo", "acc"],
};

type Armazenamento = Pick<Storage, "getItem" | "setItem">;
const local = (): Armazenamento => localStorage;

/** Lê as preferências; armazenamento indisponível, JSON quebrado ou valor desconhecido → padrão. */
export function lerPreferencias(armazenamento: () => Armazenamento = local): Preferencias {
  let salvo: Partial<Record<keyof Preferencias, unknown>> = {};
  try {
    salvo = JSON.parse(armazenamento().getItem(CHAVE) ?? "{}") ?? {};
  } catch {
    return { ...PADRAO };
  }
  const valor = <K extends keyof Preferencias>(k: K): Preferencias[K] =>
    VALIDOS[k].includes(salvo[k] as Preferencias[K]) ? (salvo[k] as Preferencias[K]) : PADRAO[k];
  return { lang: valor("lang"), theme: valor("theme"), pal: valor("pal") };
}

export function salvarPreferencias(p: Preferencias, armazenamento: () => Armazenamento = local): void {
  try {
    armazenamento().setItem(CHAVE, JSON.stringify(p));
  } catch {
    // Sem armazenamento (modo privado, bloqueio): a escolha vale só nesta página.
  }
}

type Raiz = Pick<HTMLElement, "setAttribute" | "removeAttribute"> & {
  classList: Pick<DOMTokenList, "toggle">;
};

/** Tema em `data-theme` (auto = sem atributo) e paleta em `pal-geo`/`pal-acc`, ambos no <html>. */
export function aplicarPreferencias(p: Preferencias, raiz: Raiz): void {
  if (p.theme === "auto") raiz.removeAttribute("data-theme");
  else raiz.setAttribute("data-theme", p.theme);
  raiz.classList.toggle("pal-acc", p.pal === "acc");
  raiz.classList.toggle("pal-geo", p.pal !== "acc");
}
