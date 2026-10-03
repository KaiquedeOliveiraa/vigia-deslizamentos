// RN07: simulação "E se chover…?" a partir das condições do D0. Nunca altera os dados carregados.
import type { T } from "../i18n";
import { classe, CLASSE_CRITICA, CLASSES, emAlerta, infoClasse, LIMIAR_ALERTA } from "./classes";
import { estadoMunicipio } from "./dados";
import { formatarIndice } from "./formato";
import { municipioInicial } from "./monitoramento";
import type { IndiceClasse, Indices, Municipio } from "./tipos";

export type Horas = 24 | 48 | 72;

export const CHUVA_MAX_MM = 400;

/** `classe` calculada a partir do índice simulado (não há classe publicada para ele). */
export interface Simulacao extends IndiceClasse {
  /** EfR do D0 decaído pela meia-vida até o fim do período, somado à chuva informada. */
  chuva_efetiva_mm: number;
}

export interface Cenario {
  ibge: string;
  chuva_mm: number;
  horas: Horas;
  regional: boolean;
}

export type NivelAviso = "crit" | "entra" | "continua" | "ok";

export const limitarChuva = (mm: number): number => Math.min(Math.max(mm, 0), CHUVA_MAX_MM);

export function simularMunicipio(m: Municipio, chuva_mm: number, horas: Horas): Simulacao | null {
  const d0 = m.dias.find((d) => d.d === 0);
  if (!d0) return null;
  const chuva_efetiva_mm = d0.efr_mm * 0.5 ** ((horas - 24) / m.mv_h) + limitarChuva(chuva_mm);
  const indice = chuva_efetiva_mm / m.limiar_mm;
  return { chuva_efetiva_mm, indice, classe: classe(indice) };
}

/** Índice e classe por IBGE: simulados para o escolhido (ou todos, se regional); os publicados do D0 para os demais. */
export function simular(municipios: Municipio[], c: Cenario): Record<string, IndiceClasse> {
  const valores: Record<string, IndiceClasse> = {};
  for (const m of municipios) {
    const simulado = c.regional || m.ibge === c.ibge ? simularMunicipio(m, c.chuva_mm, c.horas) : null;
    const valor = simulado ?? m.dias.find((d) => d.d === 0);
    if (valor) valores[m.ibge] = { indice: valor.indice, classe: valor.classe };
  }
  return valores;
}

export function nivelAviso(atual: number, simulado: number): NivelAviso {
  if (classe(simulado) >= CLASSE_CRITICA) return "crit";
  if (!emAlerta(simulado)) return "ok";
  return emAlerta(atual) ? "continua" : "entra";
}

function municipiosEmAlerta(valores: Record<string, IndiceClasse>): { ibges: string[]; total: number } {
  const ibges = Object.keys(valores).filter((ibge) => emAlerta(valores[ibge].indice));
  return { ibges, total: ibges.length };
}

/** `?municipio=<ibge>` se esse município tem dados; senão, o de maior índice no D0. */
export function municipioDaBusca(indices: Indices, busca: string): string | undefined {
  const ibge = new URLSearchParams(busca).get("municipio");
  return ibge && estadoMunicipio(indices, ibge).estado === "ok" ? ibge : municipioInicial(indices);
}

/** Fim da escala do resultado: 0 a 4. */
export const ESCALA_MAX = 4;

/** Posição do índice na escala, em %. */
export const posicaoEscala = (indice: number): number => (Math.min(Math.max(indice, 0), ESCALA_MAX) / ESCALA_MAX) * 100;

/** Largura (%) de cada classe na escala. */
export const faixasEscala = (): { numero: number; largura: number }[] =>
  CLASSES.map((c, i) => ({ numero: c.numero, largura: posicaoEscala(CLASSES[i + 1]?.min ?? ESCALA_MAX) - posicaoEscala(c.min) }));

export interface Aviso {
  tipo: "ok" | "warn" | "crit";
  titulo: string;
  texto: string;
}

export interface DadosAviso {
  nome: string;
  atual: number;
  simulado: number;
  chuva_mm: number;
  horas: Horas;
}

/** Aviso sobre o mapa conforme `nivelAviso`; texto sempre condicional (RN04). */
export function avisoSimulacao(t: T, { nome, atual, simulado, chuva_mm, horas }: DadosAviso): Aviso {
  const C = infoClasse(classe(simulado)).nome;
  const N = formatarIndice(simulado);
  const periodo = [String(chuva_mm), `${horas}h`];
  switch (nivelAviso(atual, simulado)) {
    case "crit":
      return {
        tipo: "crit",
        titulo: t("Risco {C} em {M}", { C, M: nome }),
        texto: t(
          "Se essa previsão se concretizar, o município poderá entrar em estado de alerta máximo. Fique atento aos avisos oficiais e, diante de sinais de deslizamento, ligue 199.",
        ),
      };
    case "entra":
      return {
        tipo: "warn",
        titulo: t("{M} poderá entrar em alerta", { M: nome }),
        texto: t("Se essa sua previsão se concretizar, o município poderá entrar em estado de alerta (classe {C}).", { C }),
      };
    case "continua":
      return {
        tipo: "warn",
        titulo: t("{M} continuaria em alerta", { M: nome }),
        texto: t(
          simulado > atual ? "Com {N} mm em {N} o índice subiria para {N} (classe {C})." : "Com {N} mm em {N} o índice ficaria em {N} (classe {C}).",
          { N: [...periodo, N], C },
        ),
      };
    case "ok":
      return {
        tipo: "ok",
        titulo: t("Abaixo do nível de alerta"),
        texto: t("Com {N} mm em {N}, {M} ficaria na classe {C} ({N}).", { N: [...periodo, N], M: nome, C }),
      };
  }
}

/** Segundo aviso da chuva regional: "N de M em alerta" e os que passariam de 1,00. */
export function avisoRegional(t: T, valores: Record<string, IndiceClasse>, nomes: Record<string, string>): Aviso {
  const { ibges, total } = municipiosEmAlerta(valores);
  const limiar = formatarIndice(LIMIAR_ALERTA);
  return {
    tipo: total ? "warn" : "ok",
    titulo: t("Chuva regional: {N} de {N} em alerta", { N: [String(total), String(Object.keys(valores).length)] }),
    texto: total
      ? t("Municípios que passariam de {N}: {M}.", { N: limiar, M: ibges.map((i) => nomes[i] ?? i).join(", ") })
      : t("Nenhum município passaria de {N}.", { N: limiar }),
  };
}
