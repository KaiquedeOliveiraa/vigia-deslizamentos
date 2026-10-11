import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { T } from "../i18n";
import { infoClasse, LIMIAR_ALERTA } from "../lib/classes";
import { formatarData, formatarIndice, formatarMm, formatarNumero, formatarVariacao } from "../lib/formato";
import {
  coordenadas,
  escala,
  faixasClasse,
  marcaClasse,
  marcasEvolucao,
  maxEvolucao,
  maxPluviometro,
  serieMunicipio,
  variacoesDiarias,
  type Area,
} from "../lib/graficos";
import { sentido } from "../lib/texto";
import type { ChuvaAcum, Municipio } from "../lib/tipos";

const AREA: Area = { largura: 760, altura: 300, esq: 44, dir: 16, topo: 18, base: 34 };
const AREA_MINI: Area = { largura: 110, altura: 26, esq: 3, dir: 3, topo: 3, base: 3 };
const CLASSE_SENTIDO = { subindo: "up", descendo: "dn", estável: "" } as const;

const pontos = (c: { x: number; y: number }[]) => c.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

interface PropsEvolucao {
  t: T;
  municipios: Municipio[];
  destaque: Municipio;
  /** Dias do eixo X, do mais antigo ao D0. */
  eixo: string[];
  aoSelecionar: (ibge: string) => void;
}

/** Evolução do índice (RF06): faixas das classes, linha de alerta, demais municípios em cinza e o destaque.
 * Linha-guia com o valor de todos os municípios no dia apontado (mouse, ou ←/→ com o gráfico em foco). */
