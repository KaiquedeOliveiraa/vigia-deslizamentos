import "../styles/cartilha.css";
import { Backpack, Check, DoorOpen, Phone } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import { EMERGENCIA, FASES, FONTES, MOCHILA, NAO_FACA, SECOES, SINAIS, type Ilustracao } from "../conteudo/cartilha";
import { tradutor } from "../i18n";
import { abaPorTecla, progressoMochila, secaoAtiva } from "../lib/cartilha";
import type { Idioma } from "../lib/preferencias";
import { rota } from "../lib/telas";
import BannerTelegram from "./BannerTelegram";

interface Props {
  lang: Idioma;
  municipios: readonly string[];
}

// Ilustrações de traço do protótipo (64×64): `s` traço da marca, `a` destaque, `g` grama, `m` lama.
const ILUSTRACOES: Record<Ilustracao, ReactNode> = {
  racha: (
    <>
      <path className="s" d="M10 30 32 12l22 18v24H10z" />
      <path className="s" d="M26 54V40h12v14" />
      <path className="a" d="M40 16l-4 8 6 4-5 8 4 5" />
    </>
  ),
  janela: (
    <>
      <path className="s" d="M14 14h36v36H14z" />
      <path className="a" d="M19 19l26 3-3 24-25-4z" />
      <path className="s" d="M31 21l-2 23" />
    </>
  ),
  inclina: (
    <>
      <path className="s" d="M4 54h56" />
      <path className="a" d="M20 54l10-40" />
      <path className="s" d="M27 26h9M24 36h8" />
      <path className="s" d="M44 54l6-22" />
      <path className="g" d="M50 30c-10 0-12-12-2-16 6-3 12 4 10 10-1 4-4 6-8 6z" />
      <path className="s" d="M50 30c-10 0-12-12-2-16 6-3 12 4 10 10-1 4-4 6-8 6z" />
    </>
  ),
  agua: (
    <>
      <path className="s" d="M4 22c14 0 22 10 30 22s14 12 26 12" />
      <path className="m" d="M30 44c-3 5-2 9 2 9s5-4 2-9l-2-4z" />
      <path className="m" d="M42 50c-2 3-1 6 1.5 6s3-3 1.5-6l-1.5-2.5z" />
      <path className="a" d="M14 30c2-4 6-6 10-4" />
    </>
  ),
  estalo: (
    <>
      <path className="s" d="M4 50c10 0 18-6 26-16s18-18 30-18" />
      <path className="a" d="M38 42c3 3 3 8 0 11M44 38c5 5 5 14 0 19M50 34c7 7 7 20 0 27" />
    </>
  ),
  muro: (
    <>
      <path className="s" d="M8 54h48M12 54V14h40v40" />
      <path className="s" d="M12 24h40M12 34h14M12 44h40M22 14v10M40 14v10M30 44v10" />
      <path className="a" d="M26 30c8-4 16-4 22 4-6 6-14 8-22 4" />
    </>
  ),
};

// Topo da seção abaixo da barra de âncoras fixa (mesma folga do protótipo).
const LIMITE_SECAO = 70;
// ponytail: tempo fixo para a rolagem suave do clique não trocar o destaque; usar `scrollend` quando o Safari tiver.
const ROLAGEM_MS = 1000;

