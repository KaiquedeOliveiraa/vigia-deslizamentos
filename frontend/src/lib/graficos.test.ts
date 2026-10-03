import { describe, expect, it } from "vitest";
import type { Indices, Municipio } from "./tipos";
import {
  coordenadas,
  diasEixo,
  escala,
  etiquetaChuva,
  faixasClasse,
  indicadores,
  marcaClasse,
  marcasEvolucao,
  maxEvolucao,
  maxPluviometro,
  serieMunicipio,
  variacoes,
} from "./graficos";

const municipio = (
  ibge: string,
  nome: string,
  d0: { indice: number; efr_mm: number },
  historico: [string, number][] = [],
  chuva24h = 0,
): Municipio => ({
  ibge,
  nome,
  limiar_mm: 120,
  fonte_limiar: "GeoRisk",
  mv_h: 24,
  dias: [
    { dia_alvo: "2026-10-03", d: 1, indice: 9, classe: 7, efr_mm: 999, rtotal_mm: 0, n_membros: 31, prob: { pontuais: 0, esparsos: 0, generalizados: 0 } },
    { dia_alvo: "2026-10-02", d: 0, indice: d0.indice, classe: 1, efr_mm: d0.efr_mm, rtotal_mm: 0, n_membros: 31, prob: { pontuais: 0, esparsos: 0, generalizados: 0 } },
  ],
  historico: historico.map(([dia_alvo, indice]) => ({ dia_alvo, indice, classe: 1 })),
  chuva_acum_mm: { "24h": chuva24h, "48h": 0, "72h": 0, "96h": 0 },
});

const historico15: [string, number][] = Array.from({ length: 15 }, (_, i) => [
  `2026-09-${String(17 + i).padStart(2, "0")}`,
  i / 10,
]);

describe("maxPluviometro", () => {
  it("maior valor entre 150 mm e limiar × 1,2", () => {
    expect(maxPluviometro(120)).toBeCloseTo(150);
    expect(maxPluviometro(250)).toBeCloseTo(300);
  });
});

describe("maxEvolucao", () => {
  it("até 2,00 quando nenhum valor passa de 2,00", () => {
    expect(maxEvolucao([0.4, 1.2, 2.0])).toBeCloseTo(2.0);
    expect(maxEvolucao([])).toBeCloseTo(2.0);
  });

  it("acima de 2,00 arredonda o maior para cima em 0,5", () => {
    expect(maxEvolucao([1.0, 2.3])).toBeCloseTo(2.5);
    expect(maxEvolucao([3.0, 0.5])).toBeCloseTo(3.0);
  });
});

describe("marcasEvolucao", () => {
  it("as do protótipo, mais o início das classes acima de 1,80, abaixo do max", () => {
    expect(marcasEvolucao(2)).toEqual([0, 0.4, 0.7, 1.0, 1.4, 1.8]);
    expect(marcasEvolucao(3)).toEqual([0, 0.4, 0.7, 1.0, 1.4, 1.8, 2.6]);
  });
});

describe("escala", () => {
  it("linear de 0 a max, limitada à altura", () => {
    expect(escala(75, 150, 200)).toBeCloseTo(100);
    expect(escala(0, 150, 200)).toBeCloseTo(0);
    expect(escala(400, 150, 200)).toBeCloseTo(200);
    expect(escala(-5, 150, 200)).toBeCloseTo(0);
  });
});

describe("marcaClasse", () => {
  it("marca subida e descida de classe entre dias consecutivos", () => {
    expect(marcaClasse(0.9, 1.1)).toBe("↑ moderado");
    expect(marcaClasse(1.9, 1.5)).toBe("↓ moderado");
  });

  it("sem mudança de classe não há marca", () => {
    expect(marcaClasse(1.0, 1.79)).toBeNull();
  });
});

describe("serieMunicipio", () => {
  const m = municipio("4200001", "A", { indice: 2.0, efr_mm: 50 }, historico15);

  it("últimos N dias do historico seguidos do D0", () => {
    const serie = serieMunicipio(m, 7);
    expect(serie).toHaveLength(7);
    expect(serie[0].dia_alvo).toBe("2026-09-26");
    expect(serie[6]).toEqual({ dia_alvo: "2026-10-02", indice: 2.0 });
  });

  it("5 e 15 dias", () => {
    expect(serieMunicipio(m, 5)).toHaveLength(5);
    expect(serieMunicipio(m, 15)[0].dia_alvo).toBe("2026-09-18");
  });

  it("historico curto devolve o que houver", () => {
    expect(serieMunicipio(municipio("1", "B", { indice: 1, efr_mm: 0 }, [["2026-10-01", 0.5]]), 7)).toHaveLength(2);
  });
});

