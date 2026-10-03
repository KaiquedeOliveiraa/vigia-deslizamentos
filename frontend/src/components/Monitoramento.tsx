import "../styles/monitoramento.css";
import { Check, CloudRain, Share2, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { tradutor, type T } from "../i18n";
import { emAlerta, infoClasse, type NumeroClasse } from "../lib/classes";
import { carregar, estadoMunicipio, lerIndices, type Resultado } from "../lib/dados";
import { formatarData, formatarIndice, formatarMm, formatarRazao } from "../lib/formato";
import { mensagemSelecao, valoresDoDia } from "../lib/mapa";
import { municipioInicial, resumo, variaveis, type Variaveis } from "../lib/monitoramento";
import { MONITORADOS, NOMES } from "../lib/municipios";
import type { Idioma } from "../lib/preferencias";
import { rota } from "../lib/telas";
import { textoCompartilhar } from "../lib/texto";
import type { Indices } from "../lib/tipos";
import { anunciar } from "./anunciar";
import Busca from "./Busca";
import { copiarTexto } from "./copiar";
import EstadoCarregamento from "./EstadoCarregamento";
import JanelaTelegram, { DiscoTelegram } from "./JanelaTelegram";
import Legenda from "./Legenda";
import Mapa, { type MapaApi } from "./Mapa";
import Previsoes, { FaixaPrevisao } from "./Previsoes";
import SeloClasse from "./SeloClasse";

const LISTA_NOMES = MONITORADOS.map((m) => m.nome);
const TOAST_MS = 2200;

export default function Monitoramento({ lang }: { lang: Idioma }) {
  const t = tradutor(lang);
  const [carga, setCarga] = useState<Resultado<Indices>>();
  const [d, setD] = useState(0);
  const [selecionado, setSelecionado] = useState<string>();
  const [telegram, setTelegram] = useState(false);
  const [toast, setToast] = useState("");
  const mapa = useRef<MapaApi>(null);

  useEffect(() => {
    carregar("indices.json", lerIndices).then((r) => {
      setCarga(r);
      if (r.ok) setSelecionado(municipioInicial(r.dados));
    });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), TOAST_MS);
    return () => clearTimeout(timer);
  }, [toast]);

  if (!carga?.ok) return <EstadoCarregamento t={t} falhou={!!carga} />;

  const indices = carga.dados;
  const valores = valoresDoDia(indices, d);
  const dias = indices.municipios[0]?.dias.map((x) => x.dia_alvo) ?? [indices.dia_alvo_d0];
  const { emAlerta: nAlerta, total, maior } = resumo(valores);
  const nome = (ibge: string) => NOMES.get(ibge) ?? ibge;

  const selecionar = (ibge: string) => {
    setSelecionado(ibge);
    anunciar(mensagemSelecao(t, nome(ibge), valores[ibge]));
  };

  async function compartilhar(texto: string, aviso: string) {
    const url = location.href;
    if (navigator.share) {
      await navigator.share({ title: "VIGIA", text: texto, url }).catch(() => {});
      return;
    }
    const copiou = await copiarTexto(`${texto} ${url}`);
    const mensagem = copiou ? aviso : t("Não foi possível copiar o link.");
    setToast(mensagem);
    anunciar(mensagem);
  }

  return (
    <div className="mon">
      <Mapa ref={mapa} lang={lang} valores={valores} selecionado={selecionado} onSelecionar={selecionar}>
        <Previsoes lang={lang} dias={dias} d={d} aoMudar={setD} />
        <FaixaPrevisao lang={lang} dia={dias[d]} d={d} />
        <Legenda lang={lang} />
        <Busca
          lang={lang}
          municipios={MONITORADOS.map((m) => ({ ...m, valor: valores[m.ibge] ?? null }))}
          aoEscolher={(ibge) => {
            selecionar(ibge);
            mapa.current?.piscar(ibge);
          }}
        />
        <div className={toast ? "toast on" : "toast"} aria-hidden="true">
          {toast}
        </div>
        <p className="float resumo">
          <b className={nAlerta ? "al" : undefined}>{nAlerta}</b>{" "}
          {t("de {N} municípios em alerta · maior índice {N}", { N: [String(total), maior === null ? "—" : formatarIndice(maior)] })}
        </p>
      </Mapa>
      {selecionado && (
        <Painel
          t={t}
          lang={lang}
          indices={indices}
          ibge={selecionado}
          nome={nome(selecionado)}
          d={d}
          aoCompartilhar={compartilhar}
          aoTelegram={() => setTelegram(true)}
        />
      )}
      <JanelaTelegram lang={lang} aberto={telegram} aoFechar={() => setTelegram(false)} municipios={LISTA_NOMES} ibge={selecionado} />
    </div>
  );
}

