// Escalas e séries dos gráficos (pluviômetro, evolução do índice) e indicadores da tela de dados.
import { CLASSES, classe, emAlerta, infoClasse, type NumeroClasse } from "./classes";
import type { Indices, Municipio } from "./tipos";

export interface Ponto {
  dia_alvo: string;
  indice: number;
}

const PLUV_MIN_MM = 150;
const EVOLUCAO_MIN = 2.0;
const PASSO_EVOLUCAO = 0.5;

/** Topo da escala do pluviômetro: sempre acima do limiar, para a linha dele aparecer. */
export const maxPluviometro = (limiar_mm: number): number => Math.max(PLUV_MIN_MM, limiar_mm * 1.2);

/** Topo do eixo Y da evolução: 2,00, ou o maior índice arredondado para cima em 0,5. */
export function maxEvolucao(indices: number[]): number {
  const maior = Math.max(EVOLUCAO_MIN, ...indices);
  return maior > EVOLUCAO_MIN ? Math.ceil(maior / PASSO_EVOLUCAO) * PASSO_EVOLUCAO : EVOLUCAO_MIN;
}

/** Valor em 0..max convertido para 0..alturaPx, limitado às pontas. */
export const escala = (valor: number, max: number, alturaPx: number): number =>
  (Math.min(Math.max(valor, 0), max) / max) * alturaPx;

/** `n` dias consecutivos terminando no D0 (AAAA-MM-DD), do mais antigo para o mais recente. */
export function diasEixo(dia_alvo_d0: string, n: number): string[] {
  const fim = new Date(`${dia_alvo_d0}T00:00:00Z`).getTime();
  return Array.from({ length: n }, (_, i) => new Date(fim - (n - 1 - i) * 86_400_000).toISOString().slice(0, 10));
}

/** Área de desenho em px: tamanho total e margens. */
export interface Area {
  largura: number;
  altura: number;
  esq: number;
  dir: number;
  topo: number;
  base: number;
}

export interface Coordenada {
  x: number;
  y: number;
  ponto: Ponto;
}

/** Posição de cada ponto: x pela data no `eixo` (fora do eixo fica de fora), y pelo índice de 0 a `max`. */
export function coordenadas(serie: Ponto[], eixo: string[], max: number, area: Area): Coordenada[] {
  const passo = eixo.length > 1 ? (area.largura - area.esq - area.dir) / (eixo.length - 1) : 0;
  const util = area.altura - area.topo - area.base;
  return serie.flatMap((ponto) => {
    const i = eixo.indexOf(ponto.dia_alvo);
    return i < 0 ? [] : [{ x: area.esq + i * passo, y: area.topo + util - escala(ponto.indice, max, util), ponto }];
  });
}

export interface Faixa {
  numero: NumeroClasse;
  de: number;
  ate: number;
}

/** Faixas de fundo do gráfico: as classes que começam abaixo de `max`, cortadas em `max`. */
export const faixasClasse = (max: number): Faixa[] =>
  CLASSES.filter((c) => c.min < max).map((c, i, lista) => ({
    numero: c.numero,
    de: c.min,
    ate: Math.min(lista[i + 1]?.min ?? max, max),
  }));

/** Linhas do eixo Y da evolução: as do protótipo e o início das classes acima de 1,80, abaixo do `max`. */
export const marcasEvolucao = (max: number): number[] =>
  [0, 0.4, 0.7, 1.0, 1.4, ...CLASSES.filter((c) => c.min >= 1.8).map((c) => c.min)].filter((v) => v < max);

/** "↑ moderado" / "↓ moderado" quando a classe muda de um dia para o seguinte. */
export function marcaClasse(anterior: number, atual: number): string | null {
  const de = classe(anterior);
  const para = classe(atual);
  if (de === para) return null;
  return `${para > de ? "↑" : "↓"} ${infoClasse(para).nome}`;
}

const d0 = (m: Municipio) => m.dias.find((d) => d.d === 0);

/** Últimos `dias` pontos: historico (mais antigo → mais recente) seguido do D0. */
export function serieMunicipio(m: Municipio, dias: number): Ponto[] {
  const atual = d0(m);
  const pontos: Ponto[] = m.historico.map(({ dia_alvo, indice }) => ({ dia_alvo, indice }));
  if (atual) pontos.push({ dia_alvo: atual.dia_alvo, indice: atual.indice });
  return pontos.slice(-dias);
}

/** Diferença de cada valor para o anterior (n − 1 itens). */
export const variacoes = (valores: number[]): number[] => valores.slice(1).map((v, i) => v - valores[i]);

export interface Indicadores {
  monitorados: number;
  emAlerta: number;
  chuvaEfetivaMax: { efr_mm: number; nome: string } | null;
  pico: { indice: number; nome: string; dia_alvo: string } | null;
}

/** Pico da semana: últimos 6 dias do historico mais o D0. */
const DIAS_SEMANA = 7;

export function indicadores(indices: Indices): Indicadores {
  let chuvaEfetivaMax: Indicadores["chuvaEfetivaMax"] = null;
  let pico: Indicadores["pico"] = null;
  let alerta = 0;
  for (const m of indices.municipios) {
    const atual = d0(m);
    if (atual && emAlerta(atual.indice)) alerta++;
    if (atual && (!chuvaEfetivaMax || atual.efr_mm > chuvaEfetivaMax.efr_mm))
      chuvaEfetivaMax = { efr_mm: atual.efr_mm, nome: m.nome };
    for (const p of serieMunicipio(m, DIAS_SEMANA))
      if (!pico || p.indice > pico.indice) pico = { indice: p.indice, nome: m.nome, dia_alvo: p.dia_alvo };
  }
  return {
    monitorados: indices.municipios.length + indices.municipios_sem_dados.length,
    emAlerta: alerta,
    chuvaEfetivaMax,
    pico,
  };
}

export const etiquetaChuva = (m: Municipio): string =>
  m.chuva_acum_mm["24h"] > 1 ? "choveu nas últimas 24h" : "sem chuva agora";
