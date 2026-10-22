import { describe, expect, it } from "vitest";
import ES from "../i18n/es.json";
import { BOMBEIROS, EMERGENCIA, FASES, FONTES, MOCHILA, NAO_FACA, SECOES, SINAIS } from "./cartilha";

describe("conteúdo da Cartilha", () => {
  it("6 sinais, fases 5/5/2, 11 itens da mochila e 6 'não faça'", () => {
    expect(SINAIS).toHaveLength(6);
    expect(FASES.map((f) => f.blocos.length)).toEqual([5, 5, 2]);
    expect(MOCHILA).toHaveLength(11);
    expect(NAO_FACA).toHaveLength(6);
  });

  it("números de emergência", () => {
    expect([EMERGENCIA, BOMBEIROS]).toEqual(["199", "193"]);
  });

  it("sinais e fases com os textos da spec, na ordem", () => {
    expect(SINAIS.map((s) => s.titulo)).toEqual([
      "Rachaduras novas",
      "Portas e janelas emperrando",
      "Árvores e postes inclinando",
      "Água barrenta minando",
      "Barulhos vindos do chão",
      "Muro estufado",
    ]);
    expect(FASES.map((f) => f.blocos.map((b) => b.texto))).toEqual([
      [
        "Plante grama e árvores pequenas na encosta",
        "Leve a água da chuva e o esgoto para canaletas",
        "Viu sinais de risco? Peça vistoria à Defesa Civil",
        "Alerta por SMS: envie seu CEP para {N}; o alerta automático no celular dispensa cadastro",
        "Deixe a mochila pronta",
      ],
      [
        "Casa em área de risco? Vá para a casa de parentes ou amigos em local seguro",
        "Viu sinais? Saia já e ligue {N} ou {N}",
        "Ajude crianças, idosos e pessoas com dificuldade de locomoção",
        "Siga só avisos oficiais e não repasse boatos",
        "Nunca atravesse rua com água ou lama de deslizamento fluindo",
      ],
      ["Não entre na área atingida sem autorização", "Só volte para casa quando a Defesa Civil liberar"],
    ]);
    expect(FASES[1].blocos[1].vars).toEqual({ N: [EMERGENCIA, BOMBEIROS] });
  });

  it("'Construir na beira do barranco' tem detalhe", () => {
    expect(NAO_FACA.filter((b) => b.detalhe).map((b) => b.texto)).toEqual(["Construir na beira do barranco"]);
  });

  it("toda seção tem fonte; chaves existem em FONTES, URLs https e toda fonte é usada", () => {
    const usadas = SECOES.flatMap((s) => s.fontes);
    expect(SECOES.filter((s) => s.fontes.length < 1)).toEqual([]);
    expect(usadas.filter((k) => !(k in FONTES))).toEqual([]);
    expect(Object.values(FONTES).filter((f) => !f.url.startsWith("https://"))).toEqual([]);
    expect(Object.keys(FONTES).filter((k) => !usadas.includes(k as (typeof usadas)[number]))).toEqual([]);
  });

  it("toda frase tem tradução em es.json", () => {
    const frases = [
      ...SECOES.map((s) => s.rotulo),
      ...SINAIS.flatMap((s) => [s.titulo, s.detalhe]),
      ...FASES.flatMap((f) => [f.rotulo, ...f.blocos.map((b) => b.texto)]),
      ...MOCHILA.map((b) => b.texto),
      ...NAO_FACA.flatMap((b) => [b.texto, ...(b.detalhe ? [b.detalhe] : [])]),
      ...Object.values(FONTES).map((f) => f.nome),
    ];
    expect(frases.filter((f) => !(f in ES))).toEqual([]);
  });
});
