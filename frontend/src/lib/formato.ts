// Números com vírgula decimal (RN05) e datas no horário de Brasília.

export const formatarNumero = (x: number, casas: number): string => x.toFixed(casas).replace(".", ",");

export const formatarIndice = (x: number): string => formatarNumero(x, 2);

export const formatarMm = (x: number): string => formatarNumero(x, 1);

/** Razão chuva/limiar: "0,60×". */
export const formatarRazao = (x: number): string => `${formatarNumero(x, 2)}×`;

export function formatarCoord(lat: number, lon: number): string {
  const grau = (v: number, pos: string, neg: string) => `${formatarNumero(Math.abs(v), 4)}° ${v < 0 ? neg : pos}`;
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
