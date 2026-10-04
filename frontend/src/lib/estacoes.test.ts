import { describe, expect, it } from "vitest";
import estacoes from "../fixtures/estacoes.exemplo.json";
import { tradutor } from "../i18n";
import { ordenarPorDistancia, rotuloEstacao, textoDistancia } from "./estacoes";

const pt = tradutor("pt");
const es = tradutor("es");

describe("estações regionais", () => {
  it("ordena da mais próxima para a mais distante, sem alterar a lista", () => {
    const ordenadas = ordenarPorDistancia(estacoes);
    expect(ordenadas.map((e) => e.codigo)).toEqual(["A861", "A863", "A864", "A868", "A860", "A870"]);
    expect(estacoes[0].codigo).toBe("A868");
  });

  it("distância ao município de referência, arredondada em km — nunca 'em' um município", () => {
    expect(textoDistancia(pt, 76.3, "Ibirama")).toBe("a 76 km de Ibirama");
    expect(textoDistancia(pt, 87.8, "Ibirama")).toBe("a 88 km de Ibirama");
    expect(textoDistancia(es, 30.1, "Witmarsum")).toBe("a 30 km de Witmarsum");
  });

  it("rótulo do pin: nome da estação e distância", () => {
    expect(rotuloEstacao(pt, estacoes[0], "Ibirama")).toBe("ITAJAI, a 76 km de Ibirama");
  });
});
