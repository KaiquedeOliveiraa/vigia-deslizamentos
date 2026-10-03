import "../styles/dados.css";
import { ArrowDown, ArrowRight, ArrowUp, Calculator, ChartLine, ClipboardList, Droplet, MapIcon } from "lucide-react";
import { useEffect, useState, type KeyboardEvent } from "react";
import { tradutor, type T } from "../i18n";
import { classe, emAlerta, infoClasse, LIMIAR_ALERTA } from "../lib/classes";
import { carregar, lerIndices, lerOcorrencias, ocorrenciasDoMunicipio, type Resultado } from "../lib/dados";
import {
  formatarData,
  formatarDataHora,
  formatarHora,
  formatarIndice,
  formatarMm,
  formatarNumero,
  formatarPercentual,
  formatarVariacao,
} from "../lib/formato";
import { diasEixo, etiquetaChuva, indicadores, serieMunicipio, variacoes } from "../lib/graficos";
import { municipioInicial, variaveis } from "../lib/monitoramento";
import type { Idioma } from "../lib/preferencias";
import { tendencia } from "../lib/texto";
import type { Dia, Indices, Municipio, Ocorrencia } from "../lib/tipos";
import { anunciar } from "./anunciar";
import { Evolucao, Minigrafico, Pluviometro } from "./Graficos";
import SeloClasse from "./SeloClasse";

const PERIODOS = [7, 5, 15];
const ICONE_TENDENCIA = { subindo: ArrowUp, descendo: ArrowDown, estável: ArrowRight };
const CLASSE_TENDENCIA = { subindo: "up", descendo: "dn", estável: "" };

const d0 = (m: Municipio) => m.dias.find((d) => d.d === 0)!;

