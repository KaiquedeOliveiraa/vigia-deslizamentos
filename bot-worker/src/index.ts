import { segredoConfere, segredoDoBearer } from "./autenticacao";
import { listarTodos, removerChat } from "./inscritos";
import type { Env } from "./tipos";

const ROTA_REMOCAO = /^\/inscritos\/([^/]+)$/;
const CHAT_ID_VALIDO = /^-?\d+$/;

function autorizado(requisicao: Request, env: Env): boolean {
  const recebido = segredoDoBearer(requisicao.headers.get("Authorization"));
  return segredoConfere(recebido, env.VIGIA_WORKER_SEGREDO);
}

async function tratarInscritos(requisicao: Request, env: Env, caminho: string): Promise<Response> {
  if (!autorizado(requisicao, env)) return new Response("Não autorizado", { status: 401 });

  if (caminho === "/inscritos" && requisicao.method === "GET") {
    return Response.json({ inscritos: await listarTodos(env.DB) });
  }

  const remocao = ROTA_REMOCAO.exec(caminho);
  if (remocao && requisicao.method === "DELETE") {
    const texto = remocao[1]!;
    if (!CHAT_ID_VALIDO.test(texto)) return new Response("chat_id inválido", { status: 400 });
    await removerChat(env.DB, Number(texto));
    return new Response(null, { status: 204 });
  }

  return new Response("Não encontrado", { status: 404 });
}

export default {
  async fetch(requisicao: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(requisicao.url);
    if (pathname === "/inscritos" || pathname.startsWith("/inscritos/")) {
      return tratarInscritos(requisicao, env, pathname);
    }
    return new Response("Não encontrado", { status: 404 });
  },
} satisfies ExportedHandler<Env>;
