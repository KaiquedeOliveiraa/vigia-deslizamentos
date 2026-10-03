import { describe, expect, it } from "vitest";
import { formatarCoord, formatarData, formatarDataHora, formatarHora, formatarIndice, formatarMm, formatarPercentual, formatarRazao, formatarVariacao } from "./formato";

describe("números", () => {
  it("usa vírgula decimal e as casas de cada grandeza (RN05)", () => {
    expect(formatarIndice(1.3449)).toBe("1,34");
    expect(formatarMm(72)).toBe("72,0");
    expect(formatarRazao(0.6)).toBe("0,60×");
  });

  it("coordenadas com hemisfério e quatro casas", () => {
    expect(formatarCoord(-27.0007, -49.5212)).toBe("27,0007° S, 49,5212° O");
    expect(formatarCoord(1.5, 2.25)).toBe("1,5000° N, 2,2500° L");
  });
});

describe("datas", () => {
  it("gerado_em é exibido no horário de Brasília", () => {
    expect(formatarHora("2026-09-29T09:12:00Z")).toBe("06:12");
    expect(formatarDataHora("2026-09-29T09:12:00Z")).toBe("29/09/2026 06:12");
    expect(formatarDataHora("2026-09-30T01:30:00Z")).toBe("29/09/2026 22:30");
    expect(formatarHora("2026-09-29T06:12:00-03:00")).toBe("06:12");
  });

  it("dia_alvo é uma data, sem conversão de fuso", () => {
    expect(formatarData("2026-09-29")).toBe("29/09/2026");
    expect(formatarData("2026-09-29", "curto")).toBe("29/09/26");
    expect(formatarData("2026-09-29", "dia")).toBe("29/09");
  });
});

describe("percentual e variação", () => {
  it("fração de 0 a 1 em porcentagem inteira", () => {
    expect(formatarPercentual(0.65)).toBe("65%");
    expect(formatarPercentual(0.054)).toBe("5%");
  });

  it("variação com sinal + ou − (sinal de menos tipográfico) e duas casas", () => {
    expect(formatarVariacao(0.123)).toBe("+0,12");
    expect(formatarVariacao(-0.05)).toBe("−0,05");
    expect(formatarVariacao(0.004)).toBe("0,00");
    expect(formatarVariacao(-0.004)).toBe("0,00");
  });
});
