import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { describe, expect, it } from "vitest";
import schema from "../../../docs/indices.schema.json";
import { lerContatos, lerEstacoes, lerIndices, lerOcorrencias, type Resultado } from "../lib/dados";
import indices from "./indices.exemplo.json";

describe("indices.exemplo.json", () => {
  it("segue docs/indices.schema.json", () => {
    const ajv = new Ajv2020({ allErrors: true });
    addFormats(ajv);
    const valido = ajv.validate(schema, indices);
    expect(ajv.errors ?? []).toEqual([]);
    expect(valido).toBe(true);
  });
});

// Arquivos servidos em produção (frontend/public/data): cada um passa pelo leitor do contrato.
// indices.json chega por commit automático do backend: sem leitor aqui, a primeira publicação quebraria o CI do Pages.
const LEITORES: Record<string, (json: unknown) => Resultado<unknown>> = {
  "contatos.json": lerContatos,
  "estacoes.json": lerEstacoes,
  "indices.json": lerIndices,
  "ocorrencias.json": lerOcorrencias,
};
const PUBLICADOS = import.meta.glob<unknown>("../../public/data/*.json", { eager: true, import: "default" });

describe("public/data/*.json", () => {
  const arquivos = Object.entries(PUBLICADOS).map(([caminho, json]) => [caminho.split("/").pop() ?? caminho, json] as const);

  it("há arquivos publicados e todos têm leitor", () => {
    expect(arquivos.length).toBeGreaterThan(0);
    expect(arquivos.map(([nome]) => nome).filter((nome) => !(nome in LEITORES))).toEqual([]);
  });

  it.each(arquivos)("%s segue o contrato", (nome, json) => {
    expect(LEITORES[nome](json)).toEqual({ ok: true, dados: expect.anything() });
  });
});
