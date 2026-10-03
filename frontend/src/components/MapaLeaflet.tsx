import { divIcon, type Map as MapaL, type Marker as MarcadorL, type Polygon as PoligonoL } from "leaflet";
import { useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MapContainer, Marker, Polygon, TileLayer, Tooltip, useMap } from "react-leaflet";
import geojson from "../data/municipios.geojson?raw";
import { tradutor, type T } from "../i18n";
import { classe, CLASSES, infoClasse, SEM_DADOS } from "../lib/classes";
import { formatarIndice } from "../lib/formato";
import { CAMADAS, limites, posicoes, rotuloAria, type FeicaoMunicipio, type IdCamada, type Valor } from "../lib/mapa";
import Camadas from "./Camadas";
import type { Pino, PropsMapa } from "./Mapa";
import SeloClasse from "./SeloClasse";

const FEICOES = JSON.parse(geojson).features as FeicaoMunicipio[];
const MONITORADOS = FEICOES.filter((f) => f.properties.monitorado);
const VIZINHOS = FEICOES.filter((f) => !f.properties.monitorado);
const LIMITES = limites(FEICOES);
const POSICOES = new Map(FEICOES.map((f) => [f.properties.ibge, posicoes(f)]));

const id = (n: number) => `hachura-${n}`;

// Gota azul-marinho com miolo branco (protótipo: est.js); a ponta fica na coordenada da estação.
const ICONE_PINO = divIcon({
  className: "pin",
  html: '<svg viewBox="-20 -54 40 56" width="28" height="39" aria-hidden="true"><path d="M0 0c-4-10-18-20-18-34a18 18 0 0 1 36 0c0 14-14 24-18 34z"/><circle cy="-34" r="6.5"/></svg>',
  iconSize: [28, 39],
  iconAnchor: [14, 38],
  tooltipAnchor: [0, -24],
});

/** Um <pattern> por classe com hachura, dentro do SVG do Leaflet (protótipo: #pat4…#pat7). */
function Hachuras() {
  const mapa = useMap();
  const [svg, setSvg] = useState<SVGSVGElement | null>(null);
  // Roda depois dos polígonos (irmãos anteriores): o SVG do Leaflet já existe.
  useEffect(() => setSvg(mapa.getPanes().overlayPane.querySelector("svg")), [mapa]);
  if (!svg) return null;
  return createPortal(
    <defs>
      {CLASSES.map(({ numero, hachura: h }) =>
        h ? (
          <pattern key={numero} id={id(numero)} width={h.espacamento} height={h.espacamento} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2={h.espacamento} className="hatch" />
            {h.cruzada && <line x1="0" y1="0" x2={h.espacamento} y2="0" className="hatch" />}
          </pattern>
        ) : null,
      )}
    </defs>,
    svg,
  );
}

interface PropsMunicipio {
  t: T;
  feicao: FeicaoMunicipio;
  valor: Valor;
  selecionado: boolean;
  onSelecionar?: (ibge: string) => void;
}

