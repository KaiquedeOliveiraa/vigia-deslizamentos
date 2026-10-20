import { describe, expect, it } from "vitest";
import { tradutor } from "../i18n";
import exemplo from "../fixtures/indices.exemplo.json";
import geojsonBruto from "../data/municipios.geojson?raw";
import { FEICOES } from "./municipios";
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
    expect(rotuloAria(pt, "Ibirama", { indice: 1.3448, classe: 4 })).toBe("Ibirama: índice 1,34, classe moderado, em alerta");
    expect(rotuloAria(pt, "Witmarsum", { indice: 0.9999, classe: 3 })).toBe("Witmarsum: índice 1,00, classe baixo");
    expect(rotuloAria(pt, "Ibirama", { indice: 1, classe: 4 })).toBe("Ibirama: índice 1,00, classe moderado, em alerta");
  });

  it("usa a classe publicada, sem recalcular pelo índice", () => {
    expect(rotuloAria(pt, "Ibirama", { indice: 1.3448, classe: 5 })).toBe("Ibirama: índice 1,34, classe alto, em alerta");
  });

  it("sem dados (null) e sem valor (estações: só o nome)", () => {
    expect(rotuloAria(pt, "Dona Emma", null)).toBe("Dona Emma: sem dados");
    expect(rotuloAria(pt, "Dona Emma", undefined)).toBe("Dona Emma");
  });

  it("em espanhol", () => {
    expect(rotuloAria(es, "Ibirama", { indice: 2.7, classe: 6 })).toBe("Ibirama: índice 2,70, clase muy alto, en alerta");
    expect(rotuloAria(es, "Dona Emma", null)).toBe("Dona Emma: sin datos");
  });
});

describe("mensagemSelecao", () => {
  it("anuncia índice, classe e alerta", () => {
    expect(mensagemSelecao(pt, "Ibirama", { indice: 1.34, classe: 4 })).toBe("Ibirama selecionado. Índice 1,34, classe moderado, em alerta.");
    expect(mensagemSelecao(es, "Witmarsum", { indice: 0.3, classe: 1 })).toBe("Witmarsum seleccionado. Índice 0,30, clase extremadamente bajo, sin alerta.");
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

  it("os 27 municípios monitorados do GeoJSON enquadram o Alto Vale", () => {
    const fs = FEICOES;
    expect(fs.filter((f) => f.properties.monitorado)).toHaveLength(27);
    const [[s, o], [n, l]] = limites(fs);
    expect(s).toBeCloseTo(-27.66, 1);
    expect(o).toBeCloseTo(-50.35, 1);
    expect(l).toBeCloseTo(-49.19, 1);
    expect(n).toBeLessThan(-26.4);
  });

  it("o GeoJSON não passa de 150 KB e só tem Polygon", () => {
    expect(geojsonBruto.length).toBeLessThan(150_000);
    expect(FEICOES.every((f) => (f as { geometry: { type: string } }).geometry.type === "Polygon")).toBe(true);
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
    expect(rotuloDia("2026-10-16", "2026-10-16")).toBe("hoje");
    expect(rotuloDia("2026-10-17", "2026-10-16")).toBe("+1d");
    expect(rotuloDia("2026-10-19", "2026-10-16")).toBe("+3d");
    expect(rotuloDia("2026-10-15", "2026-10-16")).toBe("ontem");
    expect(rotuloDia("2026-10-14", "2026-10-16")).toBe("-2d");
    expect(rotuloDia("2026-11-01", "2026-10-31")).toBe("+1d"); // virada de mês
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
    expect(v["4206900"]?.indice).toBeCloseTo(1.4687);
    expect(v["4205100"]).toBeNull();
    const dia = indices.municipios.find((m) => m.ibge === "4206900")?.dias.find((x) => x.d === 0);
    expect(valoresDoDia(indices, 0)["4206900"]).toEqual({ indice: dia?.indice, classe: dia?.classe });
  });
});

describe("municipiosMonitorados", () => {
  it("só os monitorados, em ordem alfabética", () => {
    const fs = FEICOES;
    const lista = municipiosMonitorados(fs);
    expect(lista).toHaveLength(27);
    expect(lista[0]).toEqual({ ibge: "4200200", nome: "Agrolândia" });
    expect(lista.map((m) => m.nome)).toEqual([...lista.map((m) => m.nome)].sort((a, b) => a.localeCompare(b, "pt-BR")));
  });
});
