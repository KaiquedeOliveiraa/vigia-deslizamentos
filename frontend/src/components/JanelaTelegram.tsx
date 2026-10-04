import { Bell, Check, Copy, MapPin, Send, X } from "lucide-react";
import { useState } from "react";
import { tradutor } from "../i18n";
import { botTelegram, linkTelegram } from "../lib/config";
import { formatarHora } from "../lib/formato";
import type { Idioma } from "../lib/preferencias";
import { anunciar } from "./anunciar";
import Dialogo from "./Dialogo";

interface Props {
  lang: Idioma;
  aberto: boolean;
  aoFechar: () => void;
  /** Nomes dos municípios monitorados, para a prévia do teclado do bot. */
  municipios: readonly string[];
  /** Aberta do painel de um município: o link leva `?start=<ibge>`. */
  ibge?: string;
}

export const DiscoTelegram = () => (
  <span className="tgdisc" aria-hidden="true">
    <Send />
  </span>
);

export default function JanelaTelegram({ lang, aberto, aoFechar, municipios, ibge }: Props) {
  const t = tradutor(lang);
  const bot = botTelegram();
  const [copiado, setCopiado] = useState(false);

  const copiar = () =>
    navigator.clipboard
      ?.writeText(`@${bot}`)
      .then(() => {
        setCopiado(true);
        anunciar(t("Nome do bot copiado"));
      })
      .catch(() => {});

  return (
    <Dialogo aberto={aberto} aoFechar={aoFechar} rotulo="tgm-t" rotuloFechar={t("Fechar")} className="tgm">
      <div className="tgm-main">
        <h2 id="tgm-t">
          <DiscoTelegram /> {t("Receba os alertas no Telegram")}
        </h2>
        <p className="tgm-sub">
          {t("Toque no botão, abra o bot do VIGIA e toque em")} <b>{t("Iniciar")}</b>
          {t(". Você vai receber os avisos e alertas de risco de deslizamento. Dentro do bot você escolhe os municípios.")}
        </p>
        <ul className="tgm-list">
          <li>
            <Bell aria-hidden="true" />
            {t("Aviso quando um município entrar em alerta")}
          </li>
          <li>
            <MapPin aria-hidden="true" />
            {t("Você escolhe os municípios dentro do bot")}
          </li>
          <li>
            <X aria-hidden="true" />
            {t("Grátis. Para sair, envie /parar")}
          </li>
        </ul>
        <a className="btn pri tgm-go" href={linkTelegram(bot, ibge)} target="_blank" rel="noopener" data-foco-inicial>
          <Send aria-hidden="true" />
          {t("Abrir no Telegram")}
        </a>
        <p className="tgm-or">
          {t("Ou procure")} <span className="mono">@{bot}</span> {t("no Telegram")}
          <button type="button" className="tgm-copy" aria-label={t("Copiar nome do bot")} onClick={copiar}>
            {copiado ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          </button>
        </p>
      </div>
      <aside className="tgm-prev" aria-label={t("Exemplo de conversa com o bot")}>
        <div className="lbl">{t("Como aparece no Telegram")}</div>
        <div className="tgm-chat">
          <div className="tgm-bot">
            <span className="tgdisc" aria-hidden="true">
              <Bell />
            </span>
            <div>
              <b>{t("VIGIA Deslizamentos")}</b>
              <small>{t("bot")}</small>
            </div>
          </div>
          <div className="tgm-msg">
            {t("Olá! Eu aviso quando o risco de deslizamento subir. Quais municípios você quer acompanhar?")}
            <span className="t">{formatarHora(new Date().toISOString())}</span>
          </div>
          <div className="tgm-kb">
            {municipios.map((m) => (
              <span key={m}>{m}</span>
            ))}
            <span className="all">{t("Todos")}</span>
          </div>
        </div>
      </aside>
    </Dialogo>
  );
}
