import type { BotJson } from "./tipos";

export const TEXTO_INDISPONIVEL =
  "O VIGIA está temporariamente indisponível. Tente de novo em alguns minutos.";

const SCHEMA_VERSION_ESPERADA = 1;

/** Baixa o `bot.json`. Devolve `null` em qualquer falha ou schema desconhecido. */
export async function carregarBotJson(url: string): Promise<BotJson | null> {
  try {
    const resposta = await fetch(url);
    if (resposta.status !== 200) return null;
    const dados = (await resposta.json()) as BotJson | null;
    if (dados === null || typeof dados !== "object") return null;
    if (dados.schema_version !== SCHEMA_VERSION_ESPERADA) return null;
    return dados;
  } catch {
    // Sem detalhes no log: só o fato da falha.
    console.error("bot.json indisponível ou inválido");
    return null;
  }
}
