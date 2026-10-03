import "../styles/estacoes.css";
import { MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import geojson from "../data/municipios.geojson?raw";
import { tradutor } from "../i18n";
import { carregar, lerEstacoes, type Resultado } from "../lib/dados";
import { ordenarPorDistancia, rotuloEstacao, textoDistancia } from "../lib/estacoes";
import { formatarCoord } from "../lib/formato";
import type { FeicaoMunicipio } from "../lib/mapa";
import type { Idioma } from "../lib/preferencias";
import type { Estacao } from "../lib/tipos";
import EstadoCarregamento from "./EstadoCarregamento";
import Mapa, { type Pino } from "./Mapa";

const NOMES = new Map((JSON.parse(geojson).features as FeicaoMunicipio[]).map((f) => [f.properties.ibge, f.properties.nome]));
const nome = (ibge: string) => NOMES.get(ibge) ?? ibge;

/** Estações automáticas do INMET da região (RF09): pins no mapa em branco e lista à direita. */
export default function Estacoes({ lang }: { lang: Idioma }) {
  const t = tradutor(lang);
  const [carga, setCarga] = useState<Resultado<Estacao[]>>();
  const [selecionada, setSelecionada] = useState<string | null>(null);

  useEffect(() => {
    carregar("estacoes.json", lerEstacoes).then(setCarga);
  }, []);

  if (!carga?.ok) return <EstadoCarregamento t={t} falhou={!!carga} />;

  const estacoes = ordenarPorDistancia(carga.dados);
  const alternar = (codigo: string) => setSelecionada((atual) => (atual === codigo ? null : codigo));
  const distancia = (e: Estacao) => textoDistancia(t, e.distancia_km, nome(e.ibge_referencia));
  const pinos: Pino[] = estacoes.map((e) => ({
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
  }));

  return (
    <div className="est">
      <Mapa lang={lang} valores={{}} camadas={false} pinos={pinos} pinoSelecionado={selecionada} onSelecionarPino={alternar} />
      <aside className="side r" aria-labelledby="titulo-estacoes">
        <div>
          <h2 id="titulo-estacoes" className="lbl">
            {t("Estações de monitoramento")}
          </h2>
          <p className="note">
            {t(
              "Estações automáticas do INMET mais próximas dos municípios monitorados. Nenhuma fica dentro deles: cada uma mostra a distância até o município de referência. Toque num pin ou na lista para localizar.",
            )}
          </p>
        </div>
        <ul className="lst">
          {estacoes.map((e) => (
            <li key={e.codigo}>
              <button type="button" className={e.codigo === selecionada ? "on" : undefined} aria-pressed={e.codigo === selecionada} onClick={() => alternar(e.codigo)}>
                <MapPin aria-hidden="true" />
                <span>
                  {e.nome}
                  <small>
                    {distancia(e)} · INMET {e.codigo}
                  </small>
                  <small className="mono">{formatarCoord(e.lat, e.lon, t)}</small>
                </span>
              </button>
            </li>
          ))}
        </ul>
        <p className="note">
          {t("Fonte: cadastro de estações automáticas do INMET. A distância é medida até o centro do município mais próximo de cada estação.")}
        </p>
      </aside>
    </div>
  );
}
