import { ChevronsLeft, ChevronsRight, Pause, Play } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { tradutor } from "../i18n";
import { formatarData } from "../lib/formato";
import { passoDia, rotuloDia } from "../lib/mapa";
import type { Idioma } from "../lib/preferencias";
import { anunciar } from "./anunciar";

const INTERVALO_MS = 1100;

interface Props {
  lang: Idioma;
  /** `dia_alvo` de D0 a D3. */
  dias: readonly string[];
  d: number;
  aoMudar: (d: number) => void;
}

/** Cartão "Previsões": o dia-alvo e os próximos dias, com voltar, reproduzir/pausar e avançar. */
export default function Previsoes({ lang, dias, d, aoMudar }: Props) {
  const t = tradutor(lang);
  const nome = useId();
  const [tocando, setTocando] = useState(false);

  function ir(novo: number) {
    aoMudar(novo);
    const data = formatarData(dias[novo], "curto");
    anunciar(novo ? t("Previsão para {N}", { N: data }) : t("Hoje, {N}", { N: data }));
  }
  const passo = (p: number) => ir(passoDia(d, p, dias.length));

  // Um passo por vez: o timer some ao pausar, ao mudar de dia e ao sair da tela.
  useEffect(() => {
    if (!tocando) return;
    const timer = setTimeout(() => passo(1), INTERVALO_MS);
    return () => clearTimeout(timer);
  }, [tocando, d]);

  function alternar() {
    if (!tocando) passo(1);
    setTocando(!tocando);
  }

  return (
    <div className="float prevs" role="group" aria-label={t("Previsões")}>
      <span className="lbl" aria-hidden="true">
        {t("Previsões")}
      </span>
      {dias.map((dia, i) => (
        <label key={dia} className={i === d ? "on" : undefined}>
          <input type="radio" name={nome} checked={i === d} onChange={() => ir(i)} />
          {formatarData(dia, "curto")}
          <small>{t(rotuloDia(i))}</small>
        </label>
      ))}
      <div className="ctl">
        <button type="button" aria-label={t("Dia anterior")} onClick={() => passo(-1)}>
          <ChevronsLeft aria-hidden="true" />
        </button>
        <button type="button" aria-label={t(tocando ? "Pausar" : "Reproduzir")} onClick={alternar}>
          {tocando ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
        </button>
        <button type="button" aria-label={t("Próximo dia")} onClick={() => passo(1)}>
          <ChevronsRight aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

/** Faixa sobre o mapa em D1–D3 (RN06). */
export function FaixaPrevisao({ lang, dia, d }: { lang: Idioma; dia: string; d: number }) {
  if (d === 0) return null;
  return <div className="dayflag">{tradutor(lang)("Previsão · {N} — valores estimados", { N: formatarData(dia, "curto") })}</div>;
}
