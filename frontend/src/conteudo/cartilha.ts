// Textos da Cartilha em português; o espanhol e o inglês vêm do dicionário (src/i18n) pela própria frase.
// Cada seção cita as fontes oficiais em que se baseia (FONTES); os textos seguem a spec cartilha-oficial.
import {
  Axe,
  Backpack,
  Banknote,
  BatteryCharging,
  BedDouble,
  BriefcaseMedical,
  Clock,
  DoorOpen,
  Droplet,
  FileText,
  Flashlight,
  House,
  Leaf,
  type LucideIcon,
  Megaphone,
  Pill,
  Radio,
  Search,
  Shovel,
  Smartphone,
  Trash2,
  TreePalm,
  TriangleAlert,
  Users,
  Utensils,
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

export type ChaveFonte = "mdr" | "sgb" | "sc" | "mcom" | "pr" | "sp";

export const EMERGENCIA = "199";
export const BOMBEIROS = "193";

export const FONTES: Record<ChaveFonte, { nome: string; url: string; pdf?: true }> = {
  mdr: {
    nome: "Defesa Civil Nacional",
    url: "https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil/deslizamento.pdf",
    pdf: true,
  },
  sgb: { nome: "Serviço Geológico do Brasil", url: "https://rigeo.sgb.gov.br/handle/doc/20783" },
  sc: { nome: "Defesa Civil de Santa Catarina", url: "https://www.defesacivil.sc.gov.br/fenomeno-climatico/" },
  mcom: {
    nome: "Ministério das Comunicações",
    url: "https://www.gov.br/mcom/pt-br/noticias/noticias_alt/2026/julho/como-receber-alertas-da-defesa-civil-sobre-situacoes-de-emergencia-no-celular",
  },
  pr: { nome: "Defesa Civil do Paraná", url: "https://www.defesacivil.pr.gov.br/Pagina/Kit-de-Emergencia-pessoal" },
  sp: { nome: "SP Sempre Alerta", url: "https://www.spsemprealerta.sp.gov.br/orientacoes/deslizamentos/" },
};

export const SECOES = [
  { id: "sinais", rotulo: "{N}. Sinais", fontes: ["sgb", "mdr", "sc", "sp"] },
  { id: "fases", rotulo: "{N}. O que fazer", fontes: ["sgb", "mdr", "mcom", "pr", "sp"] },
  { id: "kit", rotulo: "{N}. Mochila", fontes: ["pr"] },
  { id: "evitar", rotulo: "{N}. Não faça", fontes: ["sgb", "mdr"] },
] as const satisfies readonly { id: string; rotulo: string; fontes: readonly ChaveFonte[] }[];

export const SINAIS: readonly Sinal[] = [
  { ilustracao: "racha", titulo: "Rachaduras novas", detalhe: "no chão, em muros ou paredes" },
  { ilustracao: "janela", titulo: "Portas e janelas emperrando", detalhe: "empenam ou travam de repente" },
  { ilustracao: "inclina", titulo: "Árvores e postes inclinando", detalhe: "cercas também" },
  { ilustracao: "agua", titulo: "Água barrenta minando", detalhe: "na base do barranco" },
  { ilustracao: "estalo", titulo: "Barulhos vindos do chão", detalhe: "como pequenos tremores" },
  { ilustracao: "muro", titulo: "Muro estufado", detalhe: "com barriga ou trincado" },
];

const NUMEROS = { N: [EMERGENCIA, BOMBEIROS] };

export const FASES: readonly { id: IdFase; rotulo: string; blocos: readonly Bloco[] }[] = [
  {
    id: "antes",
    rotulo: "Antes",
    blocos: [
      { icone: Leaf, texto: "Plante grama e árvores pequenas na encosta" },
      { icone: Waves, texto: "Leve a água da chuva e o esgoto para canaletas" },
      { icone: Search, texto: "Viu sinais de risco? Peça vistoria à Defesa Civil" },
      {
        icone: Smartphone,
        texto: "Alerta por SMS: envie seu CEP para {N}; o alerta automático no celular dispensa cadastro",
        vars: { N: "40199" },
      },
      { icone: Backpack, texto: "Deixe a mochila pronta" },
    ],
  },
  {
    id: "durante",
    rotulo: "Durante",
    blocos: [
      { icone: House, texto: "Casa em área de risco? Vá para a casa de parentes ou amigos em local seguro" },
      { icone: DoorOpen, texto: "Viu sinais? Saia já e ligue {N} ou {N}", vars: NUMEROS },
      { icone: Users, texto: "Ajude crianças, idosos e pessoas com dificuldade de locomoção" },
      { icone: Megaphone, texto: "Siga só avisos oficiais e não repasse boatos" },
      { icone: X, texto: "Nunca atravesse rua com água ou lama de deslizamento fluindo" },
    ],
  },
  {
    id: "depois",
    rotulo: "Depois",
    blocos: [
      { icone: TriangleAlert, texto: "Não entre na área atingida sem autorização" },
      { icone: Clock, texto: "Só volte para casa quando a Defesa Civil liberar" },
    ],
  },
];

export const MOCHILA: readonly Bloco[] = [
  { icone: Droplet, texto: "Água (2 L por pessoa por dia)" },
  { icone: Utensils, texto: "Comida que não estraga" },
  { icone: FileText, texto: "Cópia dos documentos" },
  { icone: BriefcaseMedical, texto: "Kit de primeiros socorros" },
  { icone: Pill, texto: "Remédios e cópia das receitas" },
  { icone: Banknote, texto: "Dinheiro" },
  { icone: Flashlight, texto: "Lanterna" },
  { icone: Radio, texto: "Rádio a pilhas" },
  { icone: BatteryCharging, texto: "Pilhas e baterias reserva" },
  { icone: Whistle, texto: "Apito" },
  { icone: BedDouble, texto: "Cobertor" },
];

export const NAO_FACA: readonly (Bloco & { detalhe?: string })[] = [
  { icone: Trash2, texto: "Jogar lixo no barranco" },
  { icone: Droplet, texto: "Soltar esgoto na encosta" },
  { icone: Shovel, texto: "Cortar o barranco" },
  { icone: Axe, texto: "Desmatar a encosta" },
  { icone: TreePalm, texto: "Plantar bananeira na encosta" },
  {
    icone: House,
    texto: "Construir na beira do barranco",
    detalhe: "construa a pelo menos 5 m da borda e 10 m do pé do barranco",
  },
];
