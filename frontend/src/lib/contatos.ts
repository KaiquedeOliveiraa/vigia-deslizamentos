// Cartões de contato da Defesa Civil municipal (só verificados, RN09).
import type { T } from "../i18n";
import type { Contato } from "./tipos";

const MAPS = "https://www.google.com/maps/search/?api=1&query=";

/** "Como chegar": busca do endereço no Google Maps; sem endereço, a Defesa Civil do município. */
export const urlComoChegar = (c: Contato): string =>
  MAPS + encodeURIComponent(c.endereco ? c.endereco.replace(" — ", ", ") : `Defesa Civil ${c.nome} SC`);

/** tel: só com dígitos; números com DDD (10 ou 11 dígitos) ganham o +55. */
export function hrefTelefone(telefone: string): string {
  const digitos = telefone.replace(/\D/g, "");
  return `tel:${digitos.length >= 10 ? `+55${digitos}` : digitos}`;
}

export const hrefSite = (site: string): string => (/^https?:\/\//.test(site) ? site : `https://${site}`);

export interface Filtro {
  /** ibge dos cartões esmaecidos. */
  esmaecidos: string[];
  /** Mensagem quando o município escolhido não tem contato verificado. */
  aviso: string | null;
}

/** Filtro "Seu município" (`ibge` vazio = Todos). */
export function filtrarContatos(t: T, contatos: readonly Contato[], ibge: string, nome: string): Filtro {
  if (!ibge) return { esmaecidos: [], aviso: null };
  const esmaecidos = contatos.filter((c) => c.ibge !== ibge).map((c) => c.ibge);
  const aviso =
    esmaecidos.length === contatos.length
      ? t("Ainda não há contato verificado da Defesa Civil de {M}. Em perigo, ligue {N}.", { M: nome, N: "199" })
      : null;
  return { esmaecidos, aviso };
}
