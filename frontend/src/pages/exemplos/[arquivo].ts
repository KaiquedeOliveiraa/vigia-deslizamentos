import type { APIRoute, GetStaticPaths } from "astro";

// Só em desenvolvimento: serve src/fixtures/*.exemplo.json em /exemplos/<nome>.json (ver .env.development).
const exemplos = import.meta.glob<{ default: unknown }>("../../fixtures/*.exemplo.json", { eager: true });

export const getStaticPaths: GetStaticPaths = () =>
  import.meta.env.DEV
    ? Object.entries(exemplos).map(([caminho, modulo]) => ({
        params: { arquivo: caminho.split("/").pop()!.replace(".exemplo", "") },
        props: { dados: modulo.default },
      }))
    : [];

export const GET: APIRoute = ({ props }) => Response.json(props.dados);
