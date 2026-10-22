import { divIcon, polygon, type DivIcon, type Map as MapaL, type Marker as MarcadorL, type Polygon as PoligonoL } from "leaflet";
import { useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MapContainer, Marker, Polygon, TileLayer, Tooltip, useMap } from "react-leaflet";
import { tradutor, type T } from "../i18n";
import { CLASSES, infoClasse, SEM_DADOS } from "../lib/classes";
import { formatarIndice } from "../lib/formato";
import { CAMADA_NEUTRA, classesDoRotulo, limites, posicoes, pontoInterno, rotulosDeLonge, rotuloAria, type Camada, type FeicaoMunicipio, type LatLon, type Valor } from "../lib/mapa";
import { FEICOES } from "../lib/municipios";
import type { GrauSetor, Setor } from "../lib/setores";
import Camadas from "./Camadas";
import type { Pino, PropsMapa } from "./Mapa";
import SeloClasse from "./SeloClasse";

const COM_POSICOES = FEICOES.map((feicao) => ({ feicao, pos: posicoes(feicao) }));
const MONITORADOS = COM_POSICOES.filter((x) => x.feicao.properties.monitorado);
const VIZINHOS = COM_POSICOES.filter((x) => !x.feicao.properties.monitorado);
const LIMITES = limites(FEICOES);
const SEM_SETORES: Setor[] = [];
const PONTO_INTERNO = new Map(MONITORADOS.map(({ feicao }) => [feicao.properties.ibge, pontoInterno(feicao)]));

// Ícones em cache de módulo: o DOM dos marcadores não é recriado a cada render.
const ICONES_SETOR = new Map<string, DivIcon>();
function iconeSetor(grau: GrauSetor, sel: boolean): DivIcon {
  const chave = `${grau}|${sel}`;
  let ic = ICONES_SETOR.get(chave);
  if (!ic) {
    ic = divIcon({ className: `setor-marca ${grau}${sel ? " sel" : ""}`, html: "<i></i>", iconSize: [44, 44], iconAnchor: [22, 22] });
    ICONES_SETOR.set(chave, ic);
  }
  return ic;
}
function iconeConta(n: number): DivIcon {
  const chave = `conta|${n}`;
  let ic = ICONES_SETOR.get(chave);
  if (!ic) {
    ic = divIcon({ className: "setor-conta-icone", html: `<span class="setor-conta">${n}</span>`, iconSize: [44, 44], iconAnchor: [22, 22] });
    ICONES_SETOR.set(chave, ic);
  }
  return ic;
}

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
      <pattern id="hachura-setor" width={7} height={7} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line x1="0" y1="0" x2="0" y2="7" className="hatch-setor" />
      </pattern>
    </defs>,
    svg,
  );
}

interface PropsMunicipio {
  t: T;
  feicao: FeicaoMunicipio;
  /** Anéis do polígono, já em [lat, lon]. */
  pos: LatLon[][];
  valor: Valor;
  selecionado: boolean;
  onSelecionar?: (ibge: string) => void;
  rotuloMunicipio?: (ibge: string, nome: string) => string;
}