export default function Dados({ lang }: { lang: Idioma }) {
  const t = tradutor(lang);
  const [indices, setIndices] = useState<Indices>();
  const [ocorrencias, setOcorrencias] = useState<Resultado<Ocorrencia[]>>();
  const [periodo, setPeriodo] = useState(PERIODOS[0]);
  const [ibge, setIbge] = useState<string>();

  useEffect(() => {
    carregar("indices.json", lerIndices).then((r) => {
      if (!r.ok) return;
      setIndices(r.dados);
      setIbge(municipioInicial(r.dados));
    });
    carregar("ocorrencias.json", lerOcorrencias).then(setOcorrencias);
  }, []);

  if (!indices) return null;

  const municipios = indices.municipios.filter((m) => !indices.municipios_sem_dados.includes(m.ibge) && m.dias.some((d) => d.d === 0));
  const destaque = municipios.find((m) => m.ibge === ibge);
  const eixo = diasEixo(indices.dia_alvo_d0, periodo);
  const k = indicadores(indices);

  const selecionar = (novo: string) => {
    setIbge(novo);
    anunciar(t("Evolução do índice — {M}", { M: municipios.find((m) => m.ibge === novo)!.nome }));
  };

  return (
    <div className="dados">
      <div className="ttl">
        <div>
          <span className="lbl">{t("Dados da análise · dia-alvo {N}", { N: formatarData(indices.dia_alvo_d0) })}</span>
          <h1>{t("Como a região chegou até aqui")}</h1>
          <p>{t("Mesmos dados do mapa, com a chuva acumulada e a evolução do índice nos últimos {N} dias.", { N: String(periodo) })}</p>
        </div>
        <div className="seg" role="group" aria-label={t("Período")}>
          {PERIODOS.map((p) => (
            <button key={p} type="button" aria-pressed={p === periodo} onClick={() => setPeriodo(p)}>
              {t("{N} dias", { N: String(p) })}
            </button>
          ))}
        </div>
      </div>

      <ul className="kstrip">
        <li className="kpi">
          <b>{k.monitorados}</b>
          <span>{t("municípios monitorados")}</span>
        </li>
        <li className="kpi">
          <b className="al">{k.emAlerta}</b>
          <span>{t("em alerta (índice ≥ {N})", { N: formatarNumero(LIMIAR_ALERTA, 1) })}</span>
        </li>
        <li className="kpi">
          <b>
            {k.chuvaEfetivaMax ? formatarMm(k.chuvaEfetivaMax.efr_mm) : "—"}
            <small> mm</small>
          </b>
          <span>{t("chuva efetiva máxima ({M})", { M: k.chuvaEfetivaMax?.nome ?? "—" })}</span>
        </li>
        <li className="kpi">
          <b>{k.pico ? formatarIndice(k.pico.indice) : "—"}</b>
          <span>{t("pico da semana ({M}, {N})", { M: k.pico?.nome ?? "—", N: k.pico ? formatarData(k.pico.dia_alvo, "dia") : "—" })}</span>
        </li>
      </ul>

      {destaque && (
        <>
          <div className="grid2">
            <section className="card" aria-labelledby="evo-t">
              <div className="ch">
                <ChartLine aria-hidden="true" />
                <h2 id="evo-t">{t("Evolução do índice — {M}", { M: destaque.nome })}</h2>
                <span className="tag">{t("diário · {N}", { N: formatarHora(indices.gerado_em) })}</span>
              </div>
              <p className="sub">
                {t("Pontos coloridos pela classe do dia. Linhas cinzas: demais municípios. Acima da linha tracejada o município está em alerta.")}
              </p>
              <div className="legend2" aria-hidden="true">
                <span className="trend up">
                  <ArrowUp />
                  {t("subindo")}
                </span>
                <span className="trend dn">
                  <ArrowDown />
                  {t("descendo")}
                </span>
                <span>{t("↑/↓ mudança de classe")}</span>
              </div>
              <Evolucao t={t} municipios={municipios} ibge={destaque.ibge} eixo={eixo} aoSelecionar={selecionar} />
            </section>
            <section className="card chuva" aria-labelledby="pluv-t">
              <div className="ch">
                <Droplet aria-hidden="true" />
                <h2 id="pluv-t">{t("Chuva acumulada")}</h2>
                <span className="tag">{t(etiquetaChuva(destaque))}</span>
              </div>
              <p className="sub">{t("Estimativa por grade Open-Meteo sobre {M} · linha tracejada = limiar crítico do município.", { M: destaque.nome })}</p>
              <Pluviometro t={t} municipio={destaque} />
            </section>
          </div>

          <Tabela t={t} municipios={municipios} ibge={destaque.ibge} eixo={eixo} aoSelecionar={selecionar} />

          <div className="grid2 meio">
            <Detalhes t={t} municipio={destaque} dia={d0(destaque)} gerado_em={indices.gerado_em} />
            <Ocorrencias t={t} municipio={destaque} ocorrencias={ocorrencias} />
          </div>
        </>
      )}

      <p className="disc">
        {t("Sistema de")} <b>{t("apoio à decisão")}</b>
        {t(", de caráter acadêmico. Não constitui alerta oficial e não substitui o Cemaden nem a Defesa Civil.")}
      </p>
    </div>
  );
}

interface PropsTabela {
  t: T;
  municipios: Municipio[];
  ibge: string;
  eixo: string[];
  aoSelecionar: (ibge: string) => void;
}

