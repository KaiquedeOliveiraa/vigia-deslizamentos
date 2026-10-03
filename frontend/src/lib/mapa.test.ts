import { describe, expect, it } from "vitest";
import { tradutor } from "../i18n";
import geojson from "../data/municipios.geojson?raw";
import exemplo from "../fixtures/indices.exemplo.json";
import type { Indices } from "./tipos";
import { destacar, limites, municipiosMonitorados, valoresDoDia, mensagemSelecao, passoDia, posicoes, rotuloAria, rotuloDia, type FeicaoMunicipio } from "./mapa";

const pt = tradutor("pt");
const es = tradutor("es");

const feicao = (monitorado: boolean, coordinates: number[][][]): FeicaoMunicipio => ({
  type: "Feature",
  properties: { ibge: "1", nome: "X", monitorado },
  geometry: { type: "Polygon", coordinates },
});

describe("rotuloAria", () => {
  it("índice, classe e alerta a partir de 1,00", () => {
    expect(rotuloAria(pt, "Ibirama", 1.3448)).toBe("Ibirama: índice 1,34, classe moderado, em alerta");
    expect(rotuloAria(pt, "Witmarsum", 0.9999)).toBe("Witmarsum: índice 1,00, classe baixo");
    expect(rotuloAria(pt, "Ibirama", 1)).toBe("Ibirama: índice 1,00, classe moderado, em alerta");
  });

  it("sem dados (null) e sem valor (estações: só o nome)", () => {
    expect(rotuloAria(pt, "Dona Emma", null)).toBe("Dona Emma: sem dados");
    expect(rotuloAria(pt, "Dona Emma", undefined)).toBe("Dona Emma");
  });

  it("em espanhol", () => {
    expect(rotuloAria(es, "Ibirama", 2.7)).toBe("Ibirama: índice 2,70, clase muy alto, en alerta");
    expect(rotuloAria(es, "Dona Emma", null)).toBe("Dona Emma: sin datos");
  });
});

describe("mensagemSelecao", () => {
  it("anuncia índice, classe e alerta", () => {
    expect(mensagemSelecao(pt, "Ibirama", 1.34)).toBe("Ibirama selecionado. Índice 1,34, classe moderado, em alerta.");
    expect(mensagemSelecao(es, "Witmarsum", 0.3)).toBe("Witmarsum seleccionado. Índice 0,30, clase extremadamente bajo, sin alerta.");
    expect(mensagemSelecao(pt, "Dona Emma", null)).toBe("Dona Emma: sem dados");
  });
});

describe("posicoes e limites", () => {
  it("GeoJSON [lon, lat] vira [lat, lon] do Leaflet", () => {
    expect(posicoes(feicao(true, [[[-49.5, -27.1], [-49.4, -27.2]]]))).toEqual([[[-27.1, -49.5], [-27.2, -49.4]]]);
  });

  it("limites cobrem só os monitorados", () => {
    const fs = [feicao(true, [[[-49.5, -27.1], [-49.4, -27.3]]]), feicao(false, [[[-50, -26], [-48, -28]]])];
    expect(limites(fs)).toEqual([[-27.3, -49.5], [-27.1, -49.4]]);
  });

  it("limites incluem pontos extras (estações fora dos municípios)", () => {
    const fs = [feicao(true, [[[-49.5, -27.1], [-49.4, -27.3]]])];
    expect(limites(fs, [[-26.4, -50.4], [-27.0, -48.8]])).toEqual([[-27.3, -50.4], [-26.4, -48.8]]);
  });

  it("os 6 municípios monitorados do GeoJSON ficam no Alto Vale", () => {
    const fs = JSON.parse(geojson).features as FeicaoMunicipio[];
    expect(fs.filter((f) => f.properties.monitorado)).toHaveLength(6);
    const [[s, o], [n, l]] = limites(fs);
    expect(s).toBeGreaterThan(-27.4);
    expect(n).toBeLessThan(-26.5);
    expect(o).toBeGreaterThan(-50.2);
    expect(l).toBeLessThan(-49.2);
  });
});

describe("destacar", () => {
  it("acha o trecho sem acento e devolve o original", () => {
    expect(destacar("José Boiteux", "jose")).toEqual(["", "José", " Boiteux"]);
    expect(destacar("Presidente Getúlio", "GETU")).toEqual(["Presidente ", "Getú", "lio"]);
  });

  it("termo vazio ou ausente: sem destaque", () => {
    expect(destacar("Ibirama", "  ")).toBeNull();
    expect(destacar("Ibirama", "xyz")).toBeNull();
  });
});

describe("dias de previsão", () => {
  it("rótulo hoje, +1d…", () => {
    expect([0, 1, 2, 3].map(rotuloDia)).toEqual(["hoje", "+1d", "+2d", "+3d"]);
  });

  it("avança e volta em ciclo", () => {
    expect(passoDia(3, 1, 4)).toBe(0);
    expect(passoDia(0, -1, 4)).toBe(3);
    expect(passoDia(1, 1, 4)).toBe(2);
  });
});

describe("valoresDoDia", () => {
  it("índice de cada município no dia d; sem dados → null", () => {
    const indices = { ...(exemplo as Indices), municipios_sem_dados: ["4205100"] };
    const v = valoresDoDia(indices, 1);
    expect(v["4206900"]).toBeCloseTo(0.8812);
    expect(v["4205100"]).toBeNull();
    expect(valoresDoDia(indices, 0)["4206900"]).toBeCloseTo(1.3448);
  });
});

describe("municipiosMonitorados", () => {
  it("só os monitorados, em ordem alfabética", () => {
    const fs = JSON.parse(geojson).features as FeicaoMunicipio[];
    const lista = municipiosMonitorados(fs);
    expect(lista).toHaveLength(6);
    expect(lista[0]).toEqual({ ibge: "4205100", nome: "Dona Emma" });
    expect(lista.map((m) => m.nome)).toEqual([...lista.map((m) => m.nome)].sort((a, b) => a.localeCompare(b, "pt-BR")));
  });
});
