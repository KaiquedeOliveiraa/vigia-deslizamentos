/** Lê `mensagem` no leitor de tela pela região aria-live do Base.astro (já traduzida por quem chama). */
export function anunciar(mensagem: string): void {
  const regiao = document.getElementById("anuncio");
  if (!regiao) return;
  // Esvazia antes para a mesma mensagem ser lida de novo.
  regiao.textContent = "";
  setTimeout(() => {
    regiao.textContent = mensagem;
  }, 30);
}
