import { Accessibility, Globe, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { tradutor } from "../i18n";
import { carregar, desatualizado, lerIndices, type Resultado } from "../lib/dados";
import { formatarData, formatarDataHora, formatarHora } from "../lib/formato";
import { lerPreferencias, salvarPreferencias, type Idioma } from "../lib/preferencias";
import { rota, rotaComEstado } from "../lib/telas";
import type { Indices } from "../lib/tipos";
import JanelaTelegram, { DiscoTelegram } from "./JanelaTelegram";
import PainelAcessibilidade from "./PainelAcessibilidade";

interface Props {
  lang: Idioma;
  /** Rota da tela atual, para o seletor PT | ES. */
  tela: string;
  municipios: readonly string[];
}

const IDIOMAS: [Idioma, string, string][] = [
  ["pt", "PT", "Português"],
  ["es", "ES", "Español"],
];

const REAVALIAR_MS = 60_000;

/** Marca, região, Telegram, idioma, acessibilidade e o carimbo dia-alvo/atualização (RN11, RN12). */
export default function Cabecalho({ lang, tela, municipios }: Props) {
  const t = tradutor(lang);
  const [telegram, setTelegram] = useState(false);
  const [acessibilidade, setAcessibilidade] = useState(false);
  const [indices, setIndices] = useState<Resultado<Indices>>();
  const [agora, setAgora] = useState(() => new Date());

  useEffect(() => {
    carregar("indices.json", lerIndices).then(setIndices);
    // RN12 com a aba aberta: reavalia o atraso a cada minuto.
    const timer = setInterval(() => setAgora(new Date()), REAVALIAR_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <>
      <header className="hdr">
        <div className="brand">
          <div className="mark" aria-hidden="true">
            <i />
          </div>
          <div>
            <b>VIGIA</b>
            <small>{t("Deslizamentos")}</small>
          </div>
        </div>
        <div className="region">
          <span className="lbl">{t("Região")}</span>
          <strong>{t("Vale Norte — Alto Vale do Itajaí, SC")}</strong>
        </div>
        <button
          type="button"
          className="hbtn tghdr"
          aria-label={t("Alertas no Telegram")}
          onClick={() => setTelegram(true)}
        >
          <DiscoTelegram />
          <span>{t("Alertas no Telegram")}</span>
        </button>
        <div className="lang" role="group" aria-label={t("Idioma")}>
          <Globe className="lg" aria-hidden="true" />
          {IDIOMAS.map(([valor, sigla, nome]) => (
            <a
              key={valor}
              href={rota(tela, valor)}
              hrefLang={valor === "es" ? "es" : "pt-BR"}
              lang={valor === "es" ? "es" : "pt-BR"}
              aria-current={valor === lang ? "true" : undefined}
              onClick={(e) => {
                e.currentTarget.href = rotaComEstado(tela, valor, location);
                salvarPreferencias({ ...lerPreferencias(), lang: valor });
              }}
            >
              <abbr title={nome}>{sigla}</abbr>
            </a>
          ))}
        </div>
        <button
          type="button"
          className="hbtn a11yb"
          aria-label={t("Acessibilidade: tema, contraste e cores")}
          onClick={() => setAcessibilidade(true)}
        >
          <Accessibility aria-hidden="true" />
        </button>
        <p className="status">
          {!indices && t("Carregando os dados…")}
          {indices?.ok && (
            <>
              <span className="dot" aria-hidden="true" />
              {t("dia-alvo {N} · atualizado {N}", {
                N: [formatarData(indices.dados.dia_alvo_d0), formatarHora(indices.dados.gerado_em)],
              })}
            </>
          )}
          {indices && !indices.ok && (
            <>
              <span className="dot erro" aria-hidden="true" />
              {t("Não foi possível carregar os dados.")}
            </>
          )}
        </p>
      </header>
      {indices?.ok && desatualizado(indices.dados.gerado_em, agora) && (
        <div className="faixa-aviso" role="status">
          <TriangleAlert aria-hidden="true" />
          {t("Dados desatualizados: a última atualização foi em {N}. Os valores podem não refletir a situação atual.", {
            N: formatarDataHora(indices.dados.gerado_em),
          })}
        </div>
      )}
      {indices && !indices.ok && (
        <div className="faixa-aviso" role="alert">
          <TriangleAlert aria-hidden="true" />
          {t("Não foi possível carregar os dados.")}
        </div>
      )}
      <JanelaTelegram lang={lang} aberto={telegram} aoFechar={() => setTelegram(false)} municipios={municipios} />
      <PainelAcessibilidade lang={lang} tela={tela} aberto={acessibilidade} aoFechar={() => setAcessibilidade(false)} />
    </>
  );
}
