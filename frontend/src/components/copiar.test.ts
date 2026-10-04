import { afterEach, describe, expect, it, vi } from "vitest";
import { copiarTexto } from "./copiar";

const documentoFalso = (copiou: boolean) => ({
  createElement: () => ({ select: () => {}, remove: () => {} }),
  body: { append: () => {} },
  execCommand: () => copiou,
});

afterEach(() => vi.unstubAllGlobals());

describe("copiarTexto", () => {
  it("área de transferência disponível → verdadeiro", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    expect(await copiarTexto("abc")).toBe(true);
    expect(writeText).toHaveBeenCalledWith("abc");
  });

  it("sem área de transferência, copia pela seleção; se ela falhar → falso", async () => {
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("document", documentoFalso(true));
    expect(await copiarTexto("abc")).toBe(true);
    vi.stubGlobal("document", documentoFalso(false));
    expect(await copiarTexto("abc")).toBe(false);
  });
});