function Municipio({ t, feicao, valor, selecionado, onSelecionar }: PropsMunicipio) {
  const { ibge, nome } = feicao.properties;
  const fundo = useRef<PoligonoL>(null);
  const hachura = useRef<PoligonoL>(null);
  const escolher = useRef(onSelecionar);
  escolher.current = onSelecionar;
  const n = typeof valor === "number" ? classe(valor) : null;

  const interativo = onSelecionar !== undefined;

  // Polígono focável por Tab e selecionável por Enter/Espaço (só quando há seleção de município).
  useEffect(() => {
    const el = fundo.current?.getElement();
    if (!el || !interativo) return;
    el.setAttribute("tabindex", "0");
    el.setAttribute("role", "button");
    el.setAttribute("data-ibge", ibge);
    const tecla = (e: Event) => {
      const { key } = e as KeyboardEvent;
      if (key !== "Enter" && key !== " ") return;
      e.preventDefault();
      escolher.current?.(ibge);
    };
    el.addEventListener("keydown", tecla);
    return () => el.removeEventListener("keydown", tecla);
  }, [ibge, interativo]);

  // className e interactive só valem na criação do polígono. Cor, hachura e estado vão por estilo inline:
  // atributos SVG não aceitam var(--cN), e assim a cor anima por CSS.
  useEffect(() => {
    const el = fundo.current?.getElement() as SVGPathElement | undefined;
    const h = hachura.current?.getElement() as SVGPathElement | undefined;
    if (!el || !h) return;
    el.style.fill = n ? infoClasse(n).cor : valor === null ? SEM_DADOS.cor : "var(--surface-000)";
    h.style.fill = n && infoClasse(n).hachura ? `url(#${id(n)})` : "none";
    // Sem role (mapa só de contexto), aria-label num <path> é proibido.
    if (interativo) {
      el.setAttribute("aria-label", rotuloAria(t, nome, valor));
      el.setAttribute("aria-pressed", String(selecionado));
    }
    el.classList.toggle("sel", selecionado);
    if (selecionado) {
      fundo.current?.bringToFront();
      hachura.current?.bringToFront();
    }
  }, [t, nome, valor, n, selecionado, interativo]);

  const pos = POSICOES.get(ibge)!;
  return (
    <>
      <Polygon
        ref={fundo}
        positions={pos}
        className="mun"
        interactive={interativo}
        pathOptions={{ fillOpacity: 1 }}
        eventHandlers={{ click: () => escolher.current?.(ibge) }}
      >
        <Tooltip permanent direction="center" className="mlabel">
          {valor !== undefined && <SeloClasse classe={n} />}
          <span>
            {nome} {typeof valor === "number" && <b>{formatarIndice(valor)}</b>}
            {valor !== undefined && <small>{t(n ? infoClasse(n).nome : SEM_DADOS.nome)}</small>}
          </span>
        </Tooltip>
      </Polygon>
      <Polygon ref={hachura} positions={pos} className="munp" interactive={false} pathOptions={{ stroke: false, fillOpacity: 1 }} />
    </>
  );
}

interface PropsPin {
  pino: Pino;
  selecionado: boolean;
  onSelecionar?: (id: string) => void;
}

/** Pin focável por Tab; clique, Enter ou Espaço selecionam. */
function Pin({ pino, selecionado, onSelecionar }: PropsPin) {
  const marcador = useRef<MarcadorL>(null);
  const escolher = useRef(onSelecionar);
  escolher.current = onSelecionar;

  // O Leaflet torna o pin focável (keyboard: true); Enter/Espaço selecionam.
  useEffect(() => {
    const el = marcador.current?.getElement();
    if (!el) return;
    const tecla = (e: KeyboardEvent) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      escolher.current?.(pino.id);
    };
    el.addEventListener("keydown", tecla);
    return () => el.removeEventListener("keydown", tecla);
  }, [pino.id]);

  useEffect(() => {
    const el = marcador.current?.getElement();
    if (!el) return;
    el.setAttribute("aria-label", pino.rotulo);
    el.setAttribute("aria-pressed", String(selecionado));
    el.classList.toggle("sel", selecionado);
  }, [pino.rotulo, selecionado]);

  return (
    <Marker
      ref={marcador}
      position={[pino.lat, pino.lon]}
      icon={ICONE_PINO}
      zIndexOffset={selecionado ? 1000 : 0}
      eventHandlers={{ click: () => escolher.current?.(pino.id) }}
    >
      {selecionado && (
        <Tooltip permanent direction="auto" offset={[16, 0]} className="balao">
          {pino.balao}
        </Tooltip>
      )}
    </Marker>
  );
}

