import "../styles/cartao.css";
import "../styles/dados.css";
import { ArrowDown, ArrowRight, ArrowUp, Calculator, ChartLine, Droplet, MapIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { tradutor, type T } from "../i18n";
import { emAlerta, infoClasse, LIMIAR_ALERTA } from "../lib/classes";
import { carregar, lerIndices, separarPorDados, type NomeMunicipio, type Resultado } from "../lib/dados";
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
import { diasComDadosDe, diasEixo, etiquetaChuva, indicadores, serieMunicipio, variacoesDiarias } from "../lib/graficos";
import { combinarHistorico, lerHistorico, type ArquivoHistorico } from "../lib/historico";
import { municipioInicial, variaveis } from "../lib/monitoramento";
import { ajustarPersonalizado, eixoDoPeriodo, escreverPeriodo, lerPeriodo, limitesPersonalizado, somarDias, type Periodo } from "../lib/periodo";
import type { Idioma } from "../lib/preferencias";
import { rota } from "../lib/telas";
import { tendencia } from "../lib/texto";
import type { Indices, Municipio } from "../lib/tipos";
import { anunciar } from "./anunciar";
import { Evolucao, Minigrafico, Pluviometro } from "./Graficos";
import EstadoCarregamento from "./EstadoCarregamento";
import SeloClasse from "./SeloClasse";

const DIAS_TABELA = 7;
const ICONE_TENDENCIA = { subindo: ArrowUp, descendo: ArrowDown, estável: ArrowRight };
const CLASSE_TENDENCIA = { subindo: "up", descendo: "dn", estável: "" };

const d0 = (m: Municipio) => m.dias.find((d) => d.d === 0);

export default function Dados({ lang, nomes }: { lang: Idioma; nomes: readonly NomeMunicipio[] }) {
  const t = tradutor(lang);
  const [carga, setCarga] = useState<Resultado<Indices>>();
  const [periodo, setPeriodo] = useState<Periodo>({ tipo: 7 });
  const [ajustado, setAjustado] = useState(false);
  const [ibge, setIbge] = useState<string>();
  // undefined = carregando.
  const [real, setReal] = useState<Resultado<ArquivoHistorico>>();
  const [rec, setRec] = useState<Resultado<ArquivoHistorico>>();

  useEffect(() => {
    carregar("indices.json", lerIndices).then((r) => {
      setCarga(r);
      if (!r.ok) return;
      setIbge(municipioInicial(r.dados));
      const lido = lerPeriodo(location.search, r.dados.dia_alvo_d0);
      setPeriodo(lido.periodo);
      setAjustado(lido.ajustado);
      if (lido.ajustado) history.replaceState(null, "", location.pathname + escreverPeriodo(location.search, lido.periodo) + location.hash);
    });
    carregar("historico.json", lerHistorico).then(setReal);
    carregar("historico_reconstruido.json", lerHistorico).then((r) => {
      if (!r.ok) console.error(r.erro);
      setRec(r);
    });
  }, []);

  const indicesOuNada = carga?.ok ? carga.dados : undefined;
  const dia0 = indicesOuNada?.dia_alvo_d0 ?? "";
  const combinados = useMemo(
    () => indicesOuNada?.municipios.map((m) => combinarHistorico(m, dia0, real?.ok ? real.dados : undefined, rec?.ok ? rec.dados : undefined)),
    [indicesOuNada, dia0, real, rec],
  );
  const separados = useMemo(() => (indicesOuNada ? separarPorDados(indicesOuNada, nomes) : undefined), [indicesOuNada, nomes]);
  // Mesma ordem de indices.municipios, só quem tem D0; referência estável para os gráficos.
  const municipios = useMemo(() => {
    const comD0 = new Set(separados?.comDados.map((m) => m.ibge));
    return (combinados ?? []).filter((m) => comD0.has(m.ibge));
  }, [combinados, separados]);
  const eixo = useMemo(() => (dia0 ? eixoDoPeriodo(periodo, dia0) : []), [periodo, dia0]);

  const mudar = (p: Periodo) => {
    setPeriodo(p);
    setAjustado(false);
    history.replaceState(null, "", location.pathname + escreverPeriodo(location.search, p) + location.hash);
  };
  const escolherPersonalizado = () => {
    if (periodo.tipo !== "personalizado") mudar({ tipo: "personalizado", de: somarDias(dia0, -29), ate: dia0 });
  };
  const mudarData = (campo: "de" | "ate", valor: string) => {
    if (periodo.tipo !== "personalizado") return;
    const aj = ajustarPersonalizado(campo === "de" ? valor : periodo.de, campo === "ate" ? valor : periodo.ate, dia0);
    if (aj) mudar({ tipo: "personalizado", de: aj.de, ate: aj.ate });
  };

  const titulo = t("Como a região chegou até aqui");
  if (!carga?.ok)
    return (
      <div className="dados">
        <h1>{titulo}</h1>
        <EstadoCarregamento t={t} falhou={!!carga} />
      </div>
    );

  const indices = carga.dados;
  const semDados = separados?.semDados ?? [];
  const destaque = municipios.find((m) => m.ibge === ibge);
  const comHistorico = destaque ? diasComDadosDe(destaque, eixo) : eixo.length;
  const eixo7 = diasEixo(dia0, DIAS_TABELA);
  const limites = limitesPersonalizado(dia0);
  const personalizado = periodo.tipo === "personalizado" ? periodo : null;
  const k = indicadores(indices);

  // Um só aviso: falha de arquivo só importa se o eixo passa do histórico do indices.json.
  const primeiroDia = indices.municipios.find((m) => m.ibge === destaque?.ibge)?.historico[0]?.dia_alvo ?? dia0;
  // O período de 7 dias não precisa dos arquivos longos: nunca avisa de falha deles.
  const alemDoIndices = periodo.tipo !== 7 && eixo[0] < primeiroDia;
  const carregando = real === undefined || rec === undefined;
  let aviso: string | null = null;
  if (destaque && !(carregando && alemDoIndices)) {
    if (alemDoIndices && (real?.ok === false || rec?.ok === false)) aviso = t("Parte do histórico não carregou; esses dias aparecem vazios.");
    else if (comHistorico < eixo.length)
      aviso =
        comHistorico === 1
          ? t("Por enquanto há histórico de 1 dia para {M}; os demais aparecem vazios.", { M: destaque.nome })
          : t("Por enquanto há histórico de {N} dias para {M}; os demais aparecem vazios.", { N: String(comHistorico), M: destaque.nome });
  }

  const selecionar = (novo: string) => {
    setIbge(novo);
    const m = municipios.find((x) => x.ibge === novo);
    if (m) anunciar(t("Evolução do índice — {M}", { M: m.nome }));
  };

  const tabela = <Tabela t={t} municipios={municipios} semDados={semDados} ibge={destaque?.ibge} eixo7={eixo7} aoSelecionar={selecionar} />;

  return (
    <div className="dados">
      <div className="ttl">
        <div>
          <span className="lbl">{t("Dados da análise · dia-alvo {N}", { N: formatarData(indices.dia_alvo_d0) })}</span>
          <h1>{titulo}</h1>
          <p>
            {personalizado
              ? t("Mesmos dados do mapa, com a chuva acumulada e a evolução do índice de {N} a {N}.", {
                  N: [formatarData(personalizado.de), formatarData(personalizado.ate)],
                })
              : t("Mesmos dados do mapa, com a chuva acumulada e a evolução do índice nos últimos {N} dias.", { N: String(periodo.tipo) })}
          </p>
          {personalizado && ajustado && <p>{t("O período do link foi ajustado ao último ano disponível.")}</p>}
          {aviso && <p>{aviso}</p>}
        </div>
        <div>
          <div className="seg" role="group" aria-label={t("Período")}>
            {([7, 30] as const).map((p) => (
              <button key={p} type="button" aria-pressed={periodo.tipo === p} onClick={() => mudar({ tipo: p })}>
                {t("{N} dias", { N: String(p) })}
              </button>
            ))}
            <button type="button" aria-pressed={!!personalizado} onClick={escolherPersonalizado}>
              {t("Personalizado")}
            </button>
          </div>
          {personalizado && (
            <div className="datas">
              <label>
                {t("De")}
                <input type="date" value={personalizado.de} min={limites.min} max={personalizado.ate} onChange={(e) => mudarData("de", e.target.value)} />
              </label>
              <label>
                {t("Até")}
                <input type="date" value={personalizado.ate} min={personalizado.de} max={limites.max} onChange={(e) => mudarData("ate", e.target.value)} />
              </label>
            </div>
          )}
          {/* Sempre montado: leitores de tela só anunciam mudanças em regiões que já existiam. */}
          <p className="sr-only" aria-live="polite">
            {personalizado && t("Período: {N} a {N}", { N: [formatarData(personalizado.de), formatarData(personalizado.ate)] })}
          </p>
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

      {destaque ? (
        <>
          <div className="grid2">
            <section className="card" aria-labelledby="evo-t">
              <div className="ch">
                <ChartLine aria-hidden="true" />
                <h2 id="evo-t">{t("Evolução do índice — {M}", { M: destaque.nome })}</h2>
                <span className="tag">{t("diário · {N}", { N: formatarHora(indices.gerado_em) })}</span>
              </div>
              <p className="sub">
                {t("Pontos coloridos pela classe do dia. Faixa cinza: mínimo e máximo dos demais municípios. Acima da linha tracejada o município está em alerta.")}
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
                <span>{t("faixa: mínimo e máximo dos demais municípios")}</span>
              </div>
              <Evolucao t={t} municipios={municipios} destaque={destaque} eixo={eixo} aoSelecionar={selecionar} />
              {semDados.length > 0 && (
                <p className="sub">{t("Sem dados nesta execução: {M}.", { M: semDados.map((m) => m.nome).join(", ") })}</p>
              )}
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

          {tabela}

          <Detalhes t={t} municipio={destaque} gerado_em={indices.gerado_em} />
          <p className="ver-areas">
            <a href={`${rota("areas-de-risco", lang)}?municipio=${destaque.ibge}`}>{t("Histórico de ocorrências e áreas de risco de {M}: ver em Áreas de risco", { M: destaque.nome })}</a>
          </p>
        </>
      ) : (
        <>
          <p className="card vazio" role="status">
            {t("Nenhum município tem dados nesta execução.")}
          </p>
          {tabela}
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
  semDados: NomeMunicipio[];
  ibge?: string;
  eixo7: string[];
  aoSelecionar: (ibge: string) => void;
}

function Tabela({ t, municipios, semDados, ibge, eixo7, aoSelecionar }: PropsTabela) {
  return (
    <section className="card" aria-labelledby="tab-t">
      <div className="ch">
        <MapIcon aria-hidden="true" />
        <h2 id="tab-t">{t("Índice por município")}</h2>
        <span className="tag">{t("clique numa linha para ver acima")}</span>
      </div>
      {/* Rola na horizontal em telas estreitas: focável para quem usa teclado. */}
      <div className="rolagem" tabIndex={0} role="region" aria-labelledby="tab-t">
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
              <th scope="col">{t("Últimos {N} dias", { N: String(eixo7.length) })}</th>
              <th scope="col" className="n">
                {t("Chuva efetiva / limiar")}
              </th>
              <th scope="col">{t("Alerta")}</th>
            </tr>
          </thead>
          <tbody>
            {municipios.map((m) => {
              // separarPorDados só põe aqui municípios com D0.
              const dia = d0(m);
              if (!dia) return null;
              const n = dia.classe;
              const tend = tendencia(dia.indice, dia.dia_alvo, m.historico);
              const delta = variacoesDiarias(serieMunicipio(m, diasEixo(dia.dia_alvo, 2))).at(-1);
              const Icone = tend ? ICONE_TENDENCIA[tend] : ArrowRight;
              const v = variaveis(m, dia);
              return (
                // A linha inteira responde ao clique; no teclado, o botão do nome (Enter/Espaço viram clique, que sobe até a linha).
                <tr key={m.ibge} className={m.ibge === ibge ? "hl" : undefined} onClick={() => aoSelecionar(m.ibge)}>
                  <th scope="row">
                    <button type="button" className="linha" aria-pressed={m.ibge === ibge}>
                      {m.nome}
                    </button>
                  </th>
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
                      {delta != null ? formatarVariacao(delta) : "—"}
                    </span>
                  </td>
                  <td>
                    <Minigrafico municipio={m} eixo={eixo7} />
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
            {semDados.map((m) => (
              <tr key={m.ibge} className="sd">
                <th scope="row">{m.nome}</th>
                <td colSpan={6}>
                  <span className="sd-tag">{t("sem dados")}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Detalhes({ t, municipio, gerado_em }: { t: T; municipio: Municipio; gerado_em: string }) {
  const dia = d0(municipio);
  if (!dia) return null;
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
