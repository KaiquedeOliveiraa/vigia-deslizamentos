import "leaflet/dist/leaflet.css";
import "../styles/mapa.css";
import type { ReactNode, Ref } from "react";
import type { Idioma } from "../lib/preferencias";
import type { IndiceClasse } from "../lib/tipos";
// O Leaflet usa `window` ao ser importado: as telas com mapa são ilhas client:only, nunca renderizadas no servidor.
// Import estático (sem lazy) para o módulo baixar junto com a tela (RNF03: o LCP é um tile do mapa).
import MapaLeaflet from "./MapaLeaflet";

export interface MapaApi {
  /** Faz o município piscar 2× (escolhido pela busca). */
  piscar: (ibge: string) => void;
}

/** Ponto no mapa (Estações): `rotulo` é o nome acessível; `balao` aparece quando selecionado. */
export interface Pino {
  id: string;
  lat: number;
  lon: number;
  rotulo: string;
  balao: ReactNode;
}

export interface PropsMapa {
  lang: Idioma;
  /** Índice e classe por IBGE; `null` = sem dados; ausente = município em branco (Estações). */
  valores: Record<string, IndiceClasse | null>;
  selecionado?: string | null;
  onSelecionar?: (ibge: string) => void;
  /** Pins sobre o mapa; o enquadramento passa a incluí-los. */
  pinos?: Pino[];
  pinoSelecionado?: string | null;
  onSelecionarPino?: (id: string) => void;
  /** Seletor de mapa de fundo no alto à direita (padrão: sim). */
  camadas?: boolean;
  ref?: Ref<MapaApi>;
}

/** Mapa dos municípios, igual em todas as telas; `children` são os controles sobrepostos (legenda, busca…). */
export default function Mapa({ children, ...props }: PropsMapa & { children?: ReactNode }) {
  return (
    <div className="mapwrap">
      <MapaLeaflet {...props} />
      {children}
    </div>
  );
}
