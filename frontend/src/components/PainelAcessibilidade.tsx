import { useEffect, useState } from "react";
import { atributoLang, tradutor } from "../i18n";
import {
  aplicarPreferencias,
  lerPreferencias,
  PADRAO,
  paletaAplicada,
  salvarPreferencias,
  type Idioma,
  type Preferencias,
} from "../lib/preferencias";
import { rotaComEstado } from "../lib/telas";
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
  ["en", "English"],
];
const TEMAS: Opcao<"theme">[] = [
  ["light", "Claro"],
  ["dark", "Escuro"],
];

/** Sem tema escolhido ("auto"), o botão marcado é o que o sistema está usando. */
const temaEmUso = (tema: Preferencias["theme"], sistemaEscuro: boolean): Preferencias["theme"] =>
  tema !== "auto" ? tema : sistemaEscuro ? "dark" : "light";
const PALETAS: Opcao<"pal">[] = [
  ["geo", "GeoRisk"],
  ["acc", "Acessível (daltonismo)"],
];

/** Idioma, tema e cores do mapa (RF13). */
export default function PainelAcessibilidade({ lang, tela, aberto, aoFechar }: Props) {
  const t = tradutor(lang);
  const [pref, setPref] = useState<Preferencias>({ ...PADRAO, lang });
  const [sistemaEscuro, setSistemaEscuro] = useState(false);

  // Relê ao abrir: a outra porta de entrada (menu ou cabeçalho) ou a legenda podem ter mudado algo.
  useEffect(() => {
    if (!aberto) return;
    setPref({ ...lerPreferencias(), lang, pal: paletaAplicada(document.documentElement) });
    // Com o painel aberto e nada escolhido, acompanha o sistema se ele trocar de tema.
    const sistema = matchMedia("(prefers-color-scheme: dark)");
    const atualizar = () => setSistemaEscuro(sistema.matches);
    atualizar();
    sistema.addEventListener("change", atualizar);
    return () => sistema.removeEventListener("change", atualizar);
  }, [aberto, lang]);

  function escolher<K extends keyof Preferencias>(chave: K, valor: Preferencias[K], rotulo: string) {
    const nova = { ...pref, [chave]: valor };
    salvarPreferencias(nova);
    if (chave === "lang") {
      if (valor !== lang) location.assign(rotaComEstado(tela, valor as Idioma, location));
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
          lang={chave === "lang" ? atributoLang(valor as Idioma) : undefined}
          aria-pressed={(chave === "theme" ? temaEmUso(pref.theme, sistemaEscuro) : pref[chave]) === valor}
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
          <p>{t("Escuro: para ambientes com pouca luz.")}</p>
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
