import path from "node:path";
import { cloudflareTest, readD1Migrations } from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";

export default defineConfig(async () => {
  const migracoes = await readD1Migrations(path.join(import.meta.dirname, "migrations"));
  return {
    plugins: [
      cloudflareTest({
        wrangler: { configPath: "./wrangler.jsonc" },
        miniflare: {
          bindings: {
            MIGRACOES: migracoes,
            TELEGRAM_TOKEN: "token-de-teste",
            TELEGRAM_WEBHOOK_SEGREDO: "webhook-de-teste",
            VIGIA_WORKER_SEGREDO: "segredo-de-teste",
          },
        },
      }),
    ],
    test: { setupFiles: ["./test/setup.ts"] },
  };
});
