import { tradutor } from "../i18n";
import { CAMADAS, type Camada } from "../lib/mapa";
import type { Idioma } from "../lib/preferencias";

interface Props {
  lang: Idioma;
  camada: Camada;
  aoMudar: (camada: Camada) => void;
}

/** Mapa de fundo: Satélite, Neutro, Ruas e Relevo. Abaixo de 900 px os botões não cabem e viram um select (mapa.css). */
export default function Camadas({ lang, camada, aoMudar }: Props) {
  const t = tradutor(lang);
  const rotulo = t("Camadas do mapa");
  return (
    <>
      <div className="float layers" role="group" aria-label={rotulo}>
        {CAMADAS.map((c) => (
          <button key={c.id} type="button" aria-pressed={c.id === camada.id} onClick={() => aoMudar(c)}>
            {t(c.nome)}
          </button>
        ))}
      </div>
      <select
        className="float layers-sel"
        aria-label={rotulo}
        value={camada.id}
        onChange={(e) => {
          const c = CAMADAS.find((x) => x.id === e.target.value);
          if (c) aoMudar(c);
        }}
      >
        {CAMADAS.map((c) => (
          <option key={c.id} value={c.id}>
            {t(c.nome)}
          </option>
        ))}
      </select>
    </>
  );
}
