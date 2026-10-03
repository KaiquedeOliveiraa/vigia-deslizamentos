/// <reference types="astro/client" />

interface ImportMetaEnv {
  /** Pasta (relativa à base do site) de onde o site lê os JSON publicados. Padrão: `data/`. */
  readonly PUBLIC_DADOS_URL?: string;
}