function Municipio({ t, feicao, pos, valor, selecionado, onSelecionar, rotuloMunicipio }: PropsMunicipio) {
  const { ibge, nome } = feicao.properties;
  const fundo = useRef<PoligonoL>(null);
  const hachura = useRef<PoligonoL>(null);
  const escolher = useRef(onSelecionar);
  escolher.current = onSelecionar;
  const n = valor ? valor.classe : null;

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
    const cor = n ? infoClasse(n).cor : valor === null ? SEM_DADOS.cor : "var(--surface-000)";
    el.style.fill = cor;
    // Nos fundos detalhados (Satélite, Ruas, Relevo) a cor vira contorno: mapa.css usa --cor-mun no stroke.
    // Sem classe, --surface-000 some sobre o Satélite no tema escuro; --muted contrasta nos dois temas.
    el.style.setProperty("--cor-mun", n || valor === null ? cor : "var(--muted)");
    h.style.fill = n && infoClasse(n).hachura ? `url(#${id(n)})` : "none";
    // Sem role (mapa só de contexto), aria-label num <path> é proibido.
    if (interativo) {
      el.setAttribute("aria-label", rotuloMunicipio ? rotuloMunicipio(ibge, nome) : rotuloAria(t, nome, valor));
      el.setAttribute("aria-pressed", String(selecionado));
    }
    el.classList.toggle("sel", selecionado);
    const rotulo = fundo.current?.getTooltip()?.getElement();
    const classes = classesDoRotulo(selecionado, valor);
    rotulo?.classList.toggle("sel", classes.sel);
    rotulo?.classList.toggle("alerta", classes.alerta);
    if (selecionado) {
      // bringToFront move o <path> no DOM e o foco do teclado (Enter no município) se perderia.
      const comFoco = document.activeElement === el;
      fundo.current?.bringToFront();
      hachura.current?.bringToFront();
      if (comFoco) el.focus();
    }
  }, [t, ibge, nome, valor, n, selecionado, interativo, rotuloMunicipio]);

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
            {nome} {valor && <b>{formatarIndice(valor.indice)}</b>}
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
  setores = SEM_SETORES,
  setorSelecionado = null,
  onSelecionarSetor,
  setoresIndividuais = true,
  onLonge,
  pinosVisiveis = true,
  rotuloMapa,
  rotuloMunicipio,
  ref,
}: PropsMapa) {
  const t = useMemo(() => tradutor(lang), [lang]);
  const [mapa, setMapa] = useState<MapaL | null>(null);
  const [fundo, setFundo] = useState<Camada>(CAMADA_NEUTRA);
  const [longeAtual, setLongeAtual] = useState(false);
  const comPinos = pinosVisiveis && pinos.length > 0;
  const temSetores = setores.length > 0;
  const setoresRef = useRef(setores);
  setoresRef.current = setores;
  const avisarLonge = useRef(onLonge);
  avisarLonge.current = onLonge;
  const contagens = useMemo(() => {
    const n = new Map<string, number>();
    for (const s of setores) n.set(s.ibge, (n.get(s.ibge) ?? 0) + 1);
    return [...n].flatMap(([ibge, total]) => {
      const pos = PONTO_INTERNO.get(ibge);
      return pos ? [{ ibge, n: total, pos }] : [];
    });
  }, [setores]);
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

  // "longe" = no enquadramento inicial (varia por tela) ou mais afastado: os nomes dos municípios se sobrepõem.
  useEffect(() => {
    if (!mapa) return;
    const zoomInicial = mapa.getZoom();
    const marcar = () => {
      const longe = rotulosDeLonge(mapa.getZoom(), zoomInicial);
      mapa.getContainer().classList.toggle("longe", longe);
      setLongeAtual(longe);
      avisarLonge.current?.(longe);
    };
    marcar();
    mapa.on("zoomend", marcar);
    return () => {
      mapa.off("zoomend", marcar);
    };
  }, [mapa]);

  // O Leaflet só remede o container no resize da janela; quando a página muda a altura do mapa
  // (faixa de aviso que aparece depois), o tamanho antigo faria o fitBounds passar da borda.
  useEffect(() => {
    if (!mapa) return;
    const observador = new ResizeObserver(() => mapa.invalidateSize());
    observador.observe(mapa.getContainer());
    return () => observador.disconnect();
  }, [mapa]);

  // Fora do Neutro, as cores ficam translúcidas para o fundo aparecer (mapa.css › [data-fundo]).
  useEffect(() => {
    const c = mapa?.getContainer();
    if (c) c.dataset.fundo = fundo.id;
  }, [mapa, fundo.id]);

  useEffect(() => {
    const c = mapa?.getContainer();
    c?.setAttribute("role", "group");
    // O Chrome põe o <svg> dos polígonos na ordem do Tab, sem nome nem foco visível.
    mapa?.getPanes().overlayPane.querySelector("svg")?.setAttribute("tabindex", "-1");
    c?.setAttribute(
      "aria-label",
      rotuloMapa ??
        (comPinos
          ? t("Mapa das estações de monitoramento. Use Tab para percorrer as estações e Enter para selecionar.")
          : t("Mapa dos municípios monitorados. Use Tab para percorrer os municípios e Enter para selecionar.")),
    );
  }, [mapa, t, comPinos, rotuloMapa]);

  // Marcadores e polígonos de setor ficam fora do Tab e do leitor de tela (o caminho é a lista do painel).
  // O município selecionado sobe ao topo do SVG (bringToFront) quando suas props mudam, e cobriria os setores:
  // por isso roda a cada render (querySelectorAll barato, idempotente).
  useEffect(() => {
    if (!mapa) return;
    for (const el of mapa.getContainer().querySelectorAll(".leaflet-marker-icon.setor-conta-icone, .leaflet-marker-icon.setor-marca")) {
      el.setAttribute("aria-hidden", "true");
      el.setAttribute("tabindex", "-1");
    }
    mapa.getPanes().overlayPane.querySelectorAll<SVGPathElement>("path.setor").forEach((el) => {
      el.setAttribute("aria-hidden", "true");
      el.setAttribute("tabindex", "-1");
      el.parentNode?.appendChild(el);
    });
  });

  // Município selecionado (sem setor selecionado): enquadra o município.
  useEffect(() => {
    if (!mapa || !temSetores || !selecionado || setorSelecionado) return;
    const f = MONITORADOS.find((x) => x.feicao.properties.ibge === selecionado)?.feicao;
    if (f) mapa.fitBounds(limites([f]), { padding: [24, 24] });
  }, [mapa, temSetores, selecionado, setorSelecionado]);

  // Volta à região (tinha município ou setor e não tem mais): reenquadra a região. Nunca na abertura.
  const tinhaSelecao = useRef(false);
  useEffect(() => {
    const tem = !!(selecionado || setorSelecionado);
    if (mapa && temSetores && tinhaSelecao.current && !tem) mapa.fitBounds(LIMITES, { padding: [24, 24] });
    tinhaSelecao.current = tem;
  }, [mapa, temSetores, selecionado, setorSelecionado]);

  // Setor selecionado: enquadra o setor, com zoom máximo limitado.
  useEffect(() => {
    const s = setoresRef.current.find((x) => x.id === setorSelecionado);
    if (mapa && s) mapa.fitBounds(polygon(s.aneis).getBounds(), { maxZoom: 16, padding: [32, 32] });
  // temSetores: com a seleção vinda da URL, os setores chegam depois; reenquadra quando carregam.
  }, [mapa, setorSelecionado, temSetores]);

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
        {VIZINHOS.map(({ feicao: f, pos }) => (
          <Polygon key={f.properties.ibge} positions={pos} className="ctx" interactive={false}>
            <Tooltip permanent direction="center" className="ctxl">
              {f.properties.nome}
            </Tooltip>
          </Polygon>
        ))}
        {MONITORADOS.map(({ feicao: f, pos }) => (
          <Municipio
            key={f.properties.ibge}
            t={t}
            feicao={f}
            pos={pos}
            valor={valores[f.properties.ibge]}
            selecionado={selecionado === f.properties.ibge}
            onSelecionar={onSelecionar}
            rotuloMunicipio={rotuloMunicipio}
          />
        ))}
        {pinosVisiveis &&
          pinos.map((p) => <Pin key={p.id} pino={p} selecionado={pinoSelecionado === p.id} onSelecionar={onSelecionarPino} />)}
        {temSetores &&
          !setoresIndividuais &&
          contagens.map(({ ibge, n, pos }) => (
            <Marker key={`c-${ibge}`} position={pos} keyboard={false} icon={iconeConta(n)} eventHandlers={{ click: () => onSelecionar?.(ibge) }} />
          ))}
        {temSetores &&
          setoresIndividuais &&
          setores.map((s) => {
            const sel = s.id === setorSelecionado;
            return longeAtual ? (
              <Marker
                key={s.id}
                position={[s.centro[1], s.centro[0]]}
                keyboard={false}
                zIndexOffset={sel ? 1000 : 0}
                icon={iconeSetor(s.grau, sel)}
                eventHandlers={{ click: () => onSelecionarSetor?.(s.id) }}
              />
            ) : (
              <Polygon
                key={`${s.id}${sel ? "-s" : ""}`}
                positions={s.aneis}
                className={`setor ${s.grau}${sel ? " sel" : ""}`}
                pathOptions={s.grau === "muito_alto" ? { fillColor: "url(#hachura-setor)" } : undefined}
                eventHandlers={{ click: () => onSelecionarSetor?.(s.id) }}
              />
            );
          })}
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
      <Camadas lang={lang} camada={fundo} aoMudar={setFundo} />
    </>
  );
}
