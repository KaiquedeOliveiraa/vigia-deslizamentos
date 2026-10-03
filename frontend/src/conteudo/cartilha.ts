// Textos da Cartilha em português; o espanhol vem do dicionário (src/i18n/es.json) pela própria frase.
// Baseado nas cartilhas da Defesa Civil RJ e do SP Sempre Alerta (links na tela).
import {
  Axe,
  Backpack,
  BatteryCharging,
  Bell,
  Camera,
  Clock,
  DoorOpen,
  Droplet,
  FileText,
  Flashlight,
  House,
  Leaf,
  type LucideIcon,
  Phone,
  Pill,
  Radio,
  Shirt,
  Shovel,
  Trash2,
  TreePalm,
  TriangleAlert,
  Waves,
  Whistle,
  X,
} from "lucide-react";
import type { Vars } from "../i18n";

/** Chave da ilustração de traço do sinal (desenhos no componente Cartilha). */
export type Ilustracao = "racha" | "janela" | "inclina" | "agua" | "estalo" | "muro";

export interface Sinal {
  ilustracao: Ilustracao;
  titulo: string;
  detalhe: string;
}

export interface Bloco {
  icone: LucideIcon;
  texto: string;
  vars?: Vars;
}

export type IdFase = "antes" | "durante" | "depois";

export const EMERGENCIA = "199";

export const SECOES = [
  { id: "sinais", rotulo: "{N}. Sinais" },
  { id: "fases", rotulo: "{N}. O que fazer" },
  { id: "kit", rotulo: "{N}. Mochila" },
  { id: "evitar", rotulo: "{N}. Não faça" },
] as const;

export const SINAIS: readonly Sinal[] = [
  { ilustracao: "racha", titulo: "Rachaduras novas", detalhe: "no chão, muros ou paredes" },
  { ilustracao: "janela", titulo: "Portas e janelas emperrando", detalhe: "saindo do esquadro" },
  { ilustracao: "inclina", titulo: "Árvores e postes inclinando", detalhe: "cercas e muros também" },
  { ilustracao: "agua", titulo: "Água barrenta minando", detalhe: "na base do barranco" },
  { ilustracao: "estalo", titulo: "Estalos e barulhos", detalhe: "terra se mexendo" },
  { ilustracao: "muro", titulo: "Muro estufado", detalhe: "embarrigando ou afastando" },
];

export const FASES: readonly { id: IdFase; rotulo: string; blocos: readonly Bloco[] }[] = [
  {
    id: "antes",
    rotulo: "Antes",
    blocos: [
      { icone: Leaf, texto: "Plante grama na encosta" },
      { icone: Waves, texto: "Leve a água da chuva para longe" },
      { icone: Bell, texto: "Receba alertas (SMS {N} ou Telegram)", vars: { N: "40199" } },
      { icone: Backpack, texto: "Deixe a mochila pronta" },
    ],
  },
  {
    id: "durante",
    rotulo: "Durante",
    blocos: [
      { icone: Bell, texto: "Acompanhe os avisos" },
      { icone: DoorOpen, texto: "Viu sinais? Saia já" },
      { icone: X, texto: "Não atravesse lama correndo" },
      { icone: Phone, texto: "Ligue {N}", vars: { N: EMERGENCIA } },
    ],
  },
  {
    id: "depois",
    rotulo: "Depois",
    blocos: [
      { icone: Clock, texto: "Espere a Defesa Civil liberar" },
      { icone: House, texto: "Peça vistoria antes de voltar" },
      { icone: TriangleAlert, texto: "Fique longe da área atingida" },
      { icone: Camera, texto: "Fotografe os danos" },
    ],
  },
];

export const MOCHILA: readonly Bloco[] = [
  { icone: FileText, texto: "Documentos" },
  { icone: Flashlight, texto: "Lanterna" },
  { icone: Radio, texto: "Rádio e pilhas" },
  { icone: Pill, texto: "Remédios" },
  { icone: Droplet, texto: "Água" },
  { icone: BatteryCharging, texto: "Carregador" },
  { icone: Shirt, texto: "Roupa e agasalho" },
  { icone: Whistle, texto: "Apito" },
];

export const NAO_FACA: readonly Bloco[] = [
  { icone: Trash2, texto: "Jogar lixo no barranco" },
  { icone: Droplet, texto: "Soltar esgoto na encosta" },
  { icone: Shovel, texto: "Cortar o barranco" },
  { icone: Axe, texto: "Desmatar a encosta" },
  { icone: TreePalm, texto: "Plantar bananeira na encosta" },
  { icone: House, texto: "Construir na beira do barranco" },
];

export const FONTES = {
  rj: "https://www.defesacivil.rj.gov.br/index.php/para-o-cidadao/como-agir-em-desastres/12-cartilha-de-deslizamento",
  sp: "https://www.spsemprealerta.sp.gov.br/orientacoes/deslizamentos/",
};