function Tabela({ t, municipios, ibge, eixo, aoSelecionar }: PropsTabela) {
  const teclado = (e: KeyboardEvent, novo: string) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    aoSelecionar(novo);
  };
  return (
    <section className="card" aria-labelledby="tab-t">
      <div className="ch">
        <MapIcon aria-hidden="true" />
        <h2 id="tab-t">{t("Índice por município")}</h2>
        <span className="tag">{t("clique numa linha para ver acima")}</span>
      </div>
      <div className="rolagem">
        <table className="tab">
          <thead>
            <tr>
              <th scope="col">{t("Município")}</th>
              <th scope="col" className="n">
                {t("Índice")}
              </th>
              <th scope="col">{t("Classe")}</th>
              <th scope="col" className="n">
                {t("Variação {N}", { N: "24h" })}
              </th>
              <th scope="col">{t("Últimos {N} dias", { N: String(eixo.length) })}</th>
              <th scope="col" className="n">
                {t("Chuva efetiva / limiar")}
              </th>
              <th scope="col">{t("Alerta")}</th>
            </tr>
          </thead>
          <tbody>
            {municipios.map((m) => {
              const dia = d0(m);
              const n = classe(dia.indice);
              const tend = tendencia(dia.indice, dia.dia_alvo, m.historico);
              const Icone = tend ? ICONE_TENDENCIA[tend] : ArrowRight;
              const v = variaveis(m, dia);
              return (
                <tr
                  key={m.ibge}
                  className={m.ibge === ibge ? "hl" : undefined}
                  aria-current={m.ibge === ibge ? "true" : undefined}
                  tabIndex={0}
                  onClick={() => aoSelecionar(m.ibge)}
                  onKeyDown={(e) => teclado(e, m.ibge)}
                >
                  <th scope="row">{m.nome}</th>
                  <td className="n">{formatarIndice(dia.indice)}</td>
                  <td>
                    <span className="cls">
                      <SeloClasse classe={n} />
                      {t(infoClasse(n).nome)}
                    </span>
                  </td>
                  <td className="n">
                    <span className={`trend ${tend ? CLASSE_TENDENCIA[tend] : ""}`}>
                      <Icone aria-hidden="true" />
                      {tend ? formatarVariacao(variacoes(serieMunicipio(m, 2).map((p) => p.indice))[0]) : "—"}
                    </span>
                  </td>
                  <td>
                    <Minigrafico municipio={m} eixo={eixo} />
                  </td>
                  <td className="n">
                    <div className="ratio">
                      {t("{N} / {N} mm", { N: [formatarMm(v.efr_mm), formatarNumero(v.limiar_mm, 0)] })}
                      <span className="b" aria-hidden="true">
                        <i style={{ width: `${v.barra}%` }} />
                      </span>
                    </div>
                  </td>
                  <td>{emAlerta(dia.indice) ? <span className="al">{t("sim")}</span> : t("não")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Detalhes({ t, municipio, dia, gerado_em }: { t: T; municipio: Municipio; dia: Dia; gerado_em: string }) {
  const linhas: [string, string][] = [
    [t("Probabilidade de deslizamentos pontuais"), formatarPercentual(dia.prob.pontuais)],
    [t("Probabilidade de deslizamentos esparsos"), formatarPercentual(dia.prob.esparsos)],
    [t("Probabilidade de deslizamentos generalizados"), formatarPercentual(dia.prob.generalizados)],
    [t("Chuva efetiva antecedente (EfR)"), `${formatarMm(dia.efr_mm)} mm`],
    [t("Chuva prevista para o dia-alvo"), `${formatarMm(dia.rtotal_mm)} mm`],
    [t("Limiar crítico do município"), `${formatarMm(municipio.limiar_mm)} mm`],
    [t("Fonte do limiar"), municipio.fonte_limiar],
    [t("Membros de ensemble"), String(dia.n_membros)],
    [t("Execução do modelo (horário de Brasília)"), formatarDataHora(gerado_em)],
  ];
  return (
    <section className="card" aria-labelledby="calc-t">
      <div className="ch">
        <Calculator aria-hidden="true" />
        <h2 id="calc-t">{t("Detalhes do cálculo — {M}", { M: municipio.nome })}</h2>
      </div>
      <dl className="det">
        {linhas.map(([rotulo, valor]) => (
          <div key={rotulo}>
            <dt>{rotulo}</dt>
            <dd className="num">{valor}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Ocorrencias({ t, municipio, ocorrencias }: { t: T; municipio: Municipio; ocorrencias?: Resultado<Ocorrencia[]> }) {
  const lista = ocorrencias?.ok ? ocorrenciasDoMunicipio(ocorrencias.dados, municipio.ibge) : [];
  return (
    <section className="card" aria-labelledby="oc-t">
      <div className="ch">
        <ClipboardList aria-hidden="true" />
        <h2 id="oc-t">{t("Ocorrências registradas — {M}", { M: municipio.nome })}</h2>
      </div>
      {!ocorrencias && <p className="sub">{t("Carregando os dados…")}</p>}
      {ocorrencias && !ocorrencias.ok && <p className="sub">{t("Não foi possível carregar os dados.")}</p>}
      {ocorrencias?.ok && lista.length === 0 && <p className="sub">{t("Nenhuma ocorrência registrada")}</p>}
      {lista.length > 0 && (
        <ul className="ocs">
          {lista.map((o) => (
            <li key={`${o.data}-${o.tipo}-${o.descricao}`}>
              <span className="lbl">
                <time dateTime={o.data}>{formatarData(o.data)}</time> · {o.tipo}
              </span>
              <p>{o.descricao}</p>
              <span className="note">
                {t("Fonte:")} {o.fonte}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
