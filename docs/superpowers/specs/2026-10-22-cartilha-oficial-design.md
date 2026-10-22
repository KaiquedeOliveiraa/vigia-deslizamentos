# Cartilha oficial: textos com fonte citada por seção

Parte 5 do roteiro. Branch `feat/cartilha-oficial`, sobre `feat/periodos`. Revisão 2 (após revisão por subagente que conferiu cada frase contra as fontes).

## Objetivo

A Cartilha mantém o formato interativo (cartões que viram, abas Antes/Durante/Depois, mochila marcável, lista "Não faça") e passa a ter **textos fiéis a fontes oficiais**, com a **fonte citada em cada seção**. Hoje o rodapé cita só Defesa Civil RJ e SP Sempre Alerta, e alguns itens não têm respaldo oficial ("Fotografe os danos"), estão incompletos (mochila sem comida, primeiros socorros e dinheiro) ou são ambíguos ("Não atravesse lama correndo").

**Sucesso:** cada frase da Cartilha corresponde a uma fonte oficial verificável, linkada na própria seção; nenhum número ou canal errado; o formato e a acessibilidade atuais continuam.

## Decisões (do usuário)

- Opção A: manter o formato interativo e reescrever o texto com fontes.
- Fontes preferidas: Defesa Civil SC e Nacional, SGB. Cada URL abaixo foi aberta e lida (22/10/2026); o texto do PDF do SGB foi extraído e conferido.

## Fontes

| Chave | Nome exibido | URL | Tipo |
|---|---|---|---|
| `mdr` | Defesa Civil Nacional | https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil/deslizamento.pdf | PDF |
| `sgb` | Serviço Geológico do Brasil | https://rigeo.sgb.gov.br/handle/doc/20783 | página do PDF "Comunidade mais segura" (4ª ed., 2023) |
| `sc` | Defesa Civil de Santa Catarina | https://www.defesacivil.sc.gov.br/fenomeno-climatico/ | página |
| `mcom` | Ministério das Comunicações | https://www.gov.br/mcom/pt-br/noticias/noticias_alt/2026/julho/como-receber-alertas-da-defesa-civil-sobre-situacoes-de-emergencia-no-celular | página |
| `pr` | Defesa Civil do Paraná | https://www.defesacivil.pr.gov.br/Pagina/Kit-de-Emergencia-pessoal | página |
| `sp` | SP Sempre Alerta | https://www.spsemprealerta.sp.gov.br/orientacoes/deslizamentos/ | página |

Saem: Defesa Civil RJ (nenhum item depende só dela) e a notícia do MIDR (nada que o PDF do MDR não traga).

## Conteúdo por seção

Topo (hero): o primeiro parágrafo passa a ser "Em perigo agora? Saia do local e ligue 199." e depois o texto atual de aprendizado. Botão SOS: **199** em destaque e, abaixo, menor, "Bombeiros 193"; `aria-label` "Emergência: Defesa Civil 199, Bombeiros 193 — ver contatos". Em telas < 600 px os números empilham sem estourar a largura (verificar em 320 px).

**1. Sinais de perigo** — fontes: SGB, MDR, SC, SP. (Chaves de ilustração e `key` do React mantidas.)
- `racha`: Rachaduras novas — no chão, em muros ou paredes (SGB, MDR, SC)
- `janela`: Portas e janelas emperrando — empenam ou travam de repente (SP)
- `inclina`: Árvores e postes inclinando — cercas também (MDR, SGB, SC)
- `agua`: Água barrenta minando — na base do barranco (SC, SGB)
- `estalo`: Barulhos vindos do chão — como pequenos tremores (MDR)
- `muro`: Muro estufado — com barriga ou trincado (SC, SGB)
- Verso de cada cartão: "Saia do local agora" / "Depois avise a Defesa Civil ({N}), os Bombeiros ({N}) e os vizinhos" com `{N: ["199","193"]}` (MDR).

