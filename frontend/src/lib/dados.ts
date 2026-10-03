import { urlDados } from "./config";
import type { Contato, Estacao, Indices, Municipio, Ocorrencia } from "./tipos";

// Em execução só se confere schema_version e a presença dos campos usados;
// a validação completa contra docs/indices.schema.json fica nos testes.

export type Resultado<T> = { ok: true; dados: T } | { ok: false; erro: string };

const SCHEMA_VERSION = 1;
const LIMITE_MS = 12 * 60 * 60 * 1000;

const CAMPOS_RAIZ = ["gerado_em", "dia_alvo_d0", "municipios_sem_dados", "municipios"];
const CAMPOS_MUNICIPIO = ["ibge", "nome", "limiar_mm", "mv_h", "dias", "historico", "chuva_acum_mm"];
const CAMPOS_DIA = ["dia_alvo", "d", "indice", "classe", "efr_mm", "rtotal_mm", "prob"];
const CAMPOS_OCORRENCIA = ["ibge", "data", "tipo", "descricao", "fonte"];
const CAMPOS_ESTACAO = ["codigo", "nome", "ibge_referencia", "distancia_km", "lat", "lon"];
const CAMPOS_CONTATO = ["ibge", "nome", "verificado"];

const erro = (mensagem: string): Resultado<never> => ({ ok: false, erro: mensagem });

function faltando(item: unknown, campos: string[]): string | undefined {
  if (typeof item !== "object" || item === null) return "objeto";
  return campos.find((c) => !(c in item));
}

function lerLista<T>(json: unknown, campos: string[], nome: string): Resultado<T[]> {
  if (!Array.isArray(json)) return erro(`${nome}: a raiz deve ser uma lista`);
  for (const item of json) {
    const campo = faltando(item, campos);
    if (campo) return erro(`${nome}: item sem o campo "${campo}"`);
  }
  return { ok: true, dados: json as T[] };
}

export function lerIndices(json: unknown): Resultado<Indices> {
  const raiz = json as Partial<Indices> | null;
  if (raiz?.schema_version !== SCHEMA_VERSION) {
    return erro(`indices.json: schema_version desconhecido (${String(raiz?.schema_version)})`);
  }
  const lista = (v: unknown, nome: string) => (Array.isArray(v) ? undefined : nome);
  const faltandoNoMunicipio = (m: Municipio) =>
    faltando(m, CAMPOS_MUNICIPIO) ?? lista(m.dias, "dias") ?? m.dias.map((d) => faltando(d, CAMPOS_DIA)).find(Boolean);
  const campo =
    faltando(raiz, CAMPOS_RAIZ) ?? lista(raiz.municipios, "municipios") ?? raiz.municipios!.map(faltandoNoMunicipio).find(Boolean);
  if (campo) return erro(`indices.json: falta o campo "${campo}"`);
  return { ok: true, dados: raiz as Indices };
}

export const lerOcorrencias = (json: unknown) => lerLista<Ocorrencia>(json, CAMPOS_OCORRENCIA, "ocorrencias.json");

/** Ocorrências do município, da mais recente para a mais antiga. */
export const ocorrenciasDoMunicipio = (lista: Ocorrencia[], ibge: string): Ocorrencia[] =>
  lista.filter((o) => o.ibge === ibge).sort((a, b) => b.data.localeCompare(a.data));

export const lerEstacoes = (json: unknown) => lerLista<Estacao>(json, CAMPOS_ESTACAO, "estacoes.json");

/** Só os contatos confirmados com a prefeitura (RN09). */
export function lerContatos(json: unknown): Resultado<Contato[]> {
  const r = lerLista<Contato>(json, CAMPOS_CONTATO, "contatos.json");
  return r.ok ? { ok: true, dados: r.dados.filter((c) => c.verificado === true) } : r;
}

/** RN12: mais de 12 h desde `gerado_em`. */
export const desatualizado = (gerado_em: string, agora: Date): boolean =>
  agora.getTime() - new Date(gerado_em).getTime() > LIMITE_MS;

export type EstadoMunicipio = { estado: "ok"; municipio: Municipio } | { estado: "sem dados" };

export function estadoMunicipio(indices: Indices, ibge: string): EstadoMunicipio {
  const municipio = indices.municipios_sem_dados.includes(ibge) ? undefined : indices.municipios.find((m) => m.ibge === ibge);
  return municipio ? { estado: "ok", municipio } : { estado: "sem dados" };
}

/** Busca `arquivo` em urlDados e aplica `ler`; nunca lança. `buscar` é injetado para testar sem rede. */
export async function carregar<T>(
  arquivo: string,
  ler: (json: unknown) => Resultado<T>,
  buscar: (url: string) => Promise<Response> = fetch,
): Promise<Resultado<T>> {
  try {
    const resposta = await buscar(urlDados(arquivo));
    if (!resposta.ok) return erro(`${arquivo}: HTTP ${resposta.status}`);
    return ler(await resposta.json());
  } catch (e) {
    return erro(`${arquivo}: ${e instanceof Error ? e.message : String(e)}`);
  }
}
