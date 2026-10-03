// Interações da Cartilha: mochila, abas e navegação por âncoras.
import type { T } from "../i18n";
import { passoDia } from "./mapa";

export interface ProgressoMochila {
  pct: number;
  contagem: string;
  mensagem: string;
  pronta: boolean;
}

/** "3 de 8" e a mensagem do cartão da mochila; `pct` é a largura da barra. */
export function progressoMochila(t: T, marcados: number, total: number): ProgressoMochila {
  const pronta = marcados === total;
  return {
    pct: (marcados / total) * 100,
    contagem: t("{N} de {N}", { N: [String(marcados), String(total)] }),
    mensagem: pronta ? t("Mochila pronta!") : t("itens na mochila"),
    pronta,
  };
}

/** Aba seguinte para a tecla (setas em círculo, Home e End); `null` se a tecla não navega. */
export function abaPorTecla(atual: number, tecla: string, total: number): number | null {
  if (tecla === "ArrowRight") return passoDia(atual, 1, total);
  if (tecla === "ArrowLeft") return passoDia(atual, -1, total);
  if (tecla === "Home") return 0;
  if (tecla === "End") return total - 1;
  return null;
}

/**
 * Seção a destacar: a última cujo topo (relativo ao topo da área rolável) já subiu até `limite`.
 * No fim da rolagem vale a última, que pode nunca chegar ao topo.
 */
export function secaoAtiva(topos: readonly number[], limite: number, noFim: boolean): number {
  if (noFim) return topos.length - 1;
  return Math.max(0, topos.findLastIndex((topo) => topo <= limite));
}
