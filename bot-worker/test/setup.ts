import { applyD1Migrations } from "cloudflare:test";
import { env } from "cloudflare:workers";

await applyD1Migrations(env.DB, (env as unknown as { MIGRACOES: never[] }).MIGRACOES);
