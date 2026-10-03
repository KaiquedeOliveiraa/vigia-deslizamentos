/** URL de um arquivo publicado (indices.json, contatos.json…): base do Astro + PUBLIC_DADOS_URL (padrão `data/`). */
export function urlDados(
  arquivo: string,
  base: string = import.meta.env.BASE_URL,
  dados: string | undefined = import.meta.env.PUBLIC_DADOS_URL,
): string {
  const partes = [base, dados ?? "data/", arquivo].map((p) => p.replace(/^\/+|\/+$/g, "")).filter(Boolean);
  return "/" + partes.join("/");
}

/** Nome do bot do Telegram (PUBLIC_TELEGRAM_BOT); provisório: VigiaDeslizamentosBot. */
export const botTelegram = (nome: string | undefined = import.meta.env.PUBLIC_TELEGRAM_BOT): string =>
  nome || "VigiaDeslizamentosBot";

/** Link do bot; com `ibge`, o bot já sugere aquele município. */
export const linkTelegram = (bot: string, ibge?: string): string =>
  `https://t.me/${bot}${ibge ? `?start=${ibge}` : ""}`;

/** Iframe do mapa da Defesa Civil de SC: só com PUBLIC_SC_IFRAME=true, depois da autorização (RN10). */
export const iframeSC = (flag: string | undefined = import.meta.env.PUBLIC_SC_IFRAME): boolean => flag === "true";
