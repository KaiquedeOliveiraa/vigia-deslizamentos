import { describe, expect, it } from "vitest";
import { segredoConfere, segredoDoBearer } from "../src/autenticacao";

describe("segredoConfere", () => {
  it("aceita o segredo certo", () => {
    expect(segredoConfere("abc", "abc")).toBe(true);
  });

  it("recusa segredo errado ou de outro tamanho", () => {
    expect(segredoConfere("abd", "abc")).toBe(false);
    expect(segredoConfere("abcd", "abc")).toBe(false);
  });

  it("recusa cabeçalho ausente", () => {
    expect(segredoConfere(null, "abc")).toBe(false);
  });

  it("recusa tudo quando o segredo esperado não foi configurado", () => {
    expect(segredoConfere("", "")).toBe(false);
    expect(segredoConfere("", undefined)).toBe(false);
    expect(segredoConfere("qualquer", undefined)).toBe(false);
  });
});

describe("segredoDoBearer", () => {
  it("extrai o segredo do cabeçalho Bearer", () => {
    expect(segredoDoBearer("Bearer s3gr3d0")).toBe("s3gr3d0");
  });

  it("devolve null para cabeçalho ausente ou malformado", () => {
    expect(segredoDoBearer(null)).toBeNull();
    expect(segredoDoBearer("Basic abc")).toBeNull();
    expect(segredoDoBearer("Bearer ")).toBeNull();
  });
});