interface PropsPainel {
  t: T;
  lang: Idioma;
  indices: Indices;
  ibge: string;
  nome: string;
  d: number;
  aoCompartilhar: (texto: string, aviso: string) => void;
  aoTelegram: () => void;
}

function Painel({ t, lang, indices, ibge, nome, d, aoCompartilhar, aoTelegram }: PropsPainel) {
  const estado = estadoMunicipio(indices, ibge);
  const municipio = estado.estado === "ok" ? estado.municipio : undefined;
  const dia = municipio?.dias.find((x) => x.d === d);

  return (
    <aside className="side r" aria-label={t("Município selecionado")}>
      <div>
        <span className="lbl">{t("Município selecionado")}</span>
        <h2 className="mname">{nome}</h2>
        {municipio && dia ? <Indice t={t} indice={dia.indice} classe={dia.classe} dia={d ? dia.dia_alvo : undefined} /> : <span className="pill">{t("sem dados")}</span>}
      </div>
      {municipio && dia && (
        <>
          <ListaVariaveis t={t} {...variaveis(municipio, dia)} />
          <div className="acts">
            <button
              type="button"
              className="btn pri"
              onClick={() => {
                const aviso = t("Link copiado: “{M} — {C} ({N})”", { M: nome, C: infoClasse(dia.classe).nome, N: formatarIndice(dia.indice) });
                aoCompartilhar(textoCompartilhar(nome, dia, t), aviso);
              }}
            >
              <Share2 aria-hidden="true" />
              {t("Compartilhar")}
            </button>
            <a className="btn" href={`${rota("simulacao", lang)}?municipio=${ibge}`}>
              <CloudRain aria-hidden="true" />
              {t("Simular chuva")}
            </a>
          </div>
        </>
      )}
      <button type="button" className="btn tgbtn" onClick={aoTelegram}>
        <DiscoTelegram />
        {t("Receber alertas de {M} no Telegram", { M: nome })}
      </button>
      <p className="disc">
        {t("Sistema de")} <b>{t("apoio à decisão")}</b>
        {t(", de caráter acadêmico. Não constitui alerta oficial e não substitui o Cemaden nem a Defesa Civil.")}
      </p>
    </aside>
  );
}

/** Pílula de alerta, índice grande e "índice de risco · classe[ · previsão dd/mm/aa]". */
function Indice({ t, indice, classe, dia }: { t: T; indice: number; classe: NumeroClasse; dia?: string }) {
  const nomeClasse = infoClasse(classe).nome;
  const alerta = emAlerta(indice);
  return (
    <>
      <span className={alerta ? "pill al" : "pill"}>
        {alerta ? <TriangleAlert aria-hidden="true" /> : <Check aria-hidden="true" />}
        {t(alerta ? "Em alerta" : "Sem alerta")} <span className="mono">{t("classe {C}", { C: nomeClasse })}</span>
      </span>
      <div className="bigidx">
        <SeloClasse classe={classe} grande />
        <b className="num">{formatarIndice(indice)}</b>
      </div>
      <div className="bigsub">
        {dia
          ? t("índice de risco · {C} · previsão {N}", { C: nomeClasse, N: formatarData(dia, "curto") })
          : t("índice de risco · {C}", { C: nomeClasse })}
      </div>
    </>
  );
}

function ListaVariaveis({ t, efr_mm, limiar_mm, razao, barra, n_membros }: { t: T } & Variaveis) {
  const linhas: [string, string, boolean][] = [
    [t("Chuva efetiva antecedente"), `${formatarMm(efr_mm)} mm`, true],
    [t("Limiar crítico do município"), `${formatarMm(limiar_mm)} mm`, false],
    [t("Razão chuva / limiar"), formatarRazao(razao), true],
    [t("Membros de ensemble"), String(n_membros), false],
  ];
  return (
    <dl className="vars">
      {linhas.map(([rotulo, valor, comBarra]) => (
        <div key={rotulo} className={comBarra ? "var com-barra" : "var"} style={comBarra ? ({ "--barra": `${barra}%` } as CSSProperties) : undefined}>
          <dt>{rotulo}</dt>
          <dd className="num">{valor}</dd>
        </div>
      ))}
    </dl>
  );
}
