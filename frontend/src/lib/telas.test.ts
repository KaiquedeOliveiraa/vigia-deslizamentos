import { describe, expect, it } from "vitest";
import { TELAS, rota, rotaComEstado } from "./telas";

describe("rota", () => {
  it("monta o caminho com a base do site e o prefixo /es", () => {
    expect(rota("", "pt", "/vigia-deslizamentos")).toBe("/vigia-deslizamentos/");
    expect(rota("simulacao", "pt", "/vigia-deslizamentos/")).toBe("/vigia-deslizamentos/simulacao/");
    expect(rota("", "es", "/vigia-deslizamentos/")).toBe("/vigia-deslizamentos/es/");
    expect(rota("contatos", "es", "/")).toBe("/es/contatos/");
  });
});

describe("rotaComEstado", () => {
  it("troca de idioma mantém a busca (?municipio=) e a âncora", () => {
    expect(rotaComEstado("simulacao", "es", { search: "?municipio=4207007", hash: "#res" }, "/vigia-deslizamentos/")).toBe(
      "/vigia-deslizamentos/es/simulacao/?municipio=4207007#res",
    );
    expect(rotaComEstado("", "pt", { search: "", hash: "" }, "/")).toBe("/");
  });
});

describe("TELAS", () => {
  it("7 telas na ordem do menu, Contatos por último", () => {
    expect(TELAS.map((t) => t.rota)).toEqual([
      "",
      "simulacao",
      "dados",
      "monitoramento-sc",
      "estacoes",
      "cartilha",
      "contatos",
    ]);
  });
});
