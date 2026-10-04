import { defineConfig } from "astro/config";
import react from "@astrojs/react";

export default defineConfig({
  site: "https://kaiquedeoliveiraa.github.io",
  base: "/vigia-deslizamentos",
  integrations: [react()],
});
