import { describe, expect, it } from "vitest";
import {
  CHAVE,
  PADRAO,
  aplicarPreferencias,
  lerPreferencias,
  paletaAplicada,
  salvarPreferencias,
  trocarPaleta,
} from "./preferencias";

const memoria = (inicial: Record<string, string> = {}) => {
  const dados = { ...inicial };
  return {
    dados,
    getItem: (k: string) => dados[k] ?? null,
    setItem: (k: string, v: string) => void (dados[k] = v),
  };
};
const indisponivel = () => {
  throw new Error("SecurityError");
};

describe("lerPreferencias", () => {
  it("sem nada guardado → padrão pt, auto, geo", () => {
    expect(lerPreferencias(memoria)).toEqual({ lang: "pt", theme: "auto", pal: "geo" });
    expect(PADRAO).toEqual({ lang: "pt", theme: "auto", pal: "geo" });
  });

  it("localStorage indisponível → padrão (RF13)", () => {
    expect(lerPreferencias(indisponivel)).toEqual(PADRAO);
  });

  it("valores guardados válidos são usados; inválidos ou JSON quebrado voltam ao padrão", () => {
    const ok = memoria({ [CHAVE]: JSON.stringify({ lang: "es", theme: "contraste", pal: "acc" }) });
    expect(lerPreferencias(() => ok)).toEqual({ lang: "es", theme: "contraste", pal: "acc" });
    const ruim = memoria({ [CHAVE]: JSON.stringify({ lang: "fr", theme: "dark" }) });
    expect(lerPreferencias(() => ruim)).toEqual({ lang: "pt", theme: "dark", pal: "geo" });
    expect(lerPreferencias(() => memoria({ [CHAVE]: "{" }))).toEqual(PADRAO);
  });
});

describe("salvarPreferencias", () => {
  it("guarda e relê", () => {
    const m = memoria();
    salvarPreferencias({ lang: "es", theme: "dark", pal: "acc" }, () => m);
    expect(lerPreferencias(() => m)).toEqual({ lang: "es", theme: "dark", pal: "acc" });
  });

  it("localStorage indisponível não lança", () => {
    expect(() => salvarPreferencias(PADRAO, indisponivel)).not.toThrow();
  });
});

const raiz = () => {
  const attrs: Record<string, string> = {};
  const classes = new Set<string>();
  return {
    attrs,
    classes,
    setAttribute: (k: string, v: string) => void (attrs[k] = v),
    removeAttribute: (k: string) => void delete attrs[k],
    classList: {
      toggle: (c: string, on: boolean) => (on ? classes.add(c) : classes.delete(c), on),
      contains: (c: string) => classes.has(c),
    },
  };
};

describe("aplicarPreferencias", () => {
  it("tema auto = sem data-theme; paleta vira classe pal-*", () => {
    const r = raiz();
    aplicarPreferencias({ lang: "pt", theme: "dark", pal: "acc" }, r);
    expect(r.attrs["data-theme"]).toBe("dark");
    expect([...r.classes]).toEqual(["pal-acc"]);
    aplicarPreferencias(PADRAO, r);
    expect(r.attrs["data-theme"]).toBeUndefined();
    expect([...r.classes]).toEqual(["pal-geo"]);
  });
});

describe("paleta (legenda e painel de acessibilidade)", () => {
  it("trocarPaleta guarda só a paleta e troca a classe do <html>; paletaAplicada lê essa classe", () => {
    const m = memoria({ [CHAVE]: JSON.stringify({ lang: "es", theme: "dark", pal: "geo" }) });
    const r = raiz();
    trocarPaleta("acc", r, () => m);
    expect(lerPreferencias(() => m)).toEqual({ lang: "es", theme: "dark", pal: "acc" });
    expect(paletaAplicada(r)).toBe("acc");
    trocarPaleta("geo", r, () => m);
    expect([...r.classes]).toEqual(["pal-geo"]);
    expect(paletaAplicada(r)).toBe("geo");
  });

  it("sem armazenamento a troca vale na página", () => {
    const r = raiz();
    trocarPaleta("acc", r, indisponivel);
    expect(paletaAplicada(r)).toBe("acc");
  });
});
