// Tipos dos arquivos publicados, conforme docs/contratos-de-dados.md e docs/indices.schema.json.

export interface Prob {
  pontuais: number;
  esparsos: number;
  generalizados: number;
}

export interface Dia {
  dia_alvo: string;
  d: number;
  indice: number;
  classe: number;
  efr_mm: number;
  rtotal_mm: number;
  n_membros: number;
  prob: Prob;
}

export interface HistoricoItem {
  dia_alvo: string;
  indice: number;
  classe: number;
}

export interface ChuvaAcum {
  "24h": number;
  "48h": number;
  "72h": number;
  "96h": number;
}

export interface Municipio {
  ibge: string;
  nome: string;
  limiar_mm: number;
  fonte_limiar: string;
  mv_h: number;
  dias: Dia[];
  historico: HistoricoItem[];
  chuva_acum_mm: ChuvaAcum;
}

export interface Indices {
  schema_version: number;
  gerado_em: string;
  dia_alvo_d0: string;
  municipios_sem_dados: string[];
  municipios: Municipio[];
}

export interface Ocorrencia {
  ibge: string;
  data: string;
  tipo: string;
  descricao: string;
  fonte: string;
}

/** Estação regional: `ibge_referencia` é o município mais próximo, não aquele onde a estação fica. */
export interface Estacao {
  codigo: string;
  nome: string;
  ibge_referencia: string;
  distancia_km: number;
  lat: number;
  lon: number;
}

export interface Contato {
  ibge: string;
  nome: string;
  verificado: boolean;
  responsavel: string | null;
  telefone: string | null;
  email: string | null;
  endereco: string | null;
  site: string | null;
}