export function Evolucao({ t, municipios, destaque, eixo, aoSelecionar }: PropsEvolucao) {
  const chips = useRef<(HTMLButtonElement | null)[]>([]);
  const [foco, setFoco] = useState<number | null>(null);
  const { ibge } = destaque;
  const series = municipios.map((m) => ({ m, serie: serieMunicipio(m, eixo) }));
  const max = maxEvolucao(series.flatMap((s) => s.serie.map((p) => p.indice)));
  const coords = coordenadas(serieMunicipio(destaque, eixo), eixo, max, AREA);
  const deltas = variacoesDiarias(coords.map((c) => c.ponto));
  const { esq, dir, largura, altura, topo, base } = AREA;
  const util = altura - topo - base;
  const y = (v: number) => topo + util - escala(v, max, util);
  const xs = coordenadas(eixo.map((dia_alvo) => ({ dia_alvo, indice: 0 })), eixo, max, AREA).map((c) => c.x);
  const faixas = faixasClasse(max);
  const rotulo = t("Evolução do índice de risco em {N} dias — {M}", { N: String(eixo.length), M: destaque.nome });
  const ultimo = coords.at(-1);
  const deltaUltimo = deltas.at(-1) ?? null;
  const area = coords.length > 1 ? `${coords[0].x},${y(0)} ${pontos(coords)} ${coords.at(-1)!.x},${y(0)}` : "";

  function teclado(e: KeyboardEvent, i: number) {
    const passo = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!passo) return;
    e.preventDefault();
    const j = (i + passo + municipios.length) % municipios.length;
    chips.current[j]?.focus();
    aoSelecionar(municipios[j].ibge);
  }

  // Dia mais próximo do ponteiro: o leitor mira uma data, não uma linha de 2px.
  function apontar(e: PointerEvent<SVGRectElement>) {
    const caixa = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
    const x = ((e.clientX - caixa.left) / caixa.width) * largura;
    setFoco(xs.reduce((melhor, xi, i) => (Math.abs(xi - x) < Math.abs(xs[melhor] - x) ? i : melhor), 0));
  }

  function tecladoGrafico(e: KeyboardEvent) {
    const passo = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!passo) return;
    e.preventDefault();
    setFoco((f) => (f === null ? eixo.length - 1 : Math.min(Math.max(f + passo, 0), eixo.length - 1)));
  }

  const diaFoco = foco === null ? null : eixo[foco];
  const iFoco = coords.findIndex((c) => c.ponto.dia_alvo === diaFoco);
  const pontoFoco = iFoco < 0 ? null : coords[iFoco].ponto;
  const deltaFoco = iFoco < 0 ? null : deltas[iFoco];
  const leitura =
    diaFoco === null
      ? []
      : series
          .flatMap(({ m, serie }) => {
            const p = serie.find((q) => q.dia_alvo === diaFoco);
            return p ? [{ m, p }] : [];
          })
          .sort((a, b) => Number(b.m.ibge === ibge) - Number(a.m.ibge === ibge) || b.p.indice - a.p.indice);

  return (
    <div className="evo">
      <div className="pick" role="tablist" aria-label={t("Município")}>
        {municipios.map((m, i) => (
          <button
            key={m.ibge}
            ref={(el) => {
              chips.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`evo-${m.ibge}`}
            aria-selected={m.ibge === ibge}
            aria-controls="evo-painel"
            tabIndex={m.ibge === ibge ? 0 : -1}
            onClick={() => aoSelecionar(m.ibge)}
            onKeyDown={(e) => teclado(e, i)}
          >
            {m.nome}
          </button>
        ))}
      </div>
      <div
        className="evo-svg"
        id="evo-painel"
        role="tabpanel"
        aria-labelledby={`evo-${ibge}`}
        tabIndex={0}
        onKeyDown={tecladoGrafico}
        onBlur={() => setFoco(null)}
      >
        <div className="evo-plot">
        <svg viewBox={`0 0 ${largura} ${altura}`} role="img" aria-label={rotulo}>
          {faixas.map((f) => (
            <rect key={f.numero} className="band" x={esq} width={largura - esq - dir} y={y(f.ate)} height={y(f.de) - y(f.ate)} style={{ fill: `var(--c${f.numero})` }} />
          ))}
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
          {eixo.map((dia, i) => (
            <text key={dia} className={i === foco ? "ax on" : "ax"} x={xs[i]} y={altura - 10} textAnchor="middle">
              {formatarData(dia, "dia")}
            </text>
          ))}
          {series
            .filter((s) => s.m.ibge !== ibge)
            .map((s) => (
              <polyline key={s.m.ibge} className="other" points={pontos(coordenadas(s.serie, eixo, max, AREA))} />
            ))}
          {area && <polygon className="area" points={area} />}
          <polyline className="main" points={pontos(coords)} />
          {foco !== null && <line className="guia" x1={xs[foco]} x2={xs[foco]} y1={topo} y2={y(0)} />}
          {coords.map((c, i) => {
            const n = c.ponto.classe;
            // Variação só existe quando o ponto anterior é o dia anterior.
            const marca = deltas[i] === null ? null : marcaClasse(coords[i - 1].ponto.classe, n);
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
            {leitura.length === 0 && <span className="vazio">{t("sem dados")}</span>}
            <ul>
              {leitura.map(({ m, p }) =>
                m.ibge === ibge ? (
                  <li key={m.ibge} className="eu">
                    <i aria-hidden="true" />
                    <b className="num">{formatarIndice(p.indice)}</b>
                    <span>
                      {m.nome}
                      {deltaFoco != null && <em className={`dl ${CLASSE_SENTIDO[sentido(deltaFoco)]}`}> {formatarVariacao(deltaFoco)}</em>}
                      <small>{t(infoClasse(p.classe).nome)}</small>
                    </span>
                  </li>
                ) : (
                  <li key={m.ibge}>
                    <i aria-hidden="true" />
                    <b className="num">{formatarIndice(p.indice)}</b>
                    <span>{m.nome}</span>
                  </li>
                ),
              )}
            </ul>
          </div>
        )}
        </div>
        {/* Leitura do dia apontado para leitor de tela (←/→ com o gráfico em foco). */}
        <p className="sr-only" aria-live="polite">
          {pontoFoco ? `${formatarData(pontoFoco.dia_alvo)} · ${t("{M}: índice {N}, classe {C}", { M: destaque.nome, N: formatarIndice(pontoFoco.indice), C: infoClasse(pontoFoco.classe).nome })}` : ""}
        </p>
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
                  <td>{t(infoClasse(ponto.classe).nome)}</td>
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
