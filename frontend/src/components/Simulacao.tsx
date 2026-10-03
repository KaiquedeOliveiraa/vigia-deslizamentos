import "../styles/simulacao.css";
import { ArrowRight, CloudRain, Info, RotateCcw, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { tradutor, type T } from "../i18n";
import { classe, infoClasse, LIMIAR_ALERTA } from "../lib/classes";
import { carregar, lerIndices, type Resultado } from "../lib/dados";
import { formatarData, formatarHora, formatarIndice, formatarMm } from "../lib/formato";
import { valoresDoDia } from "../lib/mapa";
import { resumo } from "../lib/monitoramento";
import type { Idioma } from "../lib/preferencias";
import {
  avisoRegional,
  avisoSimulacao,
  CHUVA_MAX_MM,
  ESCALA_MAX,
  faixasEscala,
  limitarChuva,
  municipioDaBusca,
  posicaoEscala,
  simular,
  simularMunicipio,
  type Aviso,
  type Cenario,
  type Horas,
} from "../lib/simulacao";
import type { Indices } from "../lib/tipos";
import { anunciar } from "./anunciar";
import EstadoCarregamento from "./EstadoCarregamento";
import Legenda from "./Legenda";
import Mapa, { type MapaApi } from "./Mapa";
import SeloClasse from "./SeloClasse";

const PERIODOS: Horas[] = [24, 48, 72];
const ATALHOS: [string, number][] = [
  ["fraca", 10],
  ["moderada", 30],
  ["forte", 60],
  ["muito forte", 100],
  ["extrema", 180],
];
const MARCAS = [0, LIMIAR_ALERTA, 2.6, ESCALA_MAX];
const CHUVA_INICIAL = 40;

type Ver = "agora" | "simulado";

export default function Simulacao({ lang }: { lang: Idioma }) {
  const t = tradutor(lang);
  const [carga, setCarga] = useState<Resultado<Indices>>();
  const [ibge, setIbge] = useState("");
  const [horas, setHoras] = useState<Horas>(48);
  const [chuva, setChuva] = useState(CHUVA_INICIAL);
  const [regional, setRegional] = useState(false);
  const [cenario, setCenario] = useState<Cenario | null>(null);
  const [ver, setVer] = useState<Ver>("simulado");
  const mapa = useRef<MapaApi>(null);

  useEffect(() => {
    carregar("indices.json", lerIndices).then((r) => {
      setCarga(r);
      if (!r.ok) return;
      const inicial = municipioDaBusca(r.dados, location.search) ?? "";
      setIbge(inicial);
      setCenario({ ibge: inicial, chuva_mm: CHUVA_INICIAL, horas: 48, regional: false });
    });
  }, []);

  const titulo = t("E se chover…?");
  if (!carga?.ok)
    return (
      <div className="sim-carga">
        <h1 className="simh">{titulo}</h1>
        <EstadoCarregamento t={t} falhou={!!carga} />
      </div>
    );

  const indices = carga.dados;
  const municipios = indices.municipios
    .filter((m) => !indices.municipios_sem_dados.includes(m.ibge))
    .sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
  const nomes = Object.fromEntries(indices.municipios.map((m) => [m.ibge, m.nome]));
  const atuais = valoresDoDia(indices, 0);
  const simulados = cenario && simular(indices.municipios, cenario);
  const valores = simulados && ver === "simulado" ? { ...atuais, ...simulados } : atuais;
  const { emAlerta, total } = resumo(valores);
  const quando = [formatarData(indices.dia_alvo_d0, "dia"), formatarHora(indices.gerado_em)];

  function resultado(c: Cenario) {
    const m = municipios.find((x) => x.ibge === c.ibge);
    const d0 = m?.dias.find((x) => x.d === 0);
    const s = m && simularMunicipio(m, c.chuva_mm, c.horas);
    if (!m || !d0 || !s) return null;
    const avisos = [avisoSimulacao(t, { nome: m.nome, atual: d0.indice, simulado: s.indice, chuva_mm: c.chuva_mm, horas: c.horas })];
    if (c.regional) avisos.push(avisoRegional(t, simular(indices.municipios, c), nomes));
    return { m, d0, s, avisos };
  }

  const r = cenario && resultado(cenario);

  function rodar() {
    const c = { ibge, chuva_mm: limitarChuva(chuva), horas, regional };
    const novo = resultado(c);
    if (!novo) return;
    setCenario(c);
    setVer("simulado");
    mapa.current?.piscar(ibge);
    const { m, s, avisos } = novo;
    anunciar(
      [
        t("Resultado da simulação: {M}, índice {N}, classe {C}.", { M: m.nome, N: formatarIndice(s.indice), C: infoClasse(classe(s.indice)).nome }),
        ...avisos.flatMap((a) => [`${a.titulo}.`, a.texto]),
      ].join(" "),
    );
  }

  function voltar() {
    setCenario(null);
    setVer("agora");
    anunciar(t("Voltar à condição atual"));
  }

  function escolher(x: string) {
    if (municipios.some((m) => m.ibge === x)) setIbge(x);
  }

  return (
    <div className="sim">
      <aside className="side form" aria-label={t("Simulação de cenário")}>
        <div>
          <span className="lbl">{t("Simulação de cenário")}</span>
          <h1 className="simh">{titulo}</h1>
          <p className="intro">
            {t("Parte das condições de agora ({N}, {N}). Informe a chuva que você espera e veja como o índice do município reagiria.", { N: quando })}
          </p>
        </div>
        <div className="fld">
          <label className="lbl" htmlFor="sim-mun">
            {t("Município")}
          </label>
          <select id="sim-mun" value={ibge} onChange={(e) => setIbge(e.target.value)}>
            {municipios.map((m) => (
              <option key={m.ibge} value={m.ibge}>
                {m.nome}
              </option>
            ))}
          </select>
        </div>
        <div className="fld">
          <span className="lbl" id="sim-per">
            {t("Período")}
          </span>
          <div className="seg" role="group" aria-labelledby="sim-per">
            {PERIODOS.map((h) => (
              <button key={h} type="button" aria-pressed={h === horas} onClick={() => setHoras(h)}>
                {t("próximas {N}", { N: `${h}h` })}
              </button>
            ))}
          </div>
        </div>
        <div className="fld">
          <label className="lbl" htmlFor="sim-mm">
            {t("Chuva esperada no período")}
          </label>
          <div className="row">
            <input
              type="range"
              min={0}
              max={CHUVA_MAX_MM}
              step={1}
              value={chuva}
              aria-label={t("Chuva em mm")}
              onChange={(e) => setChuva(Number(e.target.value))}
            />
            <input
              id="sim-mm"
              type="number"
              min={0}
              max={CHUVA_MAX_MM}
              value={chuva}
              onChange={(e) => setChuva(limitarChuva(Number(e.target.value) || 0))}
            />
            <span className="unit">mm</span>
          </div>
          <div className="presets">
            {ATALHOS.map(([nome, mm]) => (
              <button key={mm} type="button" onClick={() => setChuva(mm)}>
                {t(nome)} <b>{mm}</b>
              </button>
            ))}
          </div>
        </div>
        <label className="chk">
          <input type="checkbox" checked={regional} onChange={(e) => setRegional(e.target.checked)} />
          {t("Aplicar a mesma chuva aos {N} municípios (chuva regional)", { N: String(municipios.length) })}
        </label>
        <div className="go">
          <button type="button" className="btn pri" onClick={rodar}>
            <CloudRain aria-hidden="true" />
            {t("Simular")}
          </button>
          <button type="button" className="btn" aria-label={t("Voltar à condição atual")} title={t("Voltar à condição atual")} onClick={voltar}>
            <RotateCcw aria-hidden="true" />
          </button>
        </div>
        {r && <Resultado t={t} atual={r.d0.indice} simulado={r.s.indice} efr={r.d0.efr_mm} efrSimulada={r.s.chuva_efetiva_mm} limiar={r.m.limiar_mm} />}
        <p className="disc">
          {t("Simulação com a mesma equação do índice: (chuva efetiva + chuva informada) ÷ limiar. Não altera os dados reais e não dispara alertas.")}{" "}
          {t("Sistema de")} <b>{t("apoio à decisão")}</b>
          {t(", de caráter acadêmico. Não constitui alerta oficial e não substitui o Cemaden nem a Defesa Civil.")}
        </p>
      </aside>
      <Mapa ref={mapa} lang={lang} valores={valores} selecionado={ibge} onSelecionar={escolher} camadas={false}>
        <div className="maphd">
          {r && (
            <div className="avisos">
              {r.avisos.map((a) => (
                <CaixaAviso key={a.titulo} {...a} />
              ))}
            </div>
          )}
          <div className="seg" role="group" aria-label={t("Mostrar no mapa")}>
            <button type="button" aria-pressed={ver === "agora"} onClick={() => setVer("agora")}>
              {t("Agora")}
            </button>
            <button type="button" aria-pressed={ver === "simulado"} disabled={!cenario} onClick={() => setVer("simulado")}>
              {t("Simulado")}
            </button>
          </div>
        </div>
        <Legenda lang={lang} />
        <p className="float snap">
          <span className="lbl">{simulados && ver === "simulado" ? t("Cenário simulado") : t("Condição atual · {N} {N}", { N: quando })}</span>
          {t("{N} de {N} municípios em alerta", { N: [String(emAlerta), String(total)] })}
        </p>
      </Mapa>
    </div>
  );
}

function CaixaAviso({ tipo, titulo, texto }: Aviso) {
  return (
    <div className={`aviso ${tipo}`}>
      {tipo === "ok" ? <Info aria-hidden="true" /> : <TriangleAlert aria-hidden="true" />}
      <div>
        <strong>{titulo}</strong>
        {texto}
      </div>
    </div>
  );
}

interface PropsResultado {
  t: T;
  atual: number;
  simulado: number;
  efr: number;
  efrSimulada: number;
  limiar: number;
}

function Resultado({ t, atual, simulado, efr, efrSimulada, limiar }: PropsResultado) {
  return (
    <section className="res" aria-label={t("Resultado")}>
      <div className="cmp">
        <Valor t={t} rotulo={t("Agora")} indice={atual} />
        <ArrowRight className="arr" aria-hidden="true" />
        <Valor t={t} rotulo={t("Simulado")} indice={simulado} />
      </div>
      <div className="scalew" aria-hidden="true">
        <span className="mk s" style={{ left: `${posicaoEscala(simulado)}%` }}>
          {t("simulado")}
        </span>
        <div className="scale">
          {faixasEscala().map((f) => (
            <i key={f.numero} style={{ flexBasis: `${f.largura}%`, background: `var(--c${f.numero})` }} />
          ))}
        </div>
        <span className="mk a" style={{ left: `${posicaoEscala(atual)}%` }}>
          {t("agora")}
        </span>
        <div className="ends">
          {MARCAS.map((v) => (
            <span key={v} style={{ left: `${posicaoEscala(v)}%` }}>
              {v === LIMIAR_ALERTA ? t("{N} alerta", { N: formatarIndice(v) }) : v ? formatarIndice(v) : "0"}
            </span>
          ))}
        </div>
      </div>
      <dl className="detail">
        <div>
          <dt>{t("Chuva efetiva atual")}</dt>
          <dd className="num">{formatarMm(efr)} mm</dd>
        </div>
        <div>
          <dt>{t("Chuva efetiva simulada")}</dt>
          <dd className="num">{formatarMm(efrSimulada)} mm</dd>
        </div>
        <div>
          <dt>{t("Limiar crítico")}</dt>
          <dd className="num">{formatarMm(limiar)} mm</dd>
        </div>
      </dl>
    </section>
  );
}

function Valor({ t, rotulo, indice }: { t: T; rotulo: string; indice: number }) {
  const n = classe(indice);
  return (
    <div className="c">
      <span className="lbl">{rotulo}</span>
      <b className="num">{formatarIndice(indice)}</b>
      <span className="cls">
        <SeloClasse classe={n} />
        {t(infoClasse(n).nome)}
      </span>
    </div>
  );
}