describe("variacoes", () => {
  it("diferença de cada dia para o anterior", () => {
    const v = variacoes([0.5, 0.8, 0.6]);
    expect(v).toHaveLength(2);
    expect(v[0]).toBeCloseTo(0.3);
    expect(v[1]).toBeCloseTo(-0.2);
  });
});

describe("indicadores", () => {
  const indices: Indices = {
    schema_version: 1,
    gerado_em: "2026-10-02T09:00:00Z",
    dia_alvo_d0: "2026-10-02",
    municipios_sem_dados: ["4200009"],
    municipios: [
      // O dia mais antigo (3,9) fica fora dos últimos 6 dias do historico.
      municipio("4200001", "Ibirama", { indice: 1.0, efr_mm: 72 }, [["2026-09-25", 3.9], ["2026-09-26", 0.5], ["2026-09-27", 0.5], ["2026-09-28", 0.5], ["2026-09-29", 0.5], ["2026-09-30", 1.58], ["2026-10-01", 1.2]]),
      municipio("4200002", "Dona Emma", { indice: 0.9999, efr_mm: 34.6 }, [["2026-10-01", 1.1]]),
      municipio("4200003", "Presidente Getúlio", { indice: 1.4, efr_mm: 60 }),
    ],
  };

  it("monitorados, em alerta, chuva efetiva máxima e pico da semana", () => {
    const r = indicadores(indices);
    expect(r.monitorados).toBe(4);
    expect(r.emAlerta).toBe(2);
    expect(r.chuvaEfetivaMax?.nome).toBe("Ibirama");
    expect(r.chuvaEfetivaMax?.efr_mm).toBeCloseTo(72);
    expect(r.pico?.nome).toBe("Ibirama");
    expect(r.pico?.dia_alvo).toBe("2026-09-30");
    expect(r.pico?.indice).toBeCloseTo(1.58);
  });

  it("sem municípios com dados não há máximos", () => {
    const r = indicadores({ ...indices, municipios: [] });
    expect(r).toEqual({ monitorados: 1, emAlerta: 0, chuvaEfetivaMax: null, pico: null });
  });
});

describe("etiquetaChuva", () => {
  it("acumulado de 24 h acima de 1 mm", () => {
    expect(etiquetaChuva(municipio("1", "A", { indice: 0, efr_mm: 0 }, [], 1.1))).toBe("choveu nas últimas 24h");
    expect(etiquetaChuva(municipio("1", "A", { indice: 0, efr_mm: 0 }, [], 1))).toBe("sem chuva agora");
  });
});

describe("diasEixo", () => {
  it("N dias consecutivos terminando no D0, atravessando o mês", () => {
    expect(diasEixo("2026-10-02", 3)).toEqual(["2026-09-30", "2026-10-01", "2026-10-02"]);
    expect(diasEixo("2026-10-02", 7)).toHaveLength(7);
  });
});

describe("coordenadas", () => {
  const area = { largura: 120, altura: 60, esq: 10, dir: 10, topo: 5, base: 5 };
  const eixo = ["2026-09-30", "2026-10-01", "2026-10-02"];

  it("x pela posição da data no eixo e y pelo índice (0 embaixo, max em cima)", () => {
    const c = coordenadas([{ dia_alvo: "2026-09-30", indice: 0 }, { dia_alvo: "2026-10-02", indice: 2 }], eixo, 2, area);
    expect(c.map((p) => [p.x, p.y])).toEqual([[10, 55], [110, 5]]);
    expect(c[1].ponto.indice).toBe(2);
  });

  it("dia fora do eixo fica de fora; índice acima do max fica no topo", () => {
    const c = coordenadas([{ dia_alvo: "2026-09-01", indice: 1 }, { dia_alvo: "2026-10-01", indice: 9 }], eixo, 2, area);
    expect(c).toHaveLength(1);
    expect(c[0].x).toBeCloseTo(60);
    expect(c[0].y).toBeCloseTo(5);
  });

  it("eixo de um dia só fica à esquerda", () => {
    expect(coordenadas([{ dia_alvo: "2026-10-02", indice: 1 }], ["2026-10-02"], 2, area)[0].x).toBe(10);
  });
});

describe("faixasClasse", () => {
  it("classes que começam abaixo do max, cortadas no max", () => {
    expect(faixasClasse(2)).toEqual([
      { numero: 1, de: 0, ate: 0.4 },
      { numero: 2, de: 0.4, ate: 0.7 },
      { numero: 3, de: 0.7, ate: 1.0 },
      { numero: 4, de: 1.0, ate: 1.8 },
      { numero: 5, de: 1.8, ate: 2 },
    ]);
  });

  it("acima de 3,40 a última faixa vai até o max", () => {
    expect(faixasClasse(4).at(-1)).toEqual({ numero: 7, de: 3.4, ate: 4 });
  });
});
