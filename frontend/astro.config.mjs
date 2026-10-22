import { defineConfig } from "astro/config";
import react from "@astrojs/react";

export default defineConfig({
  site: "https://kaiquedeoliveiraa.github.io",
  base: "/vigia-deslizamentos",
  integrations: [react()],
  // Antiga tela Estações: o destino leva o base (sem ele o Astro gera um link que dá 404 no GitHub Pages).
  redirects: {
    "/estacoes": "/vigia-deslizamentos/areas-de-risco/",
    "/es/estacoes": "/vigia-deslizamentos/es/areas-de-risco/",
    "/en/estacoes": "/vigia-deslizamentos/en/areas-de-risco/",
  },
});
