import { describe, expect, it } from "vitest";
import { botTelegram, iframeSC, linkTelegram, urlDados } from "./config";

describe("urlDados", () => {
  it("junta base e pasta de dados sem barras duplicadas", () => {
    expect(urlDados("indices.json", "/vigia-deslizamentos", "data/")).toBe("/vigia-deslizamentos/data/indices.json");
    expect(urlDados("indices.json", "/vigia-deslizamentos/", "/data")).toBe("/vigia-deslizamentos/data/indices.json");
  });

  it("usa data/ quando PUBLIC_DADOS_URL não está definida", () => {
    expect(urlDados("contatos.json", "/", undefined)).toBe("/data/contatos.json");
  });
});

describe("Telegram", () => {
  it("nome do bot vem de PUBLIC_TELEGRAM_BOT, com padrão", () => {
    expect(botTelegram(undefined)).toBe("VigiaDeslizamentosBot");
    expect(botTelegram("")).toBe("VigiaDeslizamentosBot");
    expect(botTelegram("OutroBot")).toBe("OutroBot");
  });

  it("link do bot, com ?start=<ibge> quando aberto de um município", () => {
    expect(linkTelegram("VigiaDeslizamentosBot")).toBe("https://t.me/VigiaDeslizamentosBot");
    expect(linkTelegram("VigiaDeslizamentosBot", "4206900")).toBe("https://t.me/VigiaDeslizamentosBot?start=4206900");
  });
});

describe("iframeSC", () => {
  it("só exibe o iframe com PUBLIC_SC_IFRAME=true (RN10: autorização)", () => {
    expect(iframeSC("true")).toBe(true);
    expect(iframeSC(undefined)).toBe(false);
    expect(iframeSC("")).toBe(false);
    expect(iframeSC("false")).toBe(false);
    expect(iframeSC("1")).toBe(false);
  });
});
