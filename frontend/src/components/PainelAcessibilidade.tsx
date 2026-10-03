import { useEffect, useState } from "react";
import { tradutor } from "../i18n";
import {
  aplicarPreferencias,
  lerPreferencias,
  PADRAO,
  salvarPreferencias,
  type Idioma,
  type Preferencias,
} from "../lib/preferencias";
import { rota } from "../lib/telas";
import { anunciar } from "./anunciar";
import Dialogo from "./Dialogo";

interface Props {
  lang: Idioma;
  /** Rota da tela atual, para trocar de idioma sem sair dela. */
  tela: string;
  aberto: boolean;
  aoFechar: () => void;
}

type Opcao<K extends keyof Preferencias> = [Preferencias[K], string];

const IDIOMAS: Opcao<"lang">[] = [
  ["pt", "Português"],
  ["es", "Español"],
];
const TEMAS: Opcao<"theme">[] = [
  ["auto", "Automático"],
  ["light", "Claro"],
  ["dark", "Escuro"],
  ["contraste", "Alto contraste"],
];
const PALETAS: Opcao<"pal">[] = [
  ["geo", "GeoRisk"],
  ["acc", "Acessível (daltonismo)"],
];

/** Idioma, tema e cores do mapa (RF13). */
export default function PainelAcessibilidade({ lang, tela, aberto, aoFechar }: Props) {
  const t = tradutor(lang);
  const [pref, setPref] = useState<Preferencias>({ ...PADRAO, lang });

  // Relê ao abrir: a outra porta de entrada (menu ou cabeçalho) ou a legenda podem ter mudado algo.
  useEffect(() => {
    if (aberto) setPref({ ...lerPreferencias(), lang });
  }, [aberto, lang]);

  function escolher<K extends keyof Preferencias>(chave: K, valor: Preferencias[K], rotulo: string) {
    const nova = { ...pref, [chave]: valor };
    salvarPreferencias(nova);
    if (chave === "lang") {
      if (valor !== lang) location.assign(rota(tela, valor as Idioma));
      return;
    }
    setPref(nova);
    aplicarPreferencias(nova, document.documentElement);
    anunciar(t(`${rotulo} ativado`));
  }

  const grupo = <K extends keyof Preferencias>(chave: K, rotulo: string, opcoes: Opcao<K>[]) => (
    <div className="seg" role="group" aria-label={rotulo}>
      {opcoes.map(([valor, nome]) => (
        <button
          key={valor}
          type="button"
          lang={chave === "lang" ? (valor === "es" ? "es" : "pt-BR") : undefined}
          aria-pressed={pref[chave] === valor}
          data-foco-inicial={chave === "lang" && pref.lang === valor ? "" : undefined}
          onClick={() => escolher(chave, valor, nome)}
        >
          {chave === "lang" ? nome : t(nome)}
        </button>
      ))}
    </div>
  );

  return (
    <Dialogo aberto={aberto} aoFechar={aoFechar} rotulo="acc-t" rotuloFechar={t("Fechar")} className="acc">
      <div className="acc-panel">
        <h2 id="acc-t">{t("Acessibilidade")}</h2>
        <div className="acc-row">
          <span className="lbl">{t("Idioma")}</span>
          {grupo("lang", t("Idioma"), IDIOMAS)}
        </div>
        <div className="acc-row">
          <span className="lbl">{t("Tema")}</span>
          {grupo("theme", t("Tema"), TEMAS)}
          <p>{t("Alto contraste: melhor leitura sob sol forte. Escuro: para ambientes com pouca luz.")}</p>
        </div>
        <div className="acc-row">
          <span className="lbl">{t("Cores do mapa")}</span>
          {grupo("pal", t("Cores do mapa"), PALETAS)}
          <p>{t("Em qualquer opção, cada classe também tem ícone, nome e hachura no mapa.")}</p>
        </div>
      </div>
    </Dialogo>
  );
}
