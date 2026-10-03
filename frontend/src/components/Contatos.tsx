import "../styles/contatos.css";
import { Bell, Copy, ExternalLink, Mail, MapPin, Phone, Route, User } from "lucide-react";
import { useEffect, useState, type ChangeEvent } from "react";
import { tradutor } from "../i18n";
import { filtrarContatos, hrefSite, hrefTelefone, urlComoChegar } from "../lib/contatos";
import { carregar, lerContatos } from "../lib/dados";
import type { Idioma } from "../lib/preferencias";
import type { Contato } from "../lib/tipos";
import { anunciar } from "./anunciar";
import BannerTelegram from "./BannerTelegram";
import { copiarTexto } from "./copiar";

interface Props {
  lang: Idioma;
  municipios: readonly { ibge: string; nome: string }[];
}

const EMERGENCIAS = [
  { numero: "199", href: "tel:199", rotulo: "Defesa Civil", Icone: Phone },
  { numero: "193", href: "tel:193", rotulo: "Bombeiros", Icone: Phone },
  { numero: "192", href: "tel:192", rotulo: "SAMU", Icone: Phone },
  { numero: "40199", href: "sms:40199", rotulo: "SMS com seu CEP para receber alertas", Icone: Bell },
] as const;

const semMovimento = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Contatos (RF12): números de emergência e a Defesa Civil de cada município (só verificados, RN09). */
export default function Contatos({ lang, municipios }: Props) {
  const t = tradutor(lang);
  const [contatos, setContatos] = useState<Contato[]>([]);
  const [escolhido, setEscolhido] = useState("");
  const [copiado, setCopiado] = useState<string>();

  useEffect(() => {
    carregar("contatos.json", lerContatos).then((r) => r.ok && setContatos(r.dados));
  }, []);

  // Depois de renderizar: o aviso só existe no DOM depois da escolha.
  useEffect(() => {
    if (!escolhido) return;
    const alvo = document.getElementById("aviso-municipio") ?? document.getElementById(`cc-${escolhido}`);
    alvo?.scrollIntoView({ block: "nearest", behavior: semMovimento() ? "auto" : "smooth" });
  }, [escolhido]);

  const nomeEscolhido = municipios.find((m) => m.ibge === escolhido)?.nome ?? "";
  const filtro = filtrarContatos(t, contatos, escolhido, nomeEscolhido);

  const escolher = (e: ChangeEvent<HTMLSelectElement>) => {
    const ibge = e.target.value;
    setEscolhido(ibge);
    if (!ibge) return;
    const nome = municipios.find((m) => m.ibge === ibge)!.nome;
    const aviso = filtrarContatos(t, contatos, ibge, nome).aviso;
    anunciar(aviso ?? t("Mostrando {M}", { M: nome }));
  };

  const copiar = async (c: Contato) => {
    if (!(await copiarTexto(c.telefone!))) return;
    setCopiado(c.ibge);
    anunciar(t("Telefone copiado"));
  };

  return (
    <div className="cont">
      <div className="ctop">
        <div className="lbl">{t("Contatos")}</div>
        <h1>{t("Defesa Civil e emergência")}</h1>
        <p>{t("Em perigo, ligue {N} de qualquer lugar. Os números funcionam {N} horas.", { N: ["199", "24"] })}</p>
      </div>

      <ul className="emerg" aria-label={t("Números de emergência")}>
        {EMERGENCIAS.map(({ numero, href, rotulo, Icone }) => (
          <li key={numero} className="em">
            <Icone aria-hidden="true" />
            <div>
              <b>{numero}</b>
              <a href={href} aria-label={`${numero} — ${t(rotulo)}`}>
                {t(rotulo)}
              </a>
            </div>
          </li>
        ))}
      </ul>

      <BannerTelegram lang={lang} municipios={municipios.map((m) => m.nome)} />

      <div className="filtro">
        <label className="lbl" htmlFor="filtro-municipio">
          {t("Seu município")}
        </label>
        <select id="filtro-municipio" value={escolhido} onChange={escolher}>
          <option value="">{t("Todos")}</option>
          {municipios.map((m) => (
            <option key={m.ibge} value={m.ibge}>
              {m.nome}
            </option>
          ))}
        </select>
      </div>

      {filtro.aviso && (
        <p id="aviso-municipio" className="aviso-mun">
          <Phone aria-hidden="true" />
          {filtro.aviso}
        </p>
      )}

      <div className="cgrid">
        {contatos.map((c) => (
          <article key={c.ibge} id={`cc-${c.ibge}`} className={filtro.esmaecidos.includes(c.ibge) ? "cc dim" : "cc"} aria-labelledby={`cc-t-${c.ibge}`}>
            <h2 id={`cc-t-${c.ibge}`}>
              {c.nome}
              <span className="tag ok">{t("verificado")}</span>
            </h2>
            <dl>
              <dt>
                <User aria-hidden="true" />
                <span className="sr-only">{t("Responsável")}</span>
              </dt>
              <dd>
                {c.responsavel ?? <span className="pend-t">{t("Nome do coordenador(a) a confirmar")}</span>}
                <small>{t("Coordenador(a) municipal de Defesa Civil")}</small>
              </dd>
              {c.telefone && (
                <>
                  <dt>
                    <Phone aria-hidden="true" />
                    <span className="sr-only">{t("Telefone")}</span>
                  </dt>
                  <dd>
                    <a className="ph" href={hrefTelefone(c.telefone)}>
                      {c.telefone}
                    </a>
                  </dd>
                </>
              )}
              {c.email && (
                <>
                  <dt>
                    <Mail aria-hidden="true" />
                    <span className="sr-only">{t("E-mail")}</span>
                  </dt>
                  <dd>
                    <a href={`mailto:${c.email}`}>{c.email}</a>
                  </dd>
                </>
              )}
              {c.endereco && (
                <>
                  <dt>
                    <MapPin aria-hidden="true" />
                    <span className="sr-only">{t("Endereço")}</span>
                  </dt>
                  <dd>{c.endereco}</dd>
                </>
              )}
            </dl>
            <div className="acts">
              <a
                className="btn pri"
                href={urlComoChegar(c)}
                target="_blank"
                rel="noopener"
                aria-label={t("Como chegar à Defesa Civil de {M} no Google Maps (abre em nova aba)", { M: c.nome })}
              >
                <Route aria-hidden="true" />
                {t("Como chegar")}
              </a>
              {c.telefone ? (
                <button type="button" className="btn" aria-label={t("Copiar telefone da Defesa Civil de {M}", { M: c.nome })} onClick={() => copiar(c)}>
                  <Copy aria-hidden="true" />
                  {copiado === c.ibge ? t("Copiado") : t("Copiar telefone")}
                </button>
              ) : (
                c.site && (
                  <a className="btn" href={hrefSite(c.site)} target="_blank" rel="noopener" aria-label={t("Site da prefeitura de {M} (abre em nova aba)", { M: c.nome })}>
                    <ExternalLink aria-hidden="true" />
                    {t("Site da prefeitura")}
                  </a>
                )
              )}
            </div>
          </article>
        ))}
      </div>

      <p className="cnote">{t('"Como chegar" abre o Google Maps.')}</p>
    </div>
  );
}
