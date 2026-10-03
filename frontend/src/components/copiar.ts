/** Copia `texto`; fora de contexto seguro não há navigator.clipboard: copia pela seleção. Diz se conseguiu. */
export async function copiarTexto(texto: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    const campo = Object.assign(document.createElement("textarea"), { value: texto });
    document.body.append(campo);
    campo.select();
    const ok = document.execCommand("copy");
    campo.remove();
    return ok;
  }
}
