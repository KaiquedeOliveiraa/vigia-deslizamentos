import { describe, expect, it } from "vitest";
import { urlDados } from "./config";

describe("urlDados", () => {
  it("junta base e pasta de dados sem barras duplicadas", () => {
    expect(urlDados("indices.json", "/vigia-deslizamentos", "data/")).toBe("/vigia-deslizamentos/data/indices.json");
    expect(urlDados("indices.json", "/vigia-deslizamentos/", "/data")).toBe("/vigia-deslizamentos/data/indices.json");
  });

  it("usa data/ quando PUBLIC_DADOS_URL não está definida", () => {
    expect(urlDados("contatos.json", "/", undefined)).toBe("/data/contatos.json");
  });
});
