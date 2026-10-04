/// <reference types="astro/client" />

interface ImportMetaEnv {
  /** Pasta (relativa à base do site) de onde o site lê os JSON publicados. Padrão: `data/`. */
  readonly PUBLIC_DADOS_URL?: string;
  /** Nome do bot do Telegram, sem @. Padrão: `VigiaDeslizamentosBot`. */
  readonly PUBLIC_TELEGRAM_BOT?: string;
  /** "true" exibe o mapa da Defesa Civil de SC em iframe (só depois da autorização, RN10). */
  readonly PUBLIC_SC_IFRAME?: string;
}
