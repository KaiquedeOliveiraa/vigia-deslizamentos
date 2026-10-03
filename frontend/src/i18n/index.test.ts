import { describe, expect, it } from "vitest";
import { marcaClasse } from "../lib/graficos";
import { TELAS } from "../lib/telas";
import ES from "./es.json";
import { RE_CLASSE, tradutor } from "./index";

const pt = tradutor("pt");
const es = tradutor("es");

describe("t", () => {
  it("frase exata", () => {
    expect(es("Alertas no Telegram")).toBe("Alertas en Telegram");
    expect(pt("Alertas no Telegram")).toBe("Alertas no Telegram");
  });

  it("substitui os marcadores na ordem, em PT e em ES", () => {
    const vars = { N: ["29/09/2026", "06:12"] };
    expect(pt("dia-alvo {N} · atualizado {N}", vars)).toBe("dia-alvo 29/09/2026 · atualizado 06:12");
    expect(es("dia-alvo {N} · atualizado {N}", vars)).toBe("día objetivo 29/09/2026 · actualizado 06:12");
  });

  it("{C} é traduzido; {M} e {N} não", () => {
    expect(es("{M}: índice {N}, classe {C}", { M: "Ibirama", N: "1,34", C: "muito alto" })).toBe(
      "Ibirama: índice 1,34, clase muy alto",
    );
  });

  it("frase ausente do dicionário volta em português", () => {
    expect(es("Frase que não existe {N}", { N: "3" })).toBe("Frase que não existe 3");
  });

  it("nome de classe dentro de outra palavra não é classe", () => {
    expect(RE_CLASSE.exec("Planalto Alegre")).toBeNull();
    expect(RE_CLASSE.exec("Lalto")).toBeNull();
    expect(es("Planalto Alegre")).toBe("Planalto Alegre");
    expect(es("↑ alto")).toBe("↑ alto");
  });

  it("traduz os textos devolvidos por src/lib", () => {
    expect(es("extremamente alto")).toBe("extremadamente alto");
    expect(es("subindo")).toBe("subiendo");
    expect(es("estável")).toBe("estable");
    expect(es("sem chuva agora")).toBe("sin lluvia ahora");
    expect(es(marcaClasse(2, 7)!)).toBe("↑ extremadamente alto");
    expect(pt(marcaClasse(7, 1)!)).toBe("↓ extremamente baixo");
  });
});

describe("dicionário", () => {
  it('toda frase literal t("…") de componentes, layouts e páginas existe em es.json', () => {
    const fontes = import.meta.glob<string>(["../components/**/*.tsx", "../layouts/**/*.astro", "../pages/**/*.astro"], {
      query: "?raw",
      import: "default",
      eager: true,
    });
    const faltando = Object.values(fontes)
      .flatMap((codigo) => [...codigo.matchAll(/\bt\("([^"]+)"/g)].map((m) => m[1]))
      .filter((frase) => !(frase in ES));
    expect(faltando).toEqual([]);
  });

  it("nomes e rótulos curtos das telas existem em es.json", () => {
    const frases = TELAS.flatMap((t) => [t.nome, t.curto, `VIGIA · ${t.nome}`]);
    expect(frases.filter((f) => !(f in ES))).toEqual([]);
  });
});
