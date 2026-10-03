import { useEffect, useRef, useState } from "react";
import geojson from "../data/municipios.geojson?raw";
import { carregar, lerIndices } from "../lib/dados";
import { mensagemSelecao, valoresDoDia, type FeicaoMunicipio } from "../lib/mapa";
import type { Idioma } from "../lib/preferencias";
import type { Indices } from "../lib/tipos";
import { tradutor } from "../i18n";
import { anunciar } from "./anunciar";
import Busca from "./Busca";
import Legenda from "./Legenda";
import Mapa, { type MapaApi } from "./Mapa";
import Previsoes, { FaixaPrevisao } from "./Previsoes";

const MONITORADOS = (JSON.parse(geojson).features as FeicaoMunicipio[]).filter((f) => f.properties.monitorado);

/** Provisório (só em desenvolvimento): mostra os componentes do mapa até a Tarefa 8 montar a tela. */
export default function DemoMapa({ lang }: { lang: Idioma }) {
  const t = tradutor(lang);
  const [indices, setIndices] = useState<Indices>();
  const [d, setD] = useState(0);
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const mapa = useRef<MapaApi>(null);

  useEffect(() => {
    carregar("indices.json", lerIndices).then((r) => r.ok && setIndices(r.dados));
  }, []);
  if (!indices) return null;

  const valores = valoresDoDia(indices, d);
  const dias = indices.municipios[0].dias.map((x) => x.dia_alvo);
  const nome = (ibge: string) => MONITORADOS.find((f) => f.properties.ibge === ibge)!.properties.nome;
  const selecionar = (ibge: string) => {
    setSelecionado(ibge);
    anunciar(mensagemSelecao(t, nome(ibge), valores[ibge]));
  };

  return (
    <Mapa ref={mapa} lang={lang} valores={valores} selecionado={selecionado} onSelecionar={selecionar}>
      <Previsoes lang={lang} dias={dias} d={d} aoMudar={setD} />
      <FaixaPrevisao lang={lang} dia={dias[d]} d={d} />
      <Legenda lang={lang} />
      <Busca
        lang={lang}
        municipios={MONITORADOS.map((f) => ({ ...f.properties, indice: valores[f.properties.ibge] ?? null }))}
        aoEscolher={(ibge) => {
          selecionar(ibge);
          mapa.current?.piscar(ibge);
        }}
      />
    </Mapa>
  );
}
