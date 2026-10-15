export type Inscrito = { chat_id: number; ibge: string };

function formatarDataHora(momento: Date): string {
  return momento.toISOString().replace(/\.\d{3}Z$/, "Z");
}

export async function inscrever(
  db: D1Database,
  chatId: number,
  ibges: string[],
  agora: Date,
): Promise<void> {
  if (ibges.length === 0) return;
  const instante = formatarDataHora(agora);
  const comando = db.prepare(
    "INSERT OR IGNORE INTO inscritos (chat_id, ibge, inscrito_em) VALUES (?, ?, ?)",
  );
  await db.batch(ibges.map((ibge) => comando.bind(chatId, ibge, instante)));
}

export async function ibgesDoChat(db: D1Database, chatId: number): Promise<string[]> {
  const { results } = await db
    .prepare("SELECT ibge FROM inscritos WHERE chat_id = ?")
    .bind(chatId)
    .all<{ ibge: string }>();
  return results.map((linha) => linha.ibge);
}

export async function removerChat(db: D1Database, chatId: number): Promise<void> {
  await db.prepare("DELETE FROM inscritos WHERE chat_id = ?").bind(chatId).run();
}

export async function listarTodos(db: D1Database): Promise<Inscrito[]> {
  const { results } = await db
    .prepare("SELECT chat_id, ibge FROM inscritos ORDER BY chat_id, ibge")
    .all<Inscrito>();
  return results;
}
