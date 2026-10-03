import {
  Accessibility,
  BookOpen,
  ChartLine,
  CloudRain,
  Gauge,
  Map as IconeMapa,
  Menu as IconeMenu,
  Phone,
  RadioTower,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { tradutor } from "../i18n";
import type { Idioma } from "../lib/preferencias";
import { TELAS, rota } from "../lib/telas";
import PainelAcessibilidade from "./PainelAcessibilidade";

const ICONES: Record<string, LucideIcon> = {
  "": IconeMapa,
  simulacao: CloudRain,
  dados: ChartLine,
  "monitoramento-sc": RadioTower,
  estacoes: Gauge,
  cartilha: BookOpen,
  contatos: Phone,
};

interface Props {
  lang: Idioma;
  /** Rota da tela atual (item ativo). */
  tela: string;
}

/** Rail lateral no desktop; barra inferior abaixo de 900 px. */
export default function Menu({ lang, tela }: Props) {
  const t = tradutor(lang);
  const [expandido, setExpandido] = useState(false);
  const [acessibilidade, setAcessibilidade] = useState(false);

  return (
    <nav className={`rail${expandido ? " aberto" : ""}`} aria-label={t("Navegação principal")}>
      <div className="top">
        <button
          type="button"
          className="burger"
          aria-label={t("Mostrar nomes do menu")}
          aria-expanded={expandido}
          onClick={() => setExpandido(!expandido)}
        >
          <IconeMenu aria-hidden="true" />
        </button>
      </div>
      <ul className="navlist">
        {TELAS.map(({ rota: r, nome, curto }) => {
          const Icone = ICONES[r];
          const ativo = r === tela;
          return (
            <li key={r}>
              <a
                href={rota(r, lang)}
                className={`item${ativo ? " on" : ""}`}
                aria-current={ativo ? "page" : undefined}
              >
                <Icone aria-hidden="true" />
                <span className="full">{t(nome)}</span>
                {/* Celular: o nome acessível começa pelo rótulo curto visível (WCAG 2.5.3). */}
                <span className="short">
                  {t(curto)}
                  {curto !== nome && <span className="sr-only"> — {t(nome)}</span>}
                </span>
                <em className="tip" aria-hidden="true">
                  {t(nome)}
                </em>
              </a>
            </li>
          );
        })}
      </ul>
      <div className="foot">
        <button type="button" className="item" onClick={() => setAcessibilidade(true)}>
          <Accessibility aria-hidden="true" />
          <span className="full">{t("Acessibilidade")}</span>
          <em className="tip" aria-hidden="true">
            {t("Acessibilidade")}
          </em>
        </button>
      </div>
      <PainelAcessibilidade lang={lang} tela={tela} aberto={acessibilidade} aoFechar={() => setAcessibilidade(false)} />
    </nav>
  );
}
