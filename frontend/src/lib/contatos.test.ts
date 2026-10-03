import { describe, expect, it } from "vitest";
import contatos from "../fixtures/contatos.exemplo.json";
import { tradutor } from "../i18n";
import { lerContatos } from "./dados";
import { filtrarContatos, hrefSite, hrefTelefone, urlComoChegar } from "./contatos";

const pt = tradutor("pt");
const verificados = (() => {
  const r = lerContatos(contatos);
  if (!r.ok) throw new Error(r.erro);
  return r.dados;
})();
const ibirama = verificados[0];

describe("Como chegar", () => {
  it("busca o endereço no Google Maps, codificado e sem o travessão", () => {
    expect(urlComoChegar(ibirama)).toBe(
      "https://www.google.com/maps/search/?api=1&query=Rua%20Prof.%20Gertrud%20Aichinger%2C%20272%2C%20Centro%2C%20Ibirama%2FSC%2C%2089140-000",
    );
  });

  it("sem endereço, busca a Defesa Civil do município", () => {
    expect(urlComoChegar({ ...ibirama, endereco: null })).toBe(
      "https://www.google.com/maps/search/?api=1&query=Defesa%20Civil%20Ibirama%20SC",
    );
  });
});

describe("links de telefone e site", () => {
  it("tel: só com dígitos e o +55 nos números com DDD", () => {
    expect(hrefTelefone("(47) 98838-5645")).toBe("tel:+5547988385645");
    expect(hrefTelefone("(47) 3357-1234")).toBe("tel:+554733571234");
    expect(hrefTelefone("199")).toBe("tel:199");
  });

  it("site sem esquema ganha https://", () => {
    expect(hrefSite("www.defesacivilibirama.com.br")).toBe("https://www.defesacivilibirama.com.br");
    expect(hrefSite("http://exemplo.sc.gov.br")).toBe("http://exemplo.sc.gov.br");
  });
});

describe("filtro Seu município", () => {
  it("Todos: nada esmaecido, sem aviso", () => {
    expect(filtrarContatos(pt, verificados, "", "")).toEqual({ esmaecidos: [], aviso: null });
  });

  it("município com contato: esmaece os outros", () => {
    const lista = [...verificados, { ...ibirama, ibge: "1", nome: "Outro" }];
    expect(filtrarContatos(pt, lista, "4206900", "Ibirama")).toEqual({ esmaecidos: ["1"], aviso: null });
  });

  it("município sem contato verificado: esmaece todos e aponta o 199", () => {
    expect(filtrarContatos(pt, verificados, "4219408", "Witmarsum")).toEqual({
      esmaecidos: ["4206900"],
      aviso: "Ainda não há contato verificado da Defesa Civil de Witmarsum. Em perigo, ligue 199.",
    });
  });
});
