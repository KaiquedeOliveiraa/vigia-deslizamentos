import { useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { T } from "../i18n";
import { infoClasse, LIMIAR_ALERTA } from "../lib/classes";
import { formatarData, formatarIndice, formatarMm, formatarNumero, formatarVariacao } from "../lib/formato";
import {
  coordenadas,
  escala,
  faixaDosDemais,
  faixasClasse,
  focoAposSeta,
  indiceMaisProximo,
  marcaClasse,
  marcasEvolucao,
  maxEvolucao,
  maxPluviometro,
  passoDaSeta,
  rotulosEixo,
  serieMunicipio,
  variacoesDiarias,
  type Area,
} from "../lib/graficos";
import type { Idioma } from "../lib/preferencias";
import { sentido } from "../lib/texto";
import type { ChuvaAcum, Municipio } from "../lib/tipos";

const AREA: Area = { largura: 760, altura: 300, esq: 44, dir: 16, topo: 18, base: 34 };
const AREA_MINI: Area = { largura: 110, altura: 26, esq: 3, dir: 3, topo: 3, base: 3 };
const CLASSE_SENTIDO = { subindo: "up", descendo: "dn", estável: "" } as const;

/** Acima disto o gráfico não desenha um círculo por dia nem as marcas de mudança de classe. */
const DIAS_DETALHE = 31;

/** "out/25": mês abreviado no idioma (sem o ponto final de "oct.") e ano de 2 dígitos. */
function mesAno(dia: string, lang: Idioma): string {
  const mes = new Intl.DateTimeFormat(lang, { month: "short", timeZone: "UTC" }).format(new Date(`${dia}T00:00:00Z`)).replace(/\.$/, "");
  return `${mes}/${dia.slice(2, 4)}`;
}

const pontos = (c: { x: number; y: number }[]) => c.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

interface PropsEvolucao {
  t: T;
  municipios: Municipio[];
  destaque: Municipio;
  /** Dias do eixo X, do mais antigo ao D0. */
  eixo: string[];
  /** Primeiro dia publicado pelo sistema (depois dos reconstruídos), ou null sem histórico reconstruído. */
  inicioReal: string | null;
  lang: Idioma;
  aoSelecionar: (ibge: string) => void;
}

/** Evolução do índice (RF06): faixas das classes, linha de alerta, faixa mínimo–máximo dos demais municípios e o destaque.
 * Linha-guia com o valor do destaque e da faixa no dia apontado (mouse, ou ←/→ com o gráfico em foco). */
export function Evolucao({ t, municipios, destaque, eixo, inicioReal, lang, aoSelecionar }: PropsEvolucao) {
  const painel = useRef<HTMLDivElement>(null);
  const [focoBruto, setFoco] = useState<number | null>(null);
  // O eixo pode encolher (troca de período) com o foco ainda no índice antigo.
  const foco = focoBruto !== null && focoBruto < eixo.length ? focoBruto : null;
  const { ibge } = destaque;
  const { esq, dir, largura, altura, topo, base } = AREA;
  const util = altura - topo - base;
  // Séries, escala e faixa só mudam com municípios, destaque ou eixo (366 dias × 27 municípios): não refazer a cada foco.
  const { max, coords, deltas, xs, faixas, faixa, trechos, recs } = useMemo(() => {
    const max = maxEvolucao(municipios.flatMap((m) => serieMunicipio(m, eixo).map((p) => p.indice)));
    const coords = coordenadas(serieMunicipio(destaque, eixo), eixo, max, AREA);
    const xs = coordenadas(eixo.map((dia_alvo) => ({ dia_alvo, indice: 0 })), eixo, max, AREA).map((c) => c.x);
    const faixa = faixaDosDemais(municipios, ibge, eixo);
    // Trechos contínuos de dias: um polígono por trecho de faixa (contorno de cima, depois o de baixo de volta).
    const trechos: number[][] = [];
    faixa.forEach((f, i) => {
      if (!f) return;
      const ultimo = trechos.at(-1);
      if (ultimo && ultimo.at(-1) === i - 1) ultimo.push(i);
      else trechos.push([i]);
    });
    // Idem para os dias reconstruídos do destaque: [primeiro, último] índice no eixo.
    const reconstruidos = new Set(coords.filter((c) => c.ponto.reconstruido).map((c) => c.ponto.dia_alvo));
    const recs: [number, number][] = [];
    eixo.forEach((dia, i) => {
      if (!reconstruidos.has(dia)) return;
      const ultimo = recs.at(-1);
      if (ultimo && ultimo[1] === i - 1) ultimo[1] = i;
      else recs.push([i, i]);
    });
    return { max, coords, deltas: variacoesDiarias(coords.map((c) => c.ponto)), xs, faixas: faixasClasse(max), faixa, trechos, recs };
  }, [municipios, destaque, ibge, eixo]);
  const y = (v: number) => topo + util - escala(v, max, util);
  const detalhe = eixo.length <= DIAS_DETALHE;
  const meio = xs.length > 1 ? (xs[1] - xs[0]) / 2 : 0;
  const iInicio = inicioReal ? eixo.indexOf(inicioReal) : -1;
  const xInicio = iInicio < 0 ? 0 : iInicio > 0 ? xs[iInicio] - meio : xs[0];
  const rotulosX = useMemo(() => rotulosEixo(eixo, (dia) => mesAno(dia, lang)), [eixo, lang]);
  const rotulo = t("Evolução do índice de risco em {N} dias — {M}", { N: String(eixo.length), M: destaque.nome });
  const ultimo = coords.at(-1);
  const deltaUltimo = deltas.at(-1) ?? null;
  const area = coords.length > 1 ? `${coords[0].x},${y(0)} ${pontos(coords)} ${coords.at(-1)!.x},${y(0)}` : "";

  // No celular o gráfico rola na horizontal: abre no fim, com o D0 à vista, e não nos dias mais antigos.
  useLayoutEffect(() => {
    const el = painel.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, [eixo.length]);

  // Dia mais próximo do ponteiro: o leitor mira uma data, não uma linha de 2px.
  function apontar(e: PointerEvent<SVGRectElement>) {
    const caixa = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const x = ((e.clientX - caixa.left) / caixa.width) * largura;
    setFoco(indiceMaisProximo(xs, x));
  }

  function tecladoGrafico(e: KeyboardEvent) {
    if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      setFoco(e.key === "Home" ? 0 : eixo.length - 1);
      return;
    }
    const passo = passoDaSeta(e.key);
    if (!passo) return;
    e.preventDefault();
    setFoco((f) => focoAposSeta(f, passo, eixo.length));
  }

  const diaFoco = foco === null ? null : eixo[foco];
  const iFoco = coords.findIndex((c) => c.ponto.dia_alvo === diaFoco);
  const pontoFoco = iFoco < 0 ? null : coords[iFoco].ponto;
  const deltaFoco = iFoco < 0 ? null : deltas[iFoco];
  const leitura = pontoFoco ? [{ m: destaque, p: pontoFoco }] : [];
  const ressalva = t("estimativa reconstruída, tende a subestimar picos");

  return (
    <div className="evo">
      <label className="pick">
        <span className="sr-only">{t("Município")}</span>
        <select value={ibge} onChange={(e) => aoSelecionar(e.target.value)}>
          {municipios.map((m) => (
            <option key={m.ibge} value={m.ibge}>
              {m.nome}
            </option>
          ))}
        </select>
      </label>
      <div
        ref={painel}
        className="evo-svg"
        role="group"
        aria-label={rotulo}
        tabIndex={0}
        onKeyDown={tecladoGrafico}
        onBlur={() => setFoco(null)}
      >
        <div className="evo-plot">
        <svg viewBox={`0 0 ${largura} ${altura}`} role="img" aria-label={rotulo}>
          {faixas.map((f) => (
            <rect key={f.numero} className="band" x={esq} width={largura - esq - dir} y={y(f.ate)} height={y(f.de) - y(f.ate)} style={{ fill: `var(--c${f.numero})` }} />
          ))}
          {recs.map(([a, b]) => {
            const x0 = Math.max(esq, xs[a] - meio);
            return <rect key={a} className="rec" x={x0} width={Math.min(largura - dir, xs[b] + meio) - x0} y={topo} height={util} />;
          })}
          {marcasEvolucao(max).map((v) => (
            <g key={v}>
              <line className="grid" x1={esq} x2={largura - dir} y1={y(v)} y2={y(v)} />
              <text className="ax" x={esq - 8} y={y(v) + 4} textAnchor="end">
                {formatarIndice(v)}
              </text>
            </g>
          ))}
          <line className="alerta" x1={esq} x2={largura - dir} y1={y(LIMIAR_ALERTA)} y2={y(LIMIAR_ALERTA)} />
          <text className="alertal" x={largura - dir - 4} y={y(LIMIAR_ALERTA) - 6} textAnchor="end">
            {t("ALERTA {N}", { N: formatarIndice(LIMIAR_ALERTA) })}
          </text>
          {iInicio >= 0 && (
            <>
              <line className="inicio" x1={xInicio} x2={xInicio} y1={topo} y2={y(0)} />
              <text className="inicio-l" x={xInicio + (xInicio > largura * 0.7 ? -4 : 4)} y={topo + 10} textAnchor={xInicio > largura * 0.7 ? "end" : "start"}>
                {t("início do sistema")}
              </text>
            </>
          )}
          {rotulosX.map(({ i, texto }) => (
            <text key={i} className={i === foco ? "ax on" : "ax"} x={xs[i]} y={altura - 10} textAnchor="middle">
              {texto}
            </text>
          ))}
          {foco !== null && !rotulosX.some((r) => r.i === foco) && (
            <text className="ax on" x={xs[foco]} y={altura - 10} textAnchor="middle">
              {formatarData(eixo[foco], "dia")}
            </text>
          )}
          {trechos.map((tr) => (
            <polygon
              key={tr[0]}
              className="faixa"
              points={[...tr.map((i) => `${xs[i]},${y(faixa[i]!.max)}`), ...[...tr].reverse().map((i) => `${xs[i]},${y(faixa[i]!.min)}`)].join(" ")}
            />
          ))}
          {area && <polygon className="area" points={area} />}
          <polyline className="main" points={pontos(coords)} />
          {foco !== null && <line className="guia" x1={xs[foco]} x2={xs[foco]} y1={topo} y2={y(0)} />}
          {coords.map((c, i) => {
            const n = c.ponto.classe;
            // Período longo: só o ponto em foco e o último levam círculo.
            if (!detalhe && c.ponto.dia_alvo !== diaFoco && i !== coords.length - 1) return null;
            // Variação só existe quando o ponto anterior é o dia anterior.
            const marca = !detalhe || deltas[i] === null ? null : marcaClasse(coords[i - 1].ponto.classe, n);
            return (
              <g key={c.ponto.dia_alvo}>
                <circle className={c.ponto.dia_alvo === diaFoco ? "pt on" : "pt"} cx={c.x} cy={c.y} r="5" style={{ fill: `var(--c${n})` }} />
                {marca && (
                  <text className="cl" x={c.x} y={c.y + 22}>
                    {t(marca)}
                  </text>
                )}
              </g>
            );
          })}
          {ultimo && (
            <text className="fim" x={ultimo.x - 10} y={ultimo.y - 12} textAnchor="end">
              {formatarIndice(ultimo.ponto.indice)}
              {deltaUltimo !== null && (
                <tspan className={`dl ${CLASSE_SENTIDO[sentido(deltaUltimo)]}`} dx="6">
                  {formatarVariacao(deltaUltimo)}
                </tspan>
              )}
            </text>
          )}
          <rect className="mira" x={esq} y={topo} width={largura - esq - dir} height={util} onPointerMove={apontar} onPointerLeave={() => setFoco(null)} />
        </svg>
        {diaFoco !== null && foco !== null && (
          <div className={xs[foco] > largura * 0.6 ? "dica esq" : "dica"} style={{ left: `${(xs[foco] / largura) * 100}%` }}>
            <span className="lbl">{formatarData(diaFoco)}</span>
            {leitura.length === 0 && !(foco !== null && faixa[foco]) && <span className="vazio">{t("sem dados")}</span>}
            <ul>
              {leitura.map(({ m, p }) => (
                <li key={m.ibge} className="eu">
                  <i aria-hidden="true" />
                  <b className="num">{formatarIndice(p.indice)}</b>
                  <span>
                    {m.nome}
                    {deltaFoco != null && <em className={`dl ${CLASSE_SENTIDO[sentido(deltaFoco)]}`}> {formatarVariacao(deltaFoco)}</em>}
                    <small>
                      {t(infoClasse(p.classe).nome)}
                      {p.reconstruido && ` · ${ressalva}`}
                    </small>
                  </span>
                </li>
              ))}
              {foco !== null && faixa[foco] && (
                <li>
                  <i aria-hidden="true" />
                  <b className="num">
                    {formatarIndice(faixa[foco]!.min)}–{formatarIndice(faixa[foco]!.max)}
                  </b>
                  <span>{t("demais municípios")}</span>
                </li>
              )}
            </ul>
          </div>
        )}
        </div>
        {/* Leitura do dia apontado para leitor de tela (←/→ com o gráfico em foco). */}
        <p className="sr-only" aria-live="polite">
          {pontoFoco ? `${formatarData(pontoFoco.dia_alvo)} · ${t("{M}: índice {N}, classe {C}", { M: destaque.nome, N: formatarIndice(pontoFoco.indice), C: infoClasse(pontoFoco.classe).nome })}${pontoFoco.reconstruido ? `. ${ressalva}` : ""}` : ""}
        </p>
        {/* Só o município em destaque: a faixa dos demais é visual (ver a legenda). */}
        {/* Dentro de uma div: <table> ignora a altura de 1px do sr-only. */}
        <div className="sr-only">
          <table>
            <caption>{rotulo}</caption>
            <thead>
              <tr>
                <th scope="col">{t("Data")}</th>
                <th scope="col">{t("Índice")}</th>
                <th scope="col">{t("Classe")}</th>
              </tr>
            </thead>
            <tbody>
              {coords.map(({ ponto }) => (
                <tr key={ponto.dia_alvo}>
                  <td>{formatarData(ponto.dia_alvo)}</td>
                  <td>{formatarIndice(ponto.indice)}</td>
                  <td>
                    {t(infoClasse(ponto.classe).nome)}
                    {ponto.reconstruido && `. ${ressalva}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

/** Minigráfico da tabela: série do período com a linha de alerta. Decorativo: os valores estão nas outras colunas. */
export function Minigrafico({ municipio, eixo }: { municipio: Municipio; eixo: string[] }) {
  const serie = serieMunicipio(municipio, eixo);
  const max = maxEvolucao(serie.map((p) => p.indice));
  const coords = coordenadas(serie, eixo, max, AREA_MINI);
  const { largura, altura, topo, base } = AREA_MINI;
  const chao = altura - base;
  const yAlerta = chao - escala(LIMIAR_ALERTA, max, altura - topo - base);
  const hoje = coords.at(-1);
  // Série discreta com área; só o ponto de hoje leva a cor da classe.
  return (
    <svg className="spark" width={largura} height={altura} viewBox={`0 0 ${largura} ${altura}`} aria-hidden="true">
      <line className="ref" x1="0" x2={largura} y1={yAlerta} y2={yAlerta} />
      {coords.length > 1 && <polygon className="area" points={`${coords[0].x},${chao} ${pontos(coords)} ${coords.at(-1)!.x},${chao}`} />}
      <polyline className="linha" points={pontos(coords)} />
      {hoje && <circle className="hoje" cx={hoje.x} cy={hoje.y} r="3.5" style={{ fill: `var(--c${hoje.ponto.classe})` }} />}
    </svg>
  );
}

const JANELAS: (keyof ChuvaAcum)[] = ["24h", "48h", "72h", "96h"];
const MARCAS = [25, 50, 75];

/** Altura em CSS dentro do tubo (3 px de folga em cima e embaixo). */
const alturaTubo = (fracao: number) => `calc(3px + (100% - 6px) * ${fracao})`;

/** Pluviômetro: chuva acumulada por janela, com o limiar do município. */
export function Pluviometro({ t, municipio }: { t: T; municipio: Municipio }) {
  const max = maxPluviometro(municipio.limiar_mm);
  return (
    <div className="pluv">
      <div className="tubos">
        {JANELAS.map((k) => (
          <div key={k} className="tube" aria-hidden="true">
            {MARCAS.map((m) => (
              <span key={m} className="tick" style={{ bottom: `${m}%` }} />
            ))}
            <div className="fill" style={{ height: `calc((100% - 6px) * ${escala(municipio.chuva_acum_mm[k], max, 1)})` }} />
          </div>
        ))}
        <div className="lim" style={{ bottom: alturaTubo(escala(municipio.limiar_mm, max, 1)) }}>
          <span>{t("limiar {N} mm", { N: formatarNumero(municipio.limiar_mm, 0) })}</span>
        </div>
      </div>
      <dl className="rots">
        {JANELAS.map((k) => (
          <div key={k}>
            <dt className="p">{k.toUpperCase()}</dt>
            <dd className="v">
              {formatarMm(municipio.chuva_acum_mm[k])}
              <small> mm</small>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
