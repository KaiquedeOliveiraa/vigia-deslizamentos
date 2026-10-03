import { describe, expect, it } from "vitest";
import ES from "../i18n/es.json";
import { FASES, MOCHILA, NAO_FACA, SECOES, SINAIS } from "./cartilha";

describe("conteúdo da Cartilha", () => {
  it("6 sinais, 3 fases com 4 blocos, 8 itens da mochila e 6 'não faça'", () => {
    expect(SINAIS).toHaveLength(6);
    expect(FASES.map((f) => f.blocos.length)).toEqual([4, 4, 4]);
    expect(MOCHILA).toHaveLength(8);
    expect(NAO_FACA).toHaveLength(6);
  });

  it("toda frase tem tradução em es.json", () => {
    const frases = [
      ...SECOES.map((s) => s.rotulo),
      ...SINAIS.flatMap((s) => [s.titulo, s.detalhe]),
      ...FASES.flatMap((f) => [f.rotulo, ...f.blocos.map((b) => b.texto)]),
      ...MOCHILA.map((b) => b.texto),
      ...NAO_FACA.map((b) => b.texto),
    ];
    expect(frases.filter((f) => !(f in ES))).toEqual([]);
  });
});
