import { Info, Lock, LockOpen, X } from "lucide-react";
import { useEffect, useRef, useState, type FocusEvent } from "react";
import { tradutor } from "../i18n";
import { CLASSES, infoClasse, LIMIAR_ALERTA, NAO_MONITORADO } from "../lib/classes";
import { formatarIndice } from "../lib/formato";
import { paletaAplicada, trocarPaleta, type Idioma, type Paleta } from "../lib/preferencias";
import { anunciar } from "./anunciar";
import SeloClasse from "./SeloClasse";

const DO_MAIOR_RISCO = [...CLASSES].reverse();

/** Legenda recolhida numa faixa de cores; abre com hover, foco ou toque; o cadeado a mantém aberta. */
export default function Legenda({ lang }: { lang: Idioma }) {
  const t = tradutor(lang);
  const [aberta, setAberta] = useState(false);
  const [fixada, setFixada] = useState(false);
  const [paleta, setPaleta] = useState<Paleta>("geo");
  const raiz = useRef<HTMLDivElement>(null);
  const cadeado = useRef<HTMLButtonElement>(null);
  const fechar = useRef<HTMLButtonElement>(null);

  // A paleta vive na classe do <html>; o painel de acessibilidade também a troca.
  useEffect(() => {
    const html = document.documentElement;
    const ler = () => setPaleta(paletaAplicada(html));
    ler();
    const observador = new MutationObserver(ler);
    observador.observe(html, { attributes: true, attributeFilter: ["class"] });
    return () => observador.disconnect();
  }, []);

  function abrirPelaFaixa() {
    setAberta(true);
    setTimeout(() => fechar.current?.focus(), 0);
  }

  function sair() {
    if (!fixada && !raiz.current?.contains(document.activeElement)) setAberta(false);
  }

  function perdeuFoco(e: FocusEvent) {
    if (!fixada && !raiz.current?.contains(e.relatedTarget)) setAberta(false);
  }

  function alternarFixada() {
    setFixada(!fixada);
    setAberta(!fixada);
    anunciar(t(fixada ? "Legenda solta" : "Legenda fixada"));
  }

  function recolher() {
    setFixada(false);
    setAberta(false);
    // O foco volta ao cadeado: na faixa, ela abriria a legenda de novo.
    cadeado.current?.focus();
  }

  function escolherPaleta(p: Paleta) {
    trocarPaleta(p, document.documentElement);
    anunciar(t(p === "acc" ? "Cores acessíveis ativadas" : "Cores GeoRisk ativadas"));
  }

  const rotuloCadeado = t(fixada ? "Destravar legenda" : "Fixar legenda");
  return (
    <div
      ref={raiz}
      className={`leg${aberta ? " open" : ""}${fixada ? " pinned" : ""}`}
      onMouseEnter={() => setAberta(true)}
      onMouseLeave={sair}
      onBlur={perdeuFoco}
    >
      <button ref={cadeado} type="button" className="lockb" aria-pressed={fixada} aria-label={rotuloCadeado} title={rotuloCadeado} onClick={alternarFixada}>
        {fixada ? <Lock aria-hidden="true" /> : <LockOpen aria-hidden="true" />}
      </button>
      <button
        type="button"
        className="strip"
        aria-expanded={aberta}
        aria-label={t("Mostrar legenda das classes de risco")}
        onClick={abrirPelaFaixa}
        onFocus={abrirPelaFaixa}
      >
        {DO_MAIOR_RISCO.map((c) => (
          <i key={c.numero} style={{ background: c.cor }} />
        ))}
        <i style={{ background: NAO_MONITORADO.cor }} />
      </button>
      <div className="card" role="group" aria-label={t("Legenda")}>
        <div className="hd">
          <Info aria-hidden="true" />
          <span className="lbl">{t("Legenda")}</span>
          <button ref={fechar} type="button" className="close" aria-label={t("Recolher legenda")} onClick={recolher}>
            <X aria-hidden="true" />
          </button>
        </div>
        <h4>{t("Análise regional dinâmica de risco de deslizamento")}</h4>
        <div className="rows">
          {DO_MAIOR_RISCO.map((c) => (
            <div key={c.numero}>
              <SeloClasse classe={c.numero} />
              {t(c.nome)}
              <span className="r">{c.faixa}</span>
            </div>
          ))}
          <div>
            <SeloClasse classe={null} />
            {t("não monitorado")}
          </div>
        </div>
        <div className="foot">
          <span className="lbl">{t("Cores")}</span>
          <div className="seg" role="group" aria-label={t("Paleta de cores do mapa")}>
            <button type="button" aria-pressed={paleta === "geo"} onClick={() => escolherPaleta("geo")}>
              {t("GeoRisk")}
            </button>
            <button type="button" aria-pressed={paleta === "acc"} onClick={() => escolherPaleta("acc")}>
              {t("Acessível")}
            </button>
          </div>
        </div>
        <p className="hint">
          {t("Alerta a partir de {N} ({C}). Classes com hachuras no mapa: {C} ou acima.", {
            N: formatarIndice(LIMIAR_ALERTA),
            C: [infoClasse(4).nome, infoClasse(4).nome],
          })}
        </p>
      </div>
    </div>
  );
}
