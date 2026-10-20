import { tecladoInicial } from "./teclados";
import type { BotJson, Env } from "./tipos";

export type Teclado = "municipios" | "remover" | "nenhum" | { linhas: string[][] };

/** Envia uma mensagem HTML. Nunca levanta: falhas vão ao log só com status ou tipo do erro. */
export async function enviarMensagem(
  env: Env,
  chatId: number,
  texto: string,
  teclado: Teclado,
  bot?: BotJson,
): Promise<void> {
  const corpo: Record<string, unknown> = { chat_id: chatId, text: texto, parse_mode: "HTML" };
  const linhas = typeof teclado === "object" ? teclado.linhas : teclado === "municipios" && bot ? tecladoInicial(bot) : null;
  if (linhas) {
    corpo.reply_markup = {
      keyboard: linhas.map((l) => l.map((text) => ({ text }))),
      resize_keyboard: true,
      one_time_keyboard: true,
    };
  } else if (teclado === "remover") {
    corpo.reply_markup = { remove_keyboard: true };
  }
  try {
    // A URL contém o token: nunca vai para o log.
    const resposta = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
      signal: AbortSignal.timeout(10000),
    });
    if (!resposta.ok) console.error(`sendMessage falhou: status ${resposta.status}`);
  } catch (erro) {
    console.error(`sendMessage falhou: ${erro instanceof Error ? erro.name : "erro"}`);
  }
}

/** `/status@NomeDoBot arg` vira `{comando: "status", args: ["arg"]}`; texto sem `/` vira `null`. */
export function interpretarComando(texto: string): { comando: string; args: string[] } | null {
  const partes = texto.trim().split(/\s+/);
  const primeira = partes[0] ?? "";
  if (!primeira.startsWith("/")) return null;
  const comando = primeira.slice(1).split("@")[0]!.toLowerCase();
  return { comando, args: partes.slice(1) };
}

export function normalizarNome(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

export function escaparHtml(texto: string): string {
  return texto
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Monta o `/status` na ordem de `bot.municipios`; ignora `ibge` fora dela. */
export function textoDoStatus(bot: BotJson, ibges: string[]): string {
  const inscritos = new Set(ibges);
  const blocos = bot.municipios
    .filter((m) => inscritos.has(m.ibge) && bot.status.blocos[m.ibge] !== undefined)
    .map((m) => bot.status.blocos[m.ibge]!);
  if (blocos.length === 0) return bot.status.sem_inscricao;
  return bot.status.cabecalho + blocos.join(bot.status.separador) + bot.status.rodape;
}

export const LIMITE_MENSAGEM_TELEGRAM = 4096;

/** `/status` em mensagens de até `limite` (comprimento JS do HTML bruto: superestima, é seguro). */
export function partesDoStatus(bot: BotJson, ibges: string[], limite = LIMITE_MENSAGEM_TELEGRAM): string[] {
  const inscritos = new Set(ibges);
  const blocos = bot.municipios
    .filter((m) => inscritos.has(m.ibge) && bot.status.blocos[m.ibge] !== undefined)
    .map((m) => bot.status.blocos[m.ibge]!);
  if (blocos.length === 0) return [bot.status.sem_inscricao];
  const { cabecalho, separador, rodape } = bot.status;
  const partes: string[] = [];
  let atual = cabecalho;
  let vazia = true;
  for (const bloco of blocos) {
    if (cabecalho.length + bloco.length + rodape.length > limite) throw new Error(`bloco sozinho passa do limite de ${limite}`);
    const junto = vazia ? atual + bloco : atual + separador + bloco;
    if (!vazia && junto.length + rodape.length > limite) {
      partes.push(atual);
      atual = bloco;
    } else {
      atual = junto;
    }
    vazia = false;
  }
  partes.push(atual + rodape);
  return partes;
}
