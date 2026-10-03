import { tradutor } from "../i18n";
import { CAMADAS, type Camada } from "../lib/mapa";
import type { Idioma } from "../lib/preferencias";

interface Props {
  lang: Idioma;
  camada: Camada;
  aoMudar: (camada: Camada) => void;
}

/** Mapa de fundo: Satélite, Neutro, Ruas e Relevo. */
export default function Camadas({ lang, camada, aoMudar }: Props) {
  const t = tradutor(lang);
  return (
    <div className="float layers" role="group" aria-label={t("Camadas do mapa")}>
      {CAMADAS.map((c) => (
        <button key={c.id} type="button" aria-pressed={c.id === camada.id} onClick={() => aoMudar(c)}>
          {t(c.nome)}
        </button>
      ))}
    </div>
  );
}
