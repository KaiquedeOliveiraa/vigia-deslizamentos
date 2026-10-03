import type { Idioma } from "./preferencias";

export interface Tela {
  /** Caminho depois da base do site ("" = Monitoramento). */
  rota: string;
  nome: string;
  /** Rótulo da barra inferior no celular. */
  curto: string;
}

export const TELAS: readonly Tela[] = [
  { rota: "", nome: "Monitoramento", curto: "Mapa" },
  { rota: "simulacao", nome: "Simulação", curto: "Simular" },
  { rota: "dados", nome: "Dados da análise", curto: "Dados" },
  { rota: "monitoramento-sc", nome: "Monitoramento SC", curto: "SC" },
  { rota: "estacoes", nome: "Estações", curto: "Estações" },
  { rota: "cartilha", nome: "Cartilha", curto: "Cartilha" },
  { rota: "contatos", nome: "Contatos", curto: "Contatos" },
];

/** URL da tela no idioma: o espanhol fica em /es/. */
export function rota(tela: string, lang: Idioma, base: string = import.meta.env.BASE_URL): string {
  const partes = [base, lang === "es" ? "es" : "", tela].map((p) => p.replace(/^\/+|\/+$/g, "")).filter(Boolean);
  return `/${partes.map((p) => `${p}/`).join("")}`;
}
