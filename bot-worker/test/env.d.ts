import type { Env as EnvDoWorker } from "../src/tipos";

declare global {
  namespace Cloudflare {
    interface Env extends EnvDoWorker {}
  }
}
export {};
