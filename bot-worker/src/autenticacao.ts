const codificador = new TextEncoder();

/** Comparação em tempo constante; `false` para `null`, segredo esperado vazio/ausente ou tamanho diferente. */
export function segredoConfere(recebido: string | null, esperado: string | undefined): boolean {
  if (recebido === null || !esperado) return false;
  const a = codificador.encode(recebido);
  const b = codificador.encode(esperado);
  if (a.byteLength !== b.byteLength) return false;
  return crypto.subtle.timingSafeEqual(a, b);
}

/** Extrai o segredo de `Authorization: Bearer <segredo>`; `null` se ausente ou malformado. */
export function segredoDoBearer(cabecalho: string | null): string | null {
  if (cabecalho === null) return null;
  const partes = /^Bearer (.+)$/.exec(cabecalho);
  return partes ? partes[1]! : null;
}