const semMovimento = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Cartilha (RF11): sinais de perigo, o que fazer, mochila e o que não fazer. */
export default function Cartilha({ lang, municipios }: Props) {
  const t = tradutor(lang);
  const [virados, setVirados] = useState<ReadonlySet<number>>(new Set());
  const [fase, setFase] = useState(0);
  const [mochila, setMochila] = useState<ReadonlySet<number>>(new Set());
  const [ativa, setAtiva] = useState(0);
  const abas = useRef<(HTMLButtonElement | null)[]>([]);
  const rolandoAte = useRef(0);

  useEffect(() => {
    const area = document.getElementById("conteudo");
    if (!area) return;
    const aoRolar = () => {
      if (performance.now() < rolandoAte.current) return;
      const topoArea = area.getBoundingClientRect().top;
      const topos = SECOES.map((s) => document.getElementById(s.id)!.getBoundingClientRect().top - topoArea);
      setAtiva(secaoAtiva(topos, LIMITE_SECAO, area.scrollTop + area.clientHeight >= area.scrollHeight - 2));
    };
    area.addEventListener("scroll", aoRolar, { passive: true });
    return () => area.removeEventListener("scroll", aoRolar);
  }, []);

  const irPara = (e: MouseEvent<HTMLAnchorElement>, id: string, i: number) => {
    e.preventDefault();
    setAtiva(i);
    rolandoAte.current = performance.now() + ROLAGEM_MS;
    const secao = document.getElementById(id)!;
    secao.scrollIntoView({ behavior: semMovimento() ? "auto" : "smooth", block: "start" });
    secao.querySelector("h2")!.focus({ preventScroll: true });
  };

  const alternar = (conjunto: ReadonlySet<number>, i: number) => {
    const novo = new Set(conjunto);
    if (!novo.delete(i)) novo.add(i);
    return novo;
  };

  const teclaAba = (e: KeyboardEvent, i: number) => {
    const proxima = abaPorTecla(i, e.key, FASES.length);
    if (proxima === null) return;
    e.preventDefault();
    setFase(proxima);
    abas.current[proxima]?.focus();
  };

  const progresso = progressoMochila(t, mochila.size, MOCHILA.length);
  const faseAtual = FASES[fase];

  return (
    <div className="cart">
      <section className="hero">
        <div>
          <div className="lbl">{t("Cartilha")}</div>
          <h1>{t("Deslizamento: como se proteger")}</h1>
          <p>{t("Aprenda a ver os sinais e o que fazer. É rápido: toque nos cartões.")}</p>
        </div>
        <a className="sos" href={rota("contatos", lang)}>
          <Phone aria-hidden="true" />
          <b>{EMERGENCIA}</b>
          <span>
            {t("Emergência?")}
            <br />
            {t("Ver contatos")}
          </span>
        </a>
      </section>

      <nav className="tabs" aria-label={t("Seções da cartilha")}>
        {SECOES.map((s, i) => (
          <a key={s.id} href={`#${s.id}`} className={i === ativa ? "on" : undefined} aria-current={i === ativa ? "true" : undefined} onClick={(e) => irPara(e, s.id, i)}>
            {t(s.rotulo, { N: String(i + 1) })}
          </a>
        ))}
      </nav>

      <section className="sec" id="sinais" aria-labelledby="h-s">
        <h2 id="h-s" tabIndex={-1}>
          <span className="n" aria-hidden="true">1</span>
          {t("Sinais de perigo")}
        </h2>
        <p>{t("Toque em cada cartão para ver o que fazer.")}</p>
        <div className="flips">
          {SINAIS.map((s, i) => {
            const virado = virados.has(i);
            return (
              <button key={s.ilustracao} type="button" className="flip" aria-pressed={virado} onClick={() => setVirados((v) => alternar(v, i))}>
                <span className="f" aria-hidden={virado}>
                  <svg className="ill" viewBox="0 0 64 64" aria-hidden="true">
                    {ILUSTRACOES[s.ilustracao]}
                  </svg>
                  <b>{t(s.titulo)}</b>
                  <small>{t(s.detalhe)}</small>
                </span>
                <span className="b" aria-hidden={!virado}>
                  <DoorOpen aria-hidden="true" />
                  <b>{t("Saia do local agora")}</b>
                  <span>{t("Depois ligue {N}", { N: EMERGENCIA })}</span>
                </span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="sec" id="fases" aria-labelledby="h-f">
        <h2 id="h-f" tabIndex={-1}>
          <span className="n" aria-hidden="true">2</span>
          {t("O que fazer")}
        </h2>
        <p>{t("Antes, durante e depois da chuva forte.")}</p>
        <div className="steps" role="tablist" aria-label={t("Momento")}>
          {FASES.map((f, i) => (
            <button
              key={f.id}
              ref={(b) => {
                abas.current[i] = b;
              }}
              type="button"
              role="tab"
              id={`tab-${f.id}`}
              aria-controls="pan-fase"
              aria-selected={i === fase}
              tabIndex={i === fase ? 0 : -1}
              onClick={() => setFase(i)}
              onKeyDown={(e) => teclaAba(e, i)}
            >
              <span className="k" aria-hidden="true">
                {i + 1}
              </span>
              {t(f.rotulo)}
            </button>
          ))}
        </div>
        <div id="pan-fase" role="tabpanel" aria-labelledby={`tab-${faseAtual.id}`} tabIndex={0} className={`tiles panel-${faseAtual.id}`}>
          {faseAtual.blocos.map(({ icone: Icone, texto, vars }) => (
            <div key={texto} className="tile">
              <span className="ic" aria-hidden="true">
                <Icone />
              </span>
              <b>{t(texto, vars)}</b>
            </div>
          ))}
        </div>
      </section>

      <section className="sec" id="kit" aria-labelledby="h-k">
        <h2 id="h-k" tabIndex={-1}>
          <span className="n" aria-hidden="true">3</span>
          {t("Monte sua mochila de emergência")}
        </h2>
        <p>{t("Toque no que você já tem separado.")}</p>
        <div className="kitwrap">
          <div className="kit">
            {MOCHILA.map(({ icone: Icone, texto }, i) => (
              <button key={texto} type="button" aria-pressed={mochila.has(i)} onClick={() => setMochila((m) => alternar(m, i))}>
                <Icone aria-hidden="true" />
                {t(texto)}
                <span className="ok" aria-hidden="true">
                  <Check />
                </span>
              </button>
            ))}
          </div>
          <div className={progresso.pronta ? "bagcard pronta" : "bagcard"} aria-live="polite">
            <Backpack className="bg" aria-hidden="true" />
            <div className="bar" aria-hidden="true">
              <i style={{ width: `${progresso.pct}%` }} />
            </div>
            <b>{progresso.contagem}</b>
            <span>{progresso.mensagem}</span>
          </div>
        </div>
      </section>

      <section className="sec" id="evitar" aria-labelledby="h-e">
        <h2 id="h-e" tabIndex={-1}>
          <span className="n" aria-hidden="true">4</span>
          {t("Não faça")}
        </h2>
        <p>{t("Isso deixa a encosta mais perigosa.")}</p>
        <ul className="nao">
          {NAO_FACA.map(({ icone: Icone, texto }) => (
            <li key={texto}>
              <span className="ic" aria-hidden="true">
                <Icone />
              </span>
              {t(texto)}
            </li>
          ))}
        </ul>
      </section>

      <div className="tgwrap">
        <BannerTelegram lang={lang} municipios={municipios} />
      </div>

      <p className="fonte">
        {t("Baseado nas cartilhas da")}{" "}
        <a href={FONTES.rj} target="_blank" rel="noopener">
          {t("Defesa Civil RJ")}
        </a>{" "}
        {t("e do")}{" "}
        <a href={FONTES.sp} target="_blank" rel="noopener">
          {t("SP Sempre Alerta")}
        </a>
        .
      </p>
    </div>
  );
}
