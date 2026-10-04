// Estações automáticas do INMET: regionais, associadas ao município de referência só por proximidade.
import type { T } from "../i18n";
import type { Estacao } from "./tipos";

/** Cópia da lista, da estação mais próxima do seu município de referência para a mais distante. */
export const ordenarPorDistancia = (lista: readonly Estacao[]): Estacao[] =>
  [...lista].sort((a, b) => a.distancia_km - b.distancia_km);

/** "a 76 km de Ibirama": a estação nunca é dita "em" um município (contratos-de-dados, regra de leitura). */
export const textoDistancia = (t: T, distancia_km: number, municipio: string): string =>
  t("a {N} km de {M}", { N: String(Math.round(distancia_km)), M: municipio });

/** "ITAJAI, a 76 km de Ibirama". */
export const rotuloEstacao = (t: T, estacao: Estacao, municipio: string): string =>
  `${estacao.nome}, ${textoDistancia(t, estacao.distancia_km, municipio)}`;
