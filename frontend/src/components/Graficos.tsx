import { useRef, type KeyboardEvent } from "react";
import type { T } from "../i18n";
import { classe, infoClasse, LIMIAR_ALERTA } from "../lib/classes";
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
  ibge: string;
  /** Dias do eixo X, do mais antigo ao D0. */
  eixo: string[];
  aoSelecionar: (ibge: string) => void;
}

/** Evolução do índice (RF06): faixas das classes, linha de alerta, demais municípios em cinza e o destaque. */
export function Evolucao({ t, municipios, ibge, eixo, aoSelecionar }: PropsEvolucao) {
  const chips = useRef<(HTMLButtonElement | null)[]>([]);
  const series = new Map(municipios.map((m) => [m.ibge, serieMunicipio(m, eixo)]));
  const max = maxEvolucao([...series.values()].flat().map((p) => p.indice));
  const destaque = municipios.find((m) => m.ibge === ibge)!;
  const coords = coordenadas(series.get(ibge)!, eixo, max, AREA);
  const deltas = variacoesDiarias(coords.map((c) => c.ponto));
  const { esq, dir, largura, altura, topo, base } = AREA;
  const util = altura - topo - base;
  const y = (v: number) => topo + util - escala(v, max, util);
  const faixas = faixasClasse(max);
  const rotulo = t("Evolução do índice de risco em {N} dias — {M}", { N: String(eixo.length), M: destaque.nome });

  function teclado(e: KeyboardEvent, i: number) {
    const passo = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!passo) return;
    e.preventDefault();
    const j = (i + passo + municipios.length) % municipios.length;
    chips.current[j]?.focus();
    aoSelecionar(municipios[j].ibge);
  }

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
      <div className="evo-svg" id="evo-painel" role="tabpanel" aria-labelledby={`evo-${ibge}`} tabIndex={0}>
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
          {coordenadas(eixo.map((dia_alvo) => ({ dia_alvo, indice: 0 })), eixo, max, AREA).map((c) => (
            <text key={c.ponto.dia_alvo} className="ax" x={c.x} y={altura - 10} textAnchor="middle">
              {formatarData(c.ponto.dia_alvo, "dia")}
            </text>
          ))}
          {municipios
            .filter((m) => m.ibge !== ibge)
            .map((m) => (
              <polyline key={m.ibge} className="other" points={pontos(coordenadas(series.get(m.ibge)!, eixo, max, AREA))} />
            ))}
          <polyline className="main" points={pontos(coords)} />
          {coords.map((c, i) => {
            const n = classe(c.ponto.indice);
            const delta = deltas[i];
            const marca = delta === null ? null : marcaClasse(c.ponto.indice - delta, c.ponto.indice);
            return (
              <g key={c.ponto.dia_alvo}>
                <circle className="pt" cx={c.x} cy={c.y} r="6" style={{ fill: `var(--c${n})` }}>
                  <title>{t("{N}: {N} — {C}", { N: [formatarData(c.ponto.dia_alvo, "dia"), formatarIndice(c.ponto.indice)], C: infoClasse(n).nome })}</title>
                </circle>
                {delta !== null && (
                  <text className={`dl ${CLASSE_SENTIDO[sentido(delta)]}`} x={c.x} y={c.y - 13}>
                    {formatarVariacao(delta)}
                  </text>
                )}
                {marca && (
                  <text className="cl" x={c.x} y={c.y + 22}>
                    {t(marca)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
        <table className="sr-only">
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
                <td>{t(infoClasse(classe(ponto.indice)).nome)}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
  const yAlerta = altura - base - escala(LIMIAR_ALERTA, max, altura - topo - base);
  return (
    <svg className="spark" width={largura} height={altura} viewBox={`0 0 ${largura} ${altura}`} aria-hidden="true">
      <line x1="0" x2={largura} y1={yAlerta} y2={yAlerta} stroke="var(--alert-line)" strokeDasharray="3 3" />
      <polyline fill="none" stroke="var(--ink-brand)" strokeWidth="1.5" points={pontos(coords)} />
      {coords.map((c) => (
        <circle key={c.ponto.dia_alvo} cx={c.x} cy={c.y} r="2.4" style={{ fill: `var(--c${classe(c.ponto.indice)})` }} stroke="var(--ink)" strokeWidth=".6" />
      ))}
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