**2. O que fazer** — fontes: SGB, MDR, MCOM, PR, SP.
- Antes (5): Plante grama e árvores pequenas na encosta (SGB) · Leve a água da chuva e o esgoto para canaletas (SGB) · Viu sinais de risco? Peça vistoria à Defesa Civil (SGB) · Alerta por SMS: envie seu CEP para {N} (40199); o alerta automático no celular dispensa cadastro (MCOM) · Deixe a mochila pronta (PR).
- Durante (5): Casa em área de risco? Vá para a casa de parentes ou amigos em local seguro (SGB) · Viu sinais? Saia já e ligue {N} ou {N} (199/193) (MDR) · Ajude crianças, idosos e pessoas com dificuldade de locomoção (MDR) · Siga só avisos oficiais e não repasse boatos (MDR) · Nunca atravesse rua com água ou lama de deslizamento fluindo (SP).
- Depois (2): Não entre na área atingida sem autorização (MDR) · Só volte para casa quando a Defesa Civil liberar (MDR).
- Saem: "Fotografe os danos" (sem fonte), "Peça vistoria antes de voltar" (a fonte não diz isso), "Receba alertas (SMS 40199 ou Telegram)" (o Telegram do VIGIA não é canal oficial; continua só no `BannerTelegram`).

**3. Mochila de emergência** — fonte: Defesa Civil do Paraná, com a frase visível "Lista de referência da Defesa Civil do Paraná (não há lista nacional nem de SC)."
- Água (2 L por pessoa por dia) · Comida que não estraga · Cópia dos documentos · Kit de primeiros socorros · Remédios e cópia das receitas · Dinheiro · Lanterna · Rádio a pilhas · Pilhas e baterias reserva · Apito · Cobertor (11 itens; a lista do PR tem 21 — ficam os 11 essenciais para sair de casa).
- Saem: "Roupa e agasalho" (não está na lista do PR) e "Carregador".

**4. Não faça** — fontes: SGB, MDR. Os mesmos 6 itens; "Construir na beira do barranco" ganha o detalhe "construa a pelo menos 5 m da borda e 10 m do pé do barranco" (SGB, recomendação de construção).

## Implementação

- `frontend/src/conteudo/cartilha.ts`: `ChaveFonte = "mdr" | "sgb" | "sc" | "mcom" | "pr" | "sp"`; `FONTES: Record<ChaveFonte, { nome: string; url: string; pdf?: true }>`; cada item de `SECOES` ganha `fontes: readonly ChaveFonte[]`; `EMERGENCIA = "199"` e `BOMBEIROS = "193"`; `NAO_FACA` itens com `detalhe?`; textos e ícones novos (lucide instalado: `Utensils`, `BriefcaseMedical`, `Banknote`, `BedDouble`, `Users`, `Megaphone`, `Search`, `Smartphone`). Comentário do topo atualizado.
- `Cartilha.tsx`:
  - linha de fonte sob o parágrafo de cada seção: `<p className="fontes-sec">{t("Fonte:")} <a …>SGB</a>, …</p>`, links com `target="_blank" rel="noopener noreferrer"`, texto oculto "(abre em nova aba)" e "(PDF)" visível quando `pdf`; tamanho ≥ 13 px com contraste AA;
  - rodapé: "Textos baseados nas fontes oficiais citadas em cada seção." no lugar da frase RJ/SP;
  - hero, SOS e verso dos cartões como acima; `<small>` do detalhe em "Não faça".
- i18n: frases de `conteudo/` continuam cobertas pelo teste da cartilha; frases novas do componente são `t("…")` literais. Toda frase nova em ES/EN com os mesmos `{N}`; chaves sem uso saem de `es.json`/`en.json`.
- Testes: atualizar `conteudo/cartilha.test.ts` (contagens 5/5/2 e mochila 11); novos: toda seção tem ≥ 1 fonte, toda chave usada existe em `FONTES`, toda URL é `https://`, toda fonte de `FONTES` é usada; um caso de `progressoMochila` com total 11.
- README: a menção à Cartilha nas fontes passa a citar as fontes oficiais.

## Verificação no navegador

PT/ES/EN, 320/390/1366 px (SOS sem estourar), claro/escuro, abas pelo teclado, mochila 11/11 mostra "pronta", links de fonte com nova aba e "(PDF)".

## Fora do escopo

- Seção nova sobre áreas de risco (a tela Áreas de risco cobre).
- WhatsApp/Telegram oficiais da Defesa Civil e a data do cell broadcast (não verificados diretamente); SAMU/PM (estão na tela Contatos).
- Mudar ilustrações.
