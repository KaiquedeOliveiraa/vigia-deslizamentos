/** URL de um arquivo publicado (indices.json, contatos.json…): base do Astro + PUBLIC_DADOS_URL (padrão `data/`). */
export function urlDados(
  arquivo: string,
  base: string = import.meta.env.BASE_URL,
  dados: string | undefined = import.meta.env.PUBLIC_DADOS_URL,
): string {
  const partes = [base, dados ?? "data/", arquivo].map((p) => p.replace(/^\/+|\/+$/g, "")).filter(Boolean);
  return "/" + partes.join("/");
}
