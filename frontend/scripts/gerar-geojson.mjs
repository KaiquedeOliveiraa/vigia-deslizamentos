// Gera src/data/municipios.geojson: os 6 municípios monitorados e os vizinhos que encostam neles,
// a partir da malha municipal do IBGE (mesma fonte do scripts/geo.py do protótipo).
// Uso: npm run gerar:geojson
import { writeFileSync } from "node:fs";

// Fixada num commit do tbrugz/geodata-br para a saída ser reprodutível (master em 2026-10-03).
const COMMIT = "c39dfb040bfd466fe2a476bafed00749c5c42f16";
const FONTE = `https://raw.githubusercontent.com/tbrugz/geodata-br/${COMMIT}/geojson/geojs-42-mun.json`;
const MONITORADOS = ["4219358", "4209151", "4219408", "4205100", "4214003", "4206900"];
const TOLERANCIA = 0.01; // graus; mesmo buffer do protótipo para decidir quem é vizinho
const SAIDA = new URL("../src/data/municipios.geojson", import.meta.url);

const resposta = await fetch(FONTE);
if (!resposta.ok) throw new Error(`Falha ao baixar a malha: HTTP ${resposta.status}`);
const malha = await resposta.json();

const aneis = (geometria) => (geometria.type === "Polygon" ? [geometria.coordinates] : geometria.coordinates).flat();
const vertices = (f) => aneis(f.geometry).flat();
const celula = (x, y) => `${Math.floor(x / TOLERANCIA)},${Math.floor(y / TOLERANCIA)}`;

const nucleo = malha.features.filter((f) => MONITORADOS.includes(f.properties.id));
if (nucleo.length !== MONITORADOS.length) throw new Error("Algum código IBGE monitorado não está na malha");

// Grade dos vértices do núcleo: um município é vizinho se algum vértice dele fica a até TOLERANCIA de um vértice do núcleo.
const grade = new Map();
for (const [x, y] of nucleo.flatMap(vertices)) {
  const k = celula(x, y);
  if (!grade.has(k)) grade.set(k, []);
  grade.get(k).push([x, y]);
}
const encosta = (f) =>
  vertices(f).some(([x, y]) => {
    const cx = Math.floor(x / TOLERANCIA), cy = Math.floor(y / TOLERANCIA);
    for (let i = -1; i <= 1; i++)
      for (let j = -1; j <= 1; j++)
        for (const [a, b] of grade.get(`${cx + i},${cy + j}`) ?? [])
          if (Math.hypot(a - x, b - y) <= TOLERANCIA) return true;
    return false;
  });

// Simplificação: 4 casas decimais (~11 m) e sem pontos repetidos em sequência.
const r4 = (n) => Math.round(n * 1e4) / 1e4;
const simplificarAnel = (anel) =>
  anel.map(([x, y]) => [r4(x), r4(y)]).filter((p, i, a) => i === 0 || p[0] !== a[i - 1][0] || p[1] !== a[i - 1][1]);
const simplificar = (g) =>
  g.type === "Polygon"
    ? { type: "Polygon", coordinates: g.coordinates.map(simplificarAnel) }
    : { type: "MultiPolygon", coordinates: g.coordinates.map((p) => p.map(simplificarAnel)) };

const features = malha.features
  .filter((f) => MONITORADOS.includes(f.properties.id) || encosta(f))
  .map((f) => ({
    type: "Feature",
    properties: { ibge: f.properties.id, nome: f.properties.name, monitorado: MONITORADOS.includes(f.properties.id) },
    geometry: simplificar(f.geometry),
  }))
  .sort((a, b) => Number(b.properties.monitorado) - Number(a.properties.monitorado) || a.properties.nome.localeCompare(b.properties.nome, "pt-BR"));

writeFileSync(SAIDA, JSON.stringify({ type: "FeatureCollection", features }) + "\n");
console.log(features.map((f) => `${f.properties.monitorado ? "*" : " "} ${f.properties.ibge} ${f.properties.nome}`).join("\n"));
