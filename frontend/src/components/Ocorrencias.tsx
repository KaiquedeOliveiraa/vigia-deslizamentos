import "../styles/cartao.css";
import "../styles/ocorrencias.css";
import { ClipboardList, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import type { T } from "../i18n";
import { carregar, lerOcorrencias, ocorrenciasDoMunicipio, resumoOcorrencias, TIPO_DESLIZAMENTO, type Resultado } from "../lib/dados";
import { formatarData } from "../lib/formato";
import type { Ocorrencia } from "../lib/tipos";

function contador(t: T, lista: Ocorrencia[]) {
  const { deslizamentos, outros, desde } = resumoOcorrencias(lista);
  const d = deslizamentos === 1 ? t("1 deslizamento") : t("{N} deslizamentos", { N: String(deslizamentos) });
  const o = outros === 1 ? t("1 outro evento de chuva") : t("{N} outros eventos de chuva", { N: String(outros) });
  return t("{N} e {N} registrados desde {N}.", { N: [d, o, String(desde?.slice(0, 4))] });
}

export default function Ocorrencias({ t, ibge, nome }: { t: T; ibge: string; nome: string }) {
  const [ocorrencias, setOcorrencias] = useState<Resultado<Ocorrencia[]>>();
  useEffect(() => {
    carregar("ocorrencias.json", lerOcorrencias).then(setOcorrencias);
  }, []);
  const lista = ocorrencias?.ok ? ocorrenciasDoMunicipio(ocorrencias.dados, ibge) : [];
  return (
    <section className="card" aria-labelledby="oc-t">
      <div className="ch">
        <ClipboardList aria-hidden="true" />
        <h2 id="oc-t">{t("Ocorrências registradas — {M}", { M: nome })}</h2>
      </div>
      <p className="sub">{t("Inclui eventos de chuva que não são deslizamento (enxurrada, inundação, alagamento, chuva intensa).")}</p>
      {!ocorrencias && <p className="sub">{t("Carregando os dados…")}</p>}
      {ocorrencias && !ocorrencias.ok && <p className="sub">{t("Não foi possível carregar os dados.")}</p>}
      {ocorrencias?.ok && lista.length === 0 && <p className="sub">{t("Nenhuma ocorrência registrada")}</p>}
      {lista.length > 0 && (
        <>
          <p className="sub">{contador(t, lista)}</p>
          <div className="ocs-rol" tabIndex={0} role="region" aria-labelledby="oc-t">
            <ul className="ocs">
              {lista.map((o) => {
                const desl = o.tipo === TIPO_DESLIZAMENTO;
                return (
                  <li key={o.fonte} className={desl ? "desl" : undefined}>
                    <span className="lbl">
                      <time dateTime={o.data}>{formatarData(o.data)}</time> · {desl && <TriangleAlert aria-hidden="true" />}
                      {t(o.tipo)}
                    </span>
                    <p>{o.descricao}</p>
                    <span className="note">
                      {t("Fonte:")} {o.fonte}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        </>
      )}
      {ocorrencias?.ok && (
        <p className="note">{t("Fonte: Atlas Digital de Desastres (MIDR/Sedec), 1991–2025. Só eventos ligados a chuva.")}</p>
      )}
    </section>
  );
}
