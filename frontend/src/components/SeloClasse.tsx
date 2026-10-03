import type { ReactNode } from "react";
import { infoClasse, NAO_MONITORADO, type IconeClasse, type NumeroClasse } from "../lib/classes";

// Desenhos do protótipo (24×24, traço): cada classe tem uma forma própria, não só a cor (RN03).
const DESENHOS: Record<IconeClasse, ReactNode> = {
  "circulo-check": (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12.5 2.8 2.8L16.5 9.5" />
    </>
  ),
  olho: (
    <>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  "triangulo-exclamacao": <path d="M12 3.5 2.5 20h19zM12 10v4.5M12 17.3v.2" />,
  "triangulo-exclamacao-dupla": <path d="M12 3.5 2.5 20h19zM10 10v4.5M14 10v4.5M10 17.3v.2M14 17.3v.2" />,
  "octogono-exclamacao": <path d="M8.2 2.5h7.6l5.7 5.7v7.6l-5.7 5.7H8.2l-5.7-5.7V8.2zM12 7.5v6M12 16.5v.2" />,
  "octogono-x": <path d="M8.2 2.5h7.6l5.7 5.7v7.6l-5.7 5.7H8.2l-5.7-5.7V8.2zM8.5 8.5l7 7M15.5 8.5l-7 7" />,
};

interface Props {
  /** `null`: sem classe (não monitorado ou sem dados), só a cor `risk-nm`. */
  classe: NumeroClasse | null;
  grande?: boolean;
}

/** Selo da classe: cor + ícone de forma distinta. Decorativo: o nome da classe vem sempre ao lado. */
export default function SeloClasse({ classe, grande = false }: Props) {
  const info = classe ? infoClasse(classe) : null;
  return (
    <span
      className={grande ? "swi big" : "swi"}
      style={info ? { background: info.cor, color: info.corIcone } : { background: NAO_MONITORADO.cor }}
      aria-hidden="true"
    >
      {info && (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
          {DESENHOS[info.icone]}
        </svg>
      )}
    </span>
  );
}
