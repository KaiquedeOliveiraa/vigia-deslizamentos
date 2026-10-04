import { Bell } from "lucide-react";
import { useState } from "react";
import { tradutor } from "../i18n";
import type { Idioma } from "../lib/preferencias";
import JanelaTelegram, { DiscoTelegram } from "./JanelaTelegram";

interface Props {
  lang: Idioma;
  municipios: readonly string[];
}

/** Porta de entrada do Telegram na Cartilha e em Contatos. */
export default function BannerTelegram({ lang, municipios }: Props) {
  const t = tradutor(lang);
  const [aberto, setAberto] = useState(false);
  return (
    <div className="tgban">
      <DiscoTelegram />
      <div>
        <b>{t("Receba os alertas no Telegram")}</b>
        <span>{t("O bot do VIGIA avisa quando o risco subir. Você escolhe os municípios no próprio bot. Grátis.")}</span>
      </div>
      <button type="button" className="btn pri" onClick={() => setAberto(true)}>
        <Bell aria-hidden="true" />
        {t("Quero receber")}
      </button>
      <JanelaTelegram lang={lang} aberto={aberto} aoFechar={() => setAberto(false)} municipios={municipios} />
    </div>
  );
}
