import "leaflet/dist/leaflet.css";
import "../styles/mapa.css";
import { lazy, Suspense, useEffect, useState, type ReactNode, type Ref } from "react";
import type { Idioma } from "../lib/preferencias";

// O Leaflet usa `window` ao ser importado: só carrega no navegador, depois da hidratação.
const MapaLeaflet = lazy(() => import("./MapaLeaflet"));

export interface MapaApi {
  /** Faz o município piscar 2× (escolhido pela busca). */
  piscar: (ibge: string) => void;
}

export interface PropsMapa {
  lang: Idioma;
  /** Índice por IBGE; `null` = sem dados; ausente = município em branco (Estações). */
  valores: Record<string, number | null>;
  selecionado?: string | null;
  onSelecionar?: (ibge: string) => void;
  /** Seletor de mapa de fundo no alto à direita (padrão: sim). */
  camadas?: boolean;
  ref?: Ref<MapaApi>;
}

/** Mapa dos municípios, igual em todas as telas; `children` são os controles sobrepostos (legenda, busca…). */
export default function Mapa({ children, ...props }: PropsMapa & { children?: ReactNode }) {
  const [noNavegador, setNoNavegador] = useState(false);
  useEffect(() => setNoNavegador(true), []);
  return (
    <div className="mapwrap">
      {noNavegador && (
        <Suspense fallback={null}>
          <MapaLeaflet {...props} />
        </Suspense>
      )}
      {children}
    </div>
  );
}
