import { TEXTO_INDISPONIVEL, carregarBotJson } from "./bot-json";
import { ibgesDoChat, inscrever, removerChat } from "./inscritos";
import {
  enviarMensagem,
  escaparHtml,
  interpretarComando,
  normalizarNome,
  textoDoStatus,
} from "./telegram";
import type { BotJson, Env } from "./tipos";

type Mensagem = { chat?: { id?: unknown }; text?: unknown };

const esperar = (segundos: number) => new Promise<void>((ok) => setTimeout(ok, segundos * 1000));

async function enviarSimulacao(env: Env, chatId: number, textos: string[], pausaS: number) {
  for (const [i, texto] of textos.entries()) {
    if (i > 0 && pausaS > 0) await esperar(pausaS);
    await enviarMensagem(env, chatId, texto, "nenhum");
  }
}

/** `/simular`: só chamado com `bot.simulacao` preenchida. */
async function simular(
  bot: BotJson,
  sim: NonNullable<BotJson["simulacao"]>,
  args: string[],
  env: Env,
  chatId: number,
  ctx: ExecutionContext,
): Promise<void> {
  const alvo =
    args.length === 0
      ? bot.municipios[0]
      : bot.municipios.find((m) => normalizarNome(m.nome) === normalizarNome(args.join(" ")));
  if (!alvo) {
    const texto = sim.municipio_invalido.replace("{entrada}", () => escaparHtml(args.join(" ")));
    await enviarMensagem(env, chatId, texto, "nenhum");
    return;
  }
  const textos = [...(sim.mensagens[alvo.ibge] ?? []), sim.fim];
  ctx.waitUntil(enviarSimulacao(env, chatId, textos, sim.pausa_s));
}

async function tratarMensagem(
  texto: string,
  chatId: number,
  env: Env,
  ctx: ExecutionContext,
): Promise<void> {
  const bot = await carregarBotJson(env.BOT_JSON_URL);
  if (bot === null) {
    await enviarMensagem(env, chatId, TEXTO_INDISPONIVEL, "nenhum");
    return;
  }
  const t = bot.textos;
  const comando = interpretarComando(texto);

  if (comando === null) {
    const nome = texto.trim();
    if (nome === t.opcao_todos) {
      await inscrever(env.DB, chatId, bot.municipios.map((m) => m.ibge), new Date());
      await enviarMensagem(env, chatId, t.inscricao_confirmada_todos, "remover");
      return;
    }
    const municipio = bot.municipios.find((m) => m.nome === nome);
    if (municipio) {
      await inscrever(env.DB, chatId, [municipio.ibge], new Date());
      await enviarMensagem(env, chatId, t.inscricao_confirmada[municipio.ibge] ?? "", "remover");
      return;
    }
  } else if (comando.comando === "start") {
    const codigo = comando.args[0] ?? "";
    const sugerido = Object.hasOwn(t.boas_vindas_sugerido, codigo)
      ? t.boas_vindas_sugerido[codigo]
      : undefined;
    await enviarMensagem(env, chatId, sugerido ?? t.boas_vindas, "municipios", bot);
    return;
  } else if (comando.comando === "status") {
    const ibges = await ibgesDoChat(env.DB, chatId);
    await enviarMensagem(env, chatId, textoDoStatus(bot, ibges), "nenhum");
    return;
  } else if (comando.comando === "parar") {
    await removerChat(env.DB, chatId);
    await enviarMensagem(env, chatId, t.inscricoes_apagadas, "remover");
    return;
  } else if (comando.comando === "simular" && bot.simulacao !== null) {
    await simular(bot, bot.simulacao, comando.args, env, chatId, ctx);
    return;
  }
  await enviarMensagem(env, chatId, t.opcao_desconhecida, "municipios", bot);
}

/** Trata uma atualização do Telegram. Ignora o que não for mensagem de texto. */
export async function tratarAtualizacao(
  update: unknown,
  env: Env,
  ctx: ExecutionContext,
): Promise<void> {
  const mensagem = (update as { message?: Mensagem } | null)?.message;
  const texto = mensagem?.text;
  const chatId = mensagem?.chat?.id;
  if (typeof texto !== "string" || typeof chatId !== "number") return;
  await tratarMensagem(texto, chatId, env, ctx);
}
