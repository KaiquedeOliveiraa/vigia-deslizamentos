import { tradutor } from "../i18n";
import { CAMADAS, type IdCamada } from "../lib/mapa";
import type { Idioma } from "../lib/preferencias";

interface Props {
  lang: Idioma;
  camada: IdCamada;
  aoMudar: (camada: IdCamada) => void;
}

/** Mapa de fundo: Satélite, Neutro, Ruas e Relevo. */
export default function Camadas({ lang, camada, aoMudar }: Props) {
  const t = tradutor(lang);
  return (
    <div className="float layers" role="group" aria-label={t("Camadas do mapa")}>
      {CAMADAS.map((c) => (
        <button key={c.id} type="button" aria-pressed={c.id === camada} onClick={() => aoMudar(c.id)}>
          {t(c.nome)}
        </button>
      ))}
    </div>
  );
}
