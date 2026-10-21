import { describe, expect, it } from "vitest";
import { escreverSelecao, lerSelecao, lerSetores, mostrarSetoresIndividuais, porMunicipio, resumo, type Setor } from "./setores";

const feicao = (props: Record<string, unknown>, geometry: unknown = { type: "Polygon", coordinates: [[[-49.5, -27], [-49.4, -27], [-49.4, -26.9], [-49.5, -27]]] }) => ({
  type: "Feature", geometry,
  properties: { id: "S1", ibge: "4206900", centro: [-49.45, -26.97], local: "Rua A", tipo: "deslizamento", grau: "alto", descricao: null, recomendacao: null, pessoas: 10, moradias: 3, data: "2018-10-25", ...props },
});
const colecao = (features: unknown[]) => ({ type: "FeatureCollection", fonte: "SGB", gerado_em: "2026-10-21T00:00:00Z", features });

describe("lerSetores", () => {
  it("lê e converte para [lat, lon]", () => {
    const r = lerSetores(colecao([feicao({})]));
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.dados.setores[0].aneis[0][0][0]).toEqual([-27, -49.5]);
    expect(r.dados.fonte).toBe("SGB");
  });
  it("descarta feição inválida e recusa raiz errada", () => {
    const r = lerSetores(colecao([feicao({ tipo: "inundacao" }), feicao({ grau: "medio" }), feicao({}, { type: "Point", coordinates: [0, 0] }), feicao({ id: "S2" })]));
    expect(r.ok && r.dados.setores.map((s) => s.id)).toEqual(["S2"]);
    expect(lerSetores([]).ok).toBe(false);
  });
});

const s = (p: Partial<Setor>): Setor => ({ id: "S", ibge: "4206900", centro: [0, 0], local: null, tipo: "deslizamento", grau: "alto", descricao: null, recomendacao: null, pessoas: null, moradias: null, data: null, aneis: [], ...p });

describe("resumo e porMunicipio", () => {
  it("soma só pessoas conhecidas, conta graus, municípios e anos", () => {
    expect(resumo([s({ id: "a", pessoas: 10, grau: "muito_alto", data: "2015-01-01" }), s({ id: "b", pessoas: null, data: "2021-05-02" }), s({ id: "c", ibge: "4214003", pessoas: 0 })])).toEqual({
      setores: 3, muitoAlto: 1, alto: 2, pessoas: 10, municipios: 2, anoMin: 2015, anoMax: 2021,
    });
    expect(resumo([])).toEqual({ setores: 0, muitoAlto: 0, alto: 0, pessoas: 0, municipios: 0, anoMin: null, anoMax: null });
  });
  it("mais setores primeiro, desempate pelo nome", () => {
    const lista = porMunicipio([s({ id: "1", ibge: "4214003" }), s({ id: "2", ibge: "4206900" }), s({ id: "3", ibge: "4214003" }), s({ id: "4", ibge: "4205100" })]);
    expect(lista.map((m) => [m.ibge, m.setores.length])).toEqual([["4214003", 2], ["4205100", 1], ["4206900", 1]]);
  });
});

describe("seleção na URL", () => {
  const setores = [s({ id: "SC_1", ibge: "4214003" })];
  const ibges = new Set(["4214003", "4206900"]);
  it("setor implica o município; inválidos são ignorados", () => {
    expect(lerSelecao("?setor=SC_1", setores, ibges)).toEqual({ municipio: "4214003", setor: "SC_1" });
    expect(lerSelecao("?municipio=4206900&setor=XX", setores, ibges)).toEqual({ municipio: "4206900", setor: null });
    expect(lerSelecao("?municipio=9999999", setores, ibges)).toEqual({ municipio: null, setor: null });
  });
  it("escreve preservando outros parâmetros", () => {
    expect(escreverSelecao("?x=1", { municipio: "4214003", setor: "SC_1" })).toBe("?x=1&municipio=4214003&setor=SC_1");
    expect(escreverSelecao("?municipio=4214003&setor=SC_1", { municipio: null, setor: null })).toBe("");
  });
});

it("setores individuais com município escolhido ou de perto", () => {
  expect(mostrarSetoresIndividuais(false, true)).toBe(false);
  expect(mostrarSetoresIndividuais(true, true)).toBe(true);
  expect(mostrarSetoresIndividuais(false, false)).toBe(true);
});
