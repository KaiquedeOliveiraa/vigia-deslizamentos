// Classes de risco GeoRisk: mesmas faixas [a, b) de backend/app/classificacao/classes.py.
// O risco nunca é indicado só por cor (RN03): cada classe tem nome, ícone e hachura.

export type NumeroClasse = 1 | 2 | 3 | 4 | 5 | 6 | 7;

export type IconeClasse =
  | "circulo-check"
  | "olho"
  | "triangulo-exclamacao"
  | "triangulo-exclamacao-dupla"
  | "octogono-exclamacao"
  | "octogono-x";

export interface Hachura {
  espacamento: number;
  cruzada: boolean;
}

export interface InfoClasse {
  numero: NumeroClasse;
  nome: string;
  faixa: string;
  /** Limite inferior incluído. */
  min: number;
  cor: string;
  corIcone: string;
  icone: IconeClasse;
  hachura: Hachura | null;
}

export const LIMIAR_ALERTA = 1.0;

/** A partir desta classe ("muito alto") a simulação fala em alerta máximo. */
export const CLASSE_CRITICA: NumeroClasse = 6;

const info = (
  numero: NumeroClasse,
  nome: string,
  faixa: string,
  min: number,
  icone: IconeClasse,
  hachura: Hachura | null = null,
): InfoClasse => ({ numero, nome, faixa, min, cor: `var(--c${numero})`, corIcone: `var(--ci${numero})`, icone, hachura });

export const CLASSES: readonly InfoClasse[] = [
  info(1, "extremamente baixo", "< 0,40", 0, "circulo-check"),
  info(2, "muito baixo", "0,40 – 0,70", 0.4, "circulo-check"),
  info(3, "baixo", "0,70 – 1,00", 0.7, "olho"),
  info(4, "moderado", "1,00 – 1,80", 1.0, "triangulo-exclamacao", { espacamento: 16, cruzada: false }),
  info(5, "alto", "1,80 – 2,60", 1.8, "triangulo-exclamacao-dupla", { espacamento: 11, cruzada: false }),
  info(6, "muito alto", "2,60 – 3,40", 2.6, "octogono-exclamacao", { espacamento: 8, cruzada: true }),
  info(7, "extremamente alto", "≥ 3,40", 3.4, "octogono-x", { espacamento: 6, cruzada: true }),
];

/** Município vizinho, fora do monitoramento. */
export const NAO_MONITORADO = { nome: "não monitorado", cor: "var(--risk-nm)" };

/** Município monitorado listado em `municipios_sem_dados`. */
export const SEM_DADOS = { nome: "sem dados", cor: "var(--risk-nm)" };

export const classe = (indice: number): NumeroClasse =>
  CLASSES.findLast((c) => indice >= c.min)?.numero ?? 1;

export const infoClasse = (numero: NumeroClasse): InfoClasse => CLASSES[numero - 1];

/** RN02: alerta a partir do moderado (índice ≥ 1,00). */
export const emAlerta = (indice: number): boolean => indice >= LIMIAR_ALERTA;
