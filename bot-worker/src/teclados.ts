import type { BotJson, Grupo } from "./tipos";

/** Primeiro teclado: com grupos, as regiões (e o sugerido na frente); sem grupos, um botão por município. */
export function tecladoInicial(bot: BotJson, sugerido?: string): string[][] {
  const todos = [bot.textos.opcao_todos];
  if (!bot.grupos?.length) return [...bot.municipios.map((m) => [m.nome]), todos];
  const nome = sugerido ? bot.municipios.find((m) => m.ibge === sugerido)?.nome : undefined;
  return [...(nome ? [[nome]] : []), ...bot.grupos.map((g) => [g.nome]), todos];
}

/** Municípios do grupo em duas colunas, "Todos da Região…" e "Voltar". */
export function tecladoDoGrupo(bot: BotJson, grupo: Grupo): string[][] {
  const nomes = grupo.municipios.flatMap((i) => bot.municipios.find((m) => m.ibge === i)?.nome ?? []);
  const linhas: string[][] = [];
  for (let i = 0; i < nomes.length; i += 2) linhas.push(nomes.slice(i, i + 2));
  return [...linhas, [grupo.opcao_todos], [bot.textos.opcao_voltar ?? "Voltar"]];
}
