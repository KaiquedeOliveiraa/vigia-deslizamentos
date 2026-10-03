import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

interface Props {
  aberto: boolean;
  aoFechar: () => void;
  /** id do título dentro do diálogo. */
  rotulo: string;
  rotuloFechar: string;
  className?: string;
  children: ReactNode;
}

/**
 * <dialog> nativo em modo modal: o resto da página fica inerte e Esc fecha.
 * Clique no fundo fecha; ao fechar, o foco volta ao botão de origem.
 * Foco inicial: elemento com `data-foco-inicial`, se houver.
 */
export default function Dialogo({ aberto, aoFechar, rotulo, rotuloFechar, className = "", children }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialogo = ref.current;
    if (!aberto || !dialogo) return;
    const origem = document.activeElement as HTMLElement | null;
    dialogo.showModal();
    dialogo.querySelector<HTMLElement>("[data-foco-inicial]")?.focus();
    return () => {
      dialogo.close();
      origem?.focus();
    };
  }, [aberto]);

  return (
    <dialog
      ref={ref}
      className={`dlg ${className}`}
      aria-labelledby={rotulo}
      onClose={aoFechar}
      onClick={(e) => e.target === e.currentTarget && aoFechar()}
    >
      {aberto && (
        <div className="dlg-box">
          <button type="button" className="dlg-x" aria-label={rotuloFechar} onClick={aoFechar}>
            <X aria-hidden="true" />
          </button>
          {children}
        </div>
      )}
    </dialog>
  );
}
