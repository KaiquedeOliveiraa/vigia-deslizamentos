import { Search } from "lucide-react";
import { useId, useRef, useState, type KeyboardEvent } from "react";
import { tradutor } from "../i18n";
import { infoClasse, SEM_DADOS } from "../lib/classes";
import { formatarIndice } from "../lib/formato";
import { destacar } from "../lib/mapa";
import type { Idioma } from "../lib/preferencias";
import { buscar } from "../lib/texto";
import type { IndiceClasse } from "../lib/tipos";
import SeloClasse from "./SeloClasse";

export interface ItemBusca {
  ibge: string;
  nome: string;
  /** `null` = sem dados. */
  valor: IndiceClasse | null;
}

interface Props {
  lang: Idioma;
  municipios: readonly ItemBusca[];
  aoEscolher: (ibge: string) => void;
}

function Nome({ nome, termo }: { nome: string; termo: string }) {
  const partes = destacar(nome, termo);
  if (!partes) return nome;
  const [antes, achado, depois] = partes;
  return (
    <>
      {antes}
      <mark>{achado}</mark>
      {depois}
    </>
  );
}

/** Lupa no canto do mapa que abre a busca de município por nome, sem acento (combobox). */
export default function Busca({ lang, municipios, aoEscolher }: Props) {
  const t = tradutor(lang);
  const base = useId();
  const [aberta, setAberta] = useState(false);
  const [termo, setTermo] = useState("");
  const [ativo, setAtivo] = useState(0);
  const lupa = useRef<HTMLButtonElement>(null);
  const resultados = buscar([...municipios], termo);
  const opcao = (i: number) => `${base}-op-${i}`;

  function alternar() {
    setAberta(!aberta);
    setTermo("");
    setAtivo(0);
  }

  function fechar() {
    setAberta(false);
    lupa.current?.focus();
  }

  function escolher(m: ItemBusca) {
    fechar();
    aoEscolher(m.ibge);
  }

  function tecla(e: KeyboardEvent) {
    if (e.key === "ArrowDown") setAtivo(Math.min(ativo + 1, resultados.length - 1));
    else if (e.key === "ArrowUp") setAtivo(Math.max(ativo - 1, 0));
    else if (e.key === "Enter" && resultados[ativo]) escolher(resultados[ativo]);
    else if (e.key === "Escape") fechar();
    else return;
    e.preventDefault();
  }

  return (
    <div className={aberta ? "busca open" : "busca"}>
      <button ref={lupa} type="button" className="go" aria-label={t("Buscar município")} aria-expanded={aberta} onClick={alternar}>
        <Search aria-hidden="true" />
      </button>
      {aberta && (
        <div className="box">
          <input
            type="search"
            autoFocus
            role="combobox"
            aria-expanded="true"
            aria-controls={`${base}-lista`}
            aria-autocomplete="list"
            aria-activedescendant={resultados.length ? opcao(ativo) : undefined}
            aria-label={t("Nome do município")}
            placeholder={t("Buscar município…")}
            value={termo}
            onChange={(e) => {
              setTermo(e.target.value);
              setAtivo(0);
            }}
            onKeyDown={tecla}
          />
          <ul role="listbox" id={`${base}-lista`} aria-label={t("Municípios")}>
            {resultados.map((m, i) => {
              const n = m.valor && m.valor.classe;
              return (
                <li
                  key={m.ibge}
                  id={opcao(i)}
                  role="option"
                  aria-selected={i === ativo}
                  className={i === ativo ? "hi" : undefined}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => escolher(m)}
                >
                  <SeloClasse classe={n} />
                  <span>
                    <Nome nome={m.nome} termo={termo} /> <small>{t(n ? infoClasse(n).nome : SEM_DADOS.nome)}</small>
                  </span>
                  {m.valor && <span className="num">{formatarIndice(m.valor.indice)}</span>}
                </li>
              );
            })}
          </ul>
          {resultados.length === 0 && (
            <p className="empty" role="status">
              {t("Nenhum município monitorado com esse nome.")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
