import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { describe, expect, it } from "vitest";
import schema from "../../../docs/indices.schema.json";
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
