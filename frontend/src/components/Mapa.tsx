import "leaflet/dist/leaflet.css";
import "../styles/mapa.css";
import type { ReactNode, Ref } from "react";
import type { Idioma } from "../lib/preferencias";
import type { Setor } from "../lib/setores";
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
  /** Setores do SGB (tela Áreas de risco). Sem a prop, nada muda nas outras telas. */
  setores?: Setor[];
  setorSelecionado?: string | null;
  onSelecionarSetor?: (id: string) => void;
  /** false = um marcador por município com o nº de setores; true = setores individuais. */
  setoresIndividuais?: boolean;
  /** Avisado quando o zoom muda: `longe` segue rotulosDeLonge(zoom, zoomInicial) desta tela. */
  onLonge?: (longe: boolean) => void;
  /** Pinos visíveis (camada INMET ligada). Padrão: true. Com pinos ocultos, o enquadramento ignora os pinos. */
  pinosVisiveis?: boolean;
  /** Nome acessível do mapa nesta tela (padrão: o de hoje). */
  rotuloMapa?: string;
  /** Nome acessível de cada município nesta tela (padrão: rotuloAria com o índice). */
  rotuloMunicipio?: (ibge: string, nome: string) => string;
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
