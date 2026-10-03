import type { T } from "../i18n";

/** Enquanto um arquivo de dados carrega, ou quando ele falha: a tela nunca fica em branco. */
export default function EstadoCarregamento({ t, falhou }: { t: T; falhou: boolean }) {
  return falhou ? (
    <p className="estado-carga erro" role="alert">
      {t("Não foi possível carregar os dados.")}
    </p>
  ) : (
    <p className="estado-carga" role="status">
      {t("Carregando os dados…")}
    </p>
  );
}
