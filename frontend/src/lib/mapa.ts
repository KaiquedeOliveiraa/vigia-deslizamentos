// Regras do mapa: rótulos acessíveis, geometria para o Leaflet, destaque da busca e dias de previsão.
import type { T } from "../i18n";
import { emAlerta, infoClasse } from "./classes";
import { formatarIndice } from "./formato";
import { normalizar } from "./texto";
import type { IndiceClasse, Indices } from "./tipos";

export interface FeicaoMunicipio {
  type: "Feature";
  properties: { ibge: string; nome: string; monitorado: boolean };
  geometry: { type: "Polygon"; coordinates: number[][][] };
}

/** Índice e classe do município no mapa; `null` = sem dados, `undefined` = sem valor (municípios em branco). */
export type Valor = IndiceClasse | null | undefined;

export type LatLon = [number, number];

/** "Nome: índice X, classe Y[, em alerta]". */
export function rotuloAria(t: T, nome: string, valor: Valor): string {
  if (valor === undefined) return nome;
  if (valor === null) return t("{M}: sem dados", { M: nome });
  const modelo = emAlerta(valor.indice) ? "{M}: índice {N}, classe {C}, em alerta" : "{M}: índice {N}, classe {C}";
  return t(modelo, { M: nome, N: formatarIndice(valor.indice), C: infoClasse(valor.classe).nome });
}

/** Mensagem do aria-live ao selecionar um município. */
export function mensagemSelecao(t: T, nome: string, valor: Valor): string {
  if (valor == null) return rotuloAria(t, nome, valor);
  const modelo = emAlerta(valor.indice)
    ? "{M} selecionado. Índice {N}, classe {C}, em alerta."
    : "{M} selecionado. Índice {N}, classe {C}, sem alerta.";
  return t(modelo, { M: nome, N: formatarIndice(valor.indice), C: infoClasse(valor.classe).nome });
}

/** `valores` do mapa no dia `d` (0 = dia-alvo), com a classe publicada: sem dados ou sem esse dia → `null`. */
export function valoresDoDia(indices: Indices, d: number): Record<string, IndiceClasse | null> {
  const valores: Record<string, IndiceClasse | null> = {};
  for (const m of indices.municipios) {
    const dia = m.dias.find((x) => x.d === d);
    valores[m.ibge] = dia ? { indice: dia.indice, classe: dia.classe } : null;
  }
  for (const ibge of indices.municipios_sem_dados) valores[ibge] = null;
  return valores;
}

/** Anéis do polígono em [lat, lon], a ordem do Leaflet. */
export const posicoes = (f: FeicaoMunicipio): LatLon[][] =>
  f.geometry.coordinates.map((anel) => anel.map(([lon, lat]) => [lat, lon]));

/** [[sul, oeste], [norte, leste]] dos municípios monitorados e dos pontos `extras`, para enquadrar o mapa. */
export function limites(feicoes: readonly FeicaoMunicipio[], extras: readonly LatLon[] = []): [LatLon, LatLon] {
  const pontos = [...feicoes.filter((f) => f.properties.monitorado).flatMap((f) => posicoes(f).flat()), ...extras];
  const lats = pontos.map(([lat]) => lat);
  const lons = pontos.map(([, lon]) => lon);
  return [
    [Math.min(...lats), Math.min(...lons)],
    [Math.max(...lats), Math.max(...lons)],
  ];
}

/** [antes, trecho achado, depois] no nome original, buscando sem acento; `null` se não há o que destacar. */
export function destacar(nome: string, termo: string): [string, string, string] | null {
  const q = normalizar(termo.trim());
  if (!q) return null;
  // Normaliza letra a letra para as posições do nome normalizado valerem no original.
  const letras = [...nome];
  const normalizadas = letras.map(normalizar);
  const k = normalizadas.join("").indexOf(q);
  if (k < 0) return null;
  let pos = 0;
  let inicio = -1;
  let fim = letras.length;
  normalizadas.forEach((l, i) => {
    if (pos === k && inicio < 0) inicio = i;
    pos += l.length;
    if (pos === k + q.length && fim === letras.length) fim = i + 1;
  });
  return [letras.slice(0, inicio).join(""), letras.slice(inicio, fim).join(""), letras.slice(fim).join("")];
}

/** "hoje" no dia-alvo; "+1d", "+2d"… nas previsões. */
export const rotuloDia = (d: number): string => (d === 0 ? "hoje" : `+${d}d`);

/** Dia seguinte (`passo` 1) ou anterior (−1), em ciclo entre `n` dias. */
export const passoDia = (d: number, passo: number, n: number): number => (((d + passo) % n) + n) % n;

export type IdCamada = "satelite" | "neutro" | "ruas" | "relevo";

export interface Camada {
  id: IdCamada;
  nome: string;
  url: string;
  atribuicao: string;
  subdominios?: string;
  zoomMax: number;
}

const OSM = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

/** Fundo inicial: o cinza claro não compete com as cores das classes (o protótipo abria no Satélite). */
export const CAMADA_NEUTRA: Camada = {
  // CARTO passou a exigir chave; o Light Gray Canvas da Esri é livre com atribuição.
  id: "neutro",
  nome: "Neutro",
  url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
  atribuicao: `&copy; Esri, HERE, Garmin, ${OSM}`,
  zoomMax: 16,
};

/** Provedores gratuitos de mapa de fundo, cada um com a atribuição exigida. */
export const CAMADAS: readonly Camada[] = [
  {
    id: "satelite",
    nome: "Satélite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    atribuicao: "Imagens &copy; Esri, Maxar, Earthstar Geographics",
    zoomMax: 18,
  },
  CAMADA_NEUTRA,
  {
    id: "ruas",
    nome: "Ruas",
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    atribuicao: OSM,
    zoomMax: 19,
  },
  {
    id: "relevo",
    nome: "Relevo",
    url: "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
    atribuicao: `${OSM}, SRTM | &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (CC-BY-SA)`,
    subdominios: "abc",
    zoomMax: 17,
  },
];

/** { ibge, nome } dos municípios monitorados, em ordem alfabética. */
export const municipiosMonitorados = (feicoes: readonly FeicaoMunicipio[]): { ibge: string; nome: string }[] =>
  feicoes
    .filter((f) => f.properties.monitorado)
    .map(({ properties: { ibge, nome } }) => ({ ibge, nome }))
    .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
