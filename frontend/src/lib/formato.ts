// Números com vírgula decimal (RN05) e datas no horário de Brasília.

export const formatarNumero = (x: number, casas: number): string => x.toFixed(casas).replace(".", ",");

export const formatarIndice = (x: number): string => formatarNumero(x, 2);

export const formatarMm = (x: number): string => formatarNumero(x, 1);

/** Fração de 0 a 1 em porcentagem inteira: "65%". */
export const formatarPercentual = (fracao: number): string => `${Math.round(fracao * 100)}%`;

/** Variação de índice com sinal: "+0,12", "−0,05" (sinal de menos tipográfico) ou "0,00". */
export function formatarVariacao(delta: number): string {
  const texto = formatarIndice(Math.abs(delta));
  if (texto === formatarIndice(0)) return texto;
  return `${delta > 0 ? "+" : "−"}${texto}`;
}

/** Razão chuva/limiar: "0,60×". */
export const formatarRazao = (x: number): string => `${formatarNumero(x, 2)}×`;

/** "27,0007° S, 49,5212° O"; `traduzir` troca as letras do hemisfério (leste: L em português, E em espanhol). */
export function formatarCoord(lat: number, lon: number, traduzir = (s: string) => s): string {
  const grau = (v: number, pos: string, neg: string) => `${formatarNumero(Math.abs(v), 4)}° ${traduzir(v < 0 ? neg : pos)}`;
  return `${grau(lat, "N", "S")}, ${grau(lon, "L", "O")}`;
}

const FUSO = "America/Sao_Paulo";
const dataBrasilia = new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, day: "2-digit", month: "2-digit", year: "numeric" });
const horaBrasilia = new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

/** Hora de `gerado_em` (data-hora) em Brasília: "06:12". */
export const formatarHora = (gerado_em: string): string => horaBrasilia.format(new Date(gerado_em));

/** `gerado_em` (data-hora) em Brasília: "29/09/2026 06:12". */
export const formatarDataHora = (gerado_em: string): string =>
  `${dataBrasilia.format(new Date(gerado_em))} ${formatarHora(gerado_em)}`;

/** `dia_alvo` é uma data (AAAA-MM-DD), não um instante: só reordena, sem fuso. */
export function formatarData(dia_alvo: string, formato: "longo" | "curto" | "dia" = "longo"): string {
  const [ano, mes, dia] = dia_alvo.split("-");
  if (formato === "dia") return `${dia}/${mes}`;
  return `${dia}/${mes}/${formato === "curto" ? ano.slice(2) : ano}`;
}
