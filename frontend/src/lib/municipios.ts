// GeoJSON dos municípios lido uma vez só, para todas as telas.
import geojson from "../data/municipios.geojson?raw";
import { municipiosMonitorados, type FeicaoMunicipio } from "./mapa";

export const FEICOES: readonly FeicaoMunicipio[] = JSON.parse(geojson).features;

/** { ibge, nome } dos monitorados, em ordem alfabética. */
export const MONITORADOS = municipiosMonitorados(FEICOES);

/** Nome de cada município do GeoJSON (monitorados e vizinhos), por IBGE. */
export const NOMES: ReadonlyMap<string, string> = new Map(FEICOES.map((f) => [f.properties.ibge, f.properties.nome]));
