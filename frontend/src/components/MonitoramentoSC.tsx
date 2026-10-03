import "../styles/sc.css";
import { ExternalLink, RadioTower } from "lucide-react";
import { useEffect, useState } from "react";
import { tradutor } from "../i18n";
import { iframeSC } from "../lib/config";
import type { Idioma } from "../lib/preferencias";

const URL_SC = "https://monitoramento.defesacivil.sc.gov.br/mapa";
const URL_CURTA = URL_SC.replace("https://", "");
const ESPERA_MS = 15000;

/** Mapa oficial da Defesa Civil de SC em iframe (com a flag, RN10) ou o plano B com o link (RF08). */
export default function MonitoramentoSC({ lang }: { lang: Idioma }) {
  const t = tradutor(lang);
  const [estado, setEstado] = useState<"carregando" | "ok" | "falhou">(iframeSC() ? "carregando" : "falhou");

  // Um iframe recusado nem sempre dispara erro: sem `load` dentro do prazo, vale o plano B.
  useEffect(() => {
    if (estado !== "carregando") return;
    const timer = setTimeout(() => setEstado("falhou"), ESPERA_MS);
    return () => clearTimeout(timer);
  }, [estado]);

  const abrir = (texto: string) => (
    <a className="btn pri" href={URL_SC} target="_blank" rel="noopener">
      <ExternalLink aria-hidden="true" />
      {texto}
    </a>
  );

  return (
    <div className="sc">
      <section className="card">
        <h1>
          <RadioTower aria-hidden="true" />
          {t("Monitoramento da Defesa Civil de SC")}
        </h1>
        <p>
          {t(
            "Mapa oficial da Secretaria de Estado da Proteção e Defesa Civil com estações, chuva acumulada, níveis de rios e barragens em tempo real. Complementa o índice do VIGIA com a observação das estações.",
          )}
        </p>
        <div className="row">
          {abrir(t("Abrir em nova aba"))}
          {estado !== "falhou" && <span className="note">{t("Visualização integrada abaixo.")}</span>}
        </div>
      </section>
      <div className="frame">
        <div className="bar">
          <RadioTower aria-hidden="true" />
          <b>{t("Painel de monitoramento — Defesa Civil SC")}</b>
          <span className="mono">{URL_CURTA}</span>
        </div>
        {estado === "falhou" ? (
          <div className="fallback">
            <h2>{t("O mapa não pôde ser carregado aqui")}</h2>
            <p>{t("O site da Defesa Civil pode bloquear a exibição dentro de outras páginas. Abra o mapa oficial em uma nova aba.")}</p>
            {abrir(t("Abrir mapa oficial"))}
          </div>
        ) : (
          <iframe
            className="area"
            src={URL_SC}
            title={t("Painel de monitoramento — Defesa Civil SC")}
            loading="lazy"
            referrerPolicy="no-referrer"
            onLoad={() => setEstado("ok")}
            onError={() => setEstado("falhou")}
          />
        )}
        <div className="foot">
          {t("Fonte:")}{" "}
          <a href={URL_SC} target="_blank" rel="noopener">
            {URL_CURTA}
          </a>{" "}
          {t("— Secretaria de Estado da Proteção e Defesa Civil de Santa Catarina")}
        </div>
      </div>
    </div>
  );
}
