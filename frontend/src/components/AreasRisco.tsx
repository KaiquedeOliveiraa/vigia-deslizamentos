import "../styles/areas.css";
import { TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { tradutor, type T } from "../i18n";
import { estadoDoPainel, rotuloSetoresMunicipio } from "../lib/areas";
import { carregar, lerEstacoes, type Resultado } from "../lib/dados";
import { estacoesVisiveis, rotuloEstacao, textoDistancia } from "../lib/estacoes";
import { formatarCoord, formatarData } from "../lib/formato";
import { MONITORADOS, NOMES } from "../lib/municipios";
import type { Idioma } from "../lib/preferencias";
import {
  escreverSelecao,
  lerSelecao,
  lerSetores,
  mostrarSetoresIndividuais,
  porMunicipio,
  resumo,
  ROTULO_GRAU,
  ROTULO_TIPO,
  type ColecaoSetores,
  type GrauSetor,
  type Setor,
} from "../lib/setores";
import { rota } from "../lib/telas";
import type { Estacao } from "../lib/tipos";
import { anunciar } from "./anunciar";
import Mapa, { type Pino } from "./Mapa";
import Ocorrencias from "./Ocorrencias";

const IBGES: ReadonlySet<string> = new Set(MONITORADOS.map((m) => m.ibge));
const SEM_SETORES: Setor[] = [];
const nome = (ibge: string) => NOMES.get(ibge) ?? ibge;
const milhar = (n: number) => n.toLocaleString("pt-BR");

interface Selecao {
  municipio: string | null;
  setor: string | null;
}

/** Símbolo do grau: círculo (alto) ou losango (muito alto), nunca só a cor (RN03). */
const Marca = ({ grau }: { grau: GrauSetor }) => (
  <span className={`setor-marca ${grau}`} aria-hidden="true">
    <i />
  </span>
);

/** "· 3.062 pessoas nos setores mapeados"; some quando nenhum setor informa pessoas (desconhecido não é zero). */
function textoPessoas(t: T, setores: Setor[]): string {
  if (!setores.some((s) => s.pessoas !== null)) return "";
  const n = resumo(setores).pessoas;
  return ` · ${n === 1 ? t("1 pessoa nos setores mapeados") : t("{N} pessoas nos setores mapeados", { N: milhar(n) })}`;
}

const tipoGrau = (t: T, s: Setor) => `${t(ROTULO_TIPO[s.tipo])} · ${t(ROTULO_GRAU[s.grau])}`;

/** Tela Áreas de risco: setores de risco geológico do SGB, ocorrências do município e a camada INMET opcional. */
export default function AreasRisco({ lang }: { lang: Idioma }) {
  const t = useMemo(() => tradutor(lang), [lang]);
  const [carga, setCarga] = useState<Resultado<ColecaoSetores>>();
  const [estacoes, setEstacoes] = useState<Resultado<Estacao[]>>();
  const [sel, setSel] = useState<Selecao>({ municipio: null, setor: null });
  const [inmet, setInmet] = useState(false);
  const [falhaInmet, setFalhaInmet] = useState(false);
  const [pino, setPino] = useState<string | null>(null);
  const [longe, setLonge] = useState(true);
  const painel = useRef<HTMLElement>(null);
  const tituloPainel = useRef<HTMLHeadingElement>(null);
  const botoesSetor = useRef(new Map<string, HTMLButtonElement>());

  // Seleção inicial lida da URL: não anuncia, não move o foco nem rola (só normaliza a URL, sem valores inválidos).
  useEffect(() => {
    carregar("setores_risco.geojson", lerSetores).then((r) => {
      setCarga(r);
      const inicial = lerSelecao(location.search, r.ok ? r.dados.setores : SEM_SETORES, IBGES);
      setSel(inicial);
      history.replaceState(null, "", location.pathname + escreverSelecao(location.search, inicial) + location.hash);
    });
  }, []);

  const setores = carga?.ok ? carga.dados.setores : SEM_SETORES;
  const contagem = useMemo(() => {
    const n = new Map<string, number>();
    for (const s of setores) n.set(s.ibge, (n.get(s.ibge) ?? 0) + 1);
    return n;
  }, [setores]);
  // Sem os setores (carregando ou erro), só o nome: um erro nunca vira "nenhum setor mapeado".
  const carregou = !!carga?.ok;
  const rotuloMunicipio = useCallback(
    (ibge: string, m: string) => (carregou ? rotuloSetoresMunicipio(t, m, contagem.get(ibge) ?? 0) : m),
    [t, contagem, carregou],
  );

  /** Toda seleção do usuário: URL, anúncio, foco (no título do painel, ou `foco`) e, no celular, rola até o painel. */
  function aplicar(nova: Selecao, mensagem: string, foco?: () => void) {
    setSel(nova);
    history.replaceState(null, "", location.pathname + escreverSelecao(location.search, nova) + location.hash);
    anunciar(mensagem);
    const celular = matchMedia("(max-width: 900px)").matches;
    requestAnimationFrame(() => {
      if (foco) return foco();
      tituloPainel.current?.focus({ preventScroll: celular });
      if (celular) painel.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    });
  }

  const escolherMunicipio = (ibge: string) =>
    aplicar({ municipio: ibge, setor: null }, carregou ? rotuloSetoresMunicipio(t, nome(ibge), contagem.get(ibge) ?? 0) : nome(ibge));
  const escolherSetor = (id: string) => {
    const s = setores.find((x) => x.id === id);
    if (s) aplicar({ municipio: s.ibge, setor: s.id }, `${tipoGrau(t, s)}, ${nome(s.ibge)}`);
  };
  const verRegiao = () => aplicar({ municipio: null, setor: null }, t("Ver toda a região"));

  async function alternarInmet() {
    if (inmet) return setInmet(false);
    setFalhaInmet(false);
    setInmet(true);
    if (estacoes?.ok) return;
    const r = await carregar("estacoes.json", lerEstacoes);
    setEstacoes(r);
    if (!r.ok) {
      setInmet(false);
      setFalhaInmet(true);
    }
  }

  const distancia = (e: Estacao) => textoDistancia(t, e.distancia_km, nome(e.ibge_referencia));
  const pinos: Pino[] = estacoes?.ok
    ? estacoesVisiveis(estacoes.dados).map((e) => ({
        id: e.codigo,
        lat: e.lat,
        lon: e.lon,
        rotulo: rotuloEstacao(t, e, nome(e.ibge_referencia)),
        balao: (
          <>
            <b>{e.nome}</b>
            <span>{distancia(e)}</span>
            <span>INMET {e.codigo}</span>
            <span className="mono">{formatarCoord(e.lat, e.lon, t)}</span>
          </>
        ),
      }))
    : [];

  const estado = estadoDoPainel(carga, sel.municipio, sel.setor);
  const titulo = (conteudo: ReactNode) => (
    <h2 id="titulo-areas" ref={tituloPainel} tabIndex={-1} className="titulo-painel">
      {conteudo}
    </h2>
  );
  const botaoRegiao = (
    <button type="button" className="btn" onClick={verRegiao}>
      {t("Ver toda a região")}
    </button>
  );
  const fonte = (
    <p className="note">
      {t("Fonte: Serviço Geológico do Brasil (SGB), setorização de riscos geológicos.")}{" "}
      <a href="https://geoportal.sgb.gov.br/" target="_blank" rel="noopener">
        geoportal.sgb.gov.br
      </a>
    </p>
  );

  function conteudo() {
    switch (estado) {
      case "carregando":
        return (
          <p className="note" role="status">
            {t("Carregando os setores…")}
          </p>
        );
      case "erro":
        return (
          <>
            <p className="erro-carga" role="alert">
              {t("Não foi possível carregar os setores de risco.")}
            </p>
            {sel.municipio && (
              <>
                {titulo(nome(sel.municipio))}
                <Ocorrencias t={t} ibge={sel.municipio} nome={nome(sel.municipio)} />
                {botaoRegiao}
              </>
            )}
          </>
        );
      case "regiao": {
        const r = resumo(setores);
        const sem = MONITORADOS.filter((m) => !contagem.has(m.ibge)).map((m) => m.nome);
        return (
          <>
            {titulo(t("Risco geológico mapeado pelo SGB"))}
            <p className="resumo-areas">
              {t("{N} setores de risco geológico em {N} dos {N} municípios", { N: [String(r.setores), String(r.municipios), String(IBGES.size)] })}
              {textoPessoas(t, setores)}
            </p>
            {r.anoMin !== null && <p className="note">{t("Mapeamentos de {N} a {N}", { N: [String(r.anoMin), String(r.anoMax)] })}</p>}
            <ul className="lst lst-areas">
              {porMunicipio(setores).map(({ ibge, setores: lista }) => (
                <li key={ibge}>
                  <button type="button" onClick={() => escolherMunicipio(ibge)}>
                    <span className="setor-conta" aria-hidden="true">
                      {lista.length}
                    </span>
                    <span>{rotuloSetoresMunicipio(t, nome(ibge), lista.length)}</span>
                  </button>
                </li>
              ))}
            </ul>
            {sem.length > 0 && (
              <details className="sem-setores">
                <summary>
                  {t("Sem setores mapeados:")} {sem.length}
                </summary>
                <p>{sem.join(", ")}</p>
              </details>
            )}
            {fonte}
          </>
        );
      }
      case "municipio": {
        const ibge = sel.municipio!;
        const M = nome(ibge);
        const lista = setores.filter((s) => s.ibge === ibge);
        const r = resumo(lista);
        return (
          <>
            {titulo(M)}
            {lista.length === 0 ? (
              <p className="resumo-areas">{t("O SGB não mapeou setores em {M}. O mapeamento é parcial: isso não significa que não haja risco.", { M })}</p>
            ) : (
              <>
                <p className="resumo-areas">
                  {lista.length === 1
                    ? t("{M}: 1 setor", { M })
                    : t("{M}: {N} setores ({N} risco muito alto, {N} alto)", { M, N: [String(r.setores), String(r.muitoAlto), String(r.alto)] })}
                  {textoPessoas(t, lista)}
                </p>
                <div className="lista-setores" tabIndex={0} role="region" aria-label={t("Setores de {M}", { M })}>
                  <ul className="lst lst-areas">
                    {lista.map((s) => (
                      <li key={s.id}>
                        <button
                          type="button"
                          aria-pressed={s.id === sel.setor}
                          ref={(el) => {
                            if (el) botoesSetor.current.set(s.id, el);
                            else botoesSetor.current.delete(s.id);
                          }}
                          onClick={() => escolherSetor(s.id)}
                        >
                          <Marca grau={s.grau} />
                          <span>
                            {tipoGrau(t, s)}
                            {s.local && (
                              <>
                                <span className="sr-only">, </span>
                                <small lang="pt-BR">{s.local}</small>
                              </>
                            )}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
                {fonte}
              </>
            )}
            <Ocorrencias t={t} ibge={ibge} nome={M} />
            <a className="btn" href={`${rota("", lang)}?municipio=${ibge}`}>
              {t("Ver o índice de {M} em Monitoramento", { M })}
            </a>
            {botaoRegiao}
          </>
        );
      }
      case "setor": {
        const s = setores.find((x) => x.id === sel.setor)!;
        const M = nome(s.ibge);
        const original = lang !== "pt" && <small className="original">{t("texto original do SGB, em português")}</small>;
        const texto = (v: string | null) => (v ? <dd lang="pt-BR">{v}</dd> : <dd>{t("não informado")}</dd>);
        const numero = (v: number | null) => <dd>{v === null ? t("não informado") : milhar(v)}</dd>;
        return (
          <>
            <span className="lbl">{M}</span>
            {titulo(
              <>
                <Marca grau={s.grau} />
                <span>{tipoGrau(t, s)}</span>
              </>,
            )}
            {original}
            <dl className="campos-setor">
              <div>
                <dt>{t("Local")}</dt>
                {texto(s.local)}
              </div>
              <div>
                <dt>{t("Pessoas")}</dt>
                {numero(s.pessoas)}
              </div>
              <div>
                <dt>{t("Moradias")}</dt>
                {numero(s.moradias)}
              </div>
              <div>
                <dt>{t("Descrição de campo")}</dt>
                {texto(s.descricao)}
              </div>
              <div>
                <dt>{t("Recomendação do SGB")}</dt>
                {texto(s.recomendacao)}
              </div>
            </dl>
            <p className="note">{s.data ? t("Mapeado em {N}", { N: formatarData(s.data) }) : t("data não informada")}</p>
            {fonte}
            <button
              type="button"
              className="btn"
              onClick={() =>
                aplicar({ municipio: s.ibge, setor: null }, M, () => botoesSetor.current.get(s.id)?.focus())
              }
            >
              {t("Voltar para {M}", { M })}
            </button>
            {botaoRegiao}
          </>
        );
      }
    }
  }

  return (
    <div className="areas">
      <Mapa
        lang={lang}
        valores={{}}
        selecionado={sel.municipio}
        onSelecionar={escolherMunicipio}
        setores={setores}
        setorSelecionado={sel.setor}
        onSelecionarSetor={escolherSetor}
        setoresIndividuais={mostrarSetoresIndividuais(!!sel.municipio, longe)}
        onLonge={setLonge}
        pinos={pinos}
        pinosVisiveis={inmet}
        pinoSelecionado={pino}
        onSelecionarPino={(id) => setPino((atual) => (atual === id ? null : id))}
        rotuloMapa={t("Mapa dos setores de risco geológico. Use a lista ao lado para percorrer os setores.")}
        rotuloMunicipio={rotuloMunicipio}
        camadas={false}
      >
        <div className="float leg-areas" role="group" aria-labelledby="leg-areas-t">
          <h3 id="leg-areas-t" className="lbl">
            {t("Risco geológico mapeado pelo SGB")}
          </h3>
          <ul>
            <li>
              <Marca grau="alto" />
              {t(ROTULO_GRAU.alto)}
            </li>
            <li>
              <Marca grau="muito_alto" />
              {t(ROTULO_GRAU.muito_alto)}
            </li>
            <li>
              <span className="setor-conta" aria-hidden="true">
                3
              </span>
              {t("número de setores do município")}
            </li>
          </ul>
          <button type="button" className="btn inmet" aria-pressed={inmet} onClick={alternarInmet}>
            {t("Estações do INMET")}
          </button>
          {falhaInmet && (
            <p className="note" role="alert">
              {t("Não foi possível carregar as estações do INMET.")}
            </p>
          )}
        </div>
      </Mapa>
      <aside ref={painel} className="side r" aria-label={t("Áreas de risco")}>
        <p className="aviso-risco" role="note">
          <TriangleAlert aria-hidden="true" />
          <span>
            {t("Mapeamento parcial do SGB: fora dos setores também pode haver risco. Isto é o terreno, não o alerta de chuva de hoje. Em perigo, ligue 199.")}{" "}
            <a href={rota("", lang)}>
              {t("Monitoramento")}
              <span aria-hidden="true"> →</span>
            </a>
          </span>
        </p>
        {conteudo()}
        <p className="disc">
          {t("Sistema de")} <b>{t("apoio à decisão")}</b>
          {t(", de caráter acadêmico. Não constitui alerta oficial e não substitui o Cemaden nem a Defesa Civil.")}
        </p>
      </aside>
    </div>
  );
}