export default function MapaLeaflet({
  lang,
  valores,
  selecionado = null,
  onSelecionar,
  pinos = [],
  pinoSelecionado = null,
  onSelecionarPino,
  camadas = true,
  ref,
}: PropsMapa) {
  const t = useMemo(() => tradutor(lang), [lang]);
  const [mapa, setMapa] = useState<MapaL | null>(null);
  // Neutro: o fundo claro não compete com as cores das classes (o protótipo abria no Satélite).
  const [camada, setCamada] = useState<IdCamada>("neutro");
  const fundo = CAMADAS.find((c) => c.id === camada)!;
  const comPinos = pinos.length > 0;
  // Só vale na criação do mapa: quem passa pinos já os tem ao montar o Mapa.
  const enquadramento = comPinos ? limites(FEICOES, pinos.map((p) => [p.lat, p.lon])) : LIMITES;

  useImperativeHandle(ref, () => ({
    piscar(ibge) {
      const el = mapa?.getPanes().overlayPane.querySelector(`[data-ibge="${ibge}"]`);
      if (!el) return;
      el.classList.remove("pulse");
      void el.getBoundingClientRect();
      el.classList.add("pulse");
    },
  }));

  // "longe" abaixo do zoom 8,5: com o mapa afastado (celular), os nomes dos municípios se sobrepõem.
  useEffect(() => {
    if (!mapa) return;
    const marcar = () => mapa.getContainer().classList.toggle("longe", mapa.getZoom() < 8.5);
    marcar();
    mapa.on("zoomend", marcar);
    return () => {
      mapa.off("zoomend", marcar);
    };
  }, [mapa]);

  useEffect(() => {
    const c = mapa?.getContainer();
    c?.setAttribute("role", "group");
    // O Chrome põe o <svg> dos polígonos na ordem do Tab, sem nome nem foco visível.
    mapa?.getPanes().overlayPane.querySelector("svg")?.setAttribute("tabindex", "-1");
    c?.setAttribute(
      "aria-label",
      comPinos
        ? t("Mapa das estações de monitoramento. Use Tab para percorrer as estações e Enter para selecionar.")
        : t("Mapa dos municípios monitorados. Use Tab para percorrer os municípios e Enter para selecionar."),
    );
  }, [mapa, t, comPinos]);

  return (
    <>
      <MapContainer ref={setMapa} fadeAnimation={false} bounds={enquadramento} boundsOptions={{ padding: comPinos ? [48, 48] : [24, 24] }} zoomSnap={0.25} zoomControl={false} className="mapa">
        <TileLayer
          key={fundo.id}
          url={fundo.url}
          attribution={fundo.atribuicao}
          maxZoom={fundo.zoomMax}
          {...(fundo.subdominios && { subdomains: fundo.subdominios })}
        />
        {VIZINHOS.map((f) => (
          <Polygon key={f.properties.ibge} positions={POSICOES.get(f.properties.ibge)!} className="ctx" interactive={false}>
            <Tooltip permanent direction="center" className="ctxl">
              {f.properties.nome}
            </Tooltip>
          </Polygon>
        ))}
        {MONITORADOS.map((f) => (
          <Municipio
            key={f.properties.ibge}
            t={t}
            feicao={f}
            valor={valores[f.properties.ibge]}
            selecionado={selecionado === f.properties.ibge}
            onSelecionar={onSelecionar}
          />
        ))}
        {pinos.map((p) => (
          <Pin key={p.id} pino={p} selecionado={pinoSelecionado === p.id} onSelecionar={onSelecionarPino} />
        ))}
        <Hachuras />
      </MapContainer>
      <div className="float zoom">
        <button type="button" aria-label={t("Aproximar")} onClick={() => mapa?.zoomIn()}>
          +
        </button>
        <button type="button" aria-label={t("Afastar")} onClick={() => mapa?.zoomOut()}>
          −
        </button>
      </div>
      {camadas && <Camadas lang={lang} camada={camada} aoMudar={setCamada} />}
    </>
  );
}
