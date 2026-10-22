# Cartilha oficial — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** reescrever os textos da Cartilha com base em fontes oficiais e citar a fonte em cada seção, mantendo o formato interativo.

**Architecture:** o conteúdo vive em `frontend/src/conteudo/cartilha.ts` (dados + fontes por seção) e é renderizado por `frontend/src/components/Cartilha.tsx`. Task 1 troca o conteúdo e as fontes (com testes); Task 2 renderiza fontes, hero/SOS, detalhes e ajusta CSS, i18n do componente e README.

**Tech Stack:** Astro 7 + React 19, lucide-react (já instalado), vitest (node), i18n PT (chave) / ES / EN.

**Spec:** `docs/superpowers/specs/2026-10-22-cartilha-oficial-design.md` (revisão 2) — o texto de cada item está lá, **use-o literalmente**.

## Global Constraints

- Textos exatamente como na spec (são fiéis às fontes; não "melhore" a redação).
- Fontes: `mdr`, `sgb`, `sc`, `mcom`, `pr`, `sp` com nomes e URLs da tabela da spec; `mdr` é PDF. Sem RJ e sem MIDR.
- `EMERGENCIA = "199"`, `BOMBEIROS = "193"`; frases com dois números usam `{N}` duas vezes e `vars {N: ["199","193"]}` (padrão já usado em Contatos).
- Links externos: `target="_blank" rel="noopener noreferrer"`, texto oculto "(abre em nova aba)", "(PDF)" visível quando for PDF; linha de fonte ≥ 13 px com contraste AA.
- Toda frase nova em `es.json`/`en.json` (PT é a chave) com os mesmos marcadores `{N}`; chaves sem uso saem.
- Sem rolagem horizontal em 320 px; o SOS com 199/193 não estoura.
- Português; commits **sem atribuição ao Claude**.
- Comandos (em `frontend/`): `npx vitest run`, `npx tsc --noEmit`, `npm run build`.

## Review Focus

1. Item com texto diferente da spec ou atribuído a fonte errada → teste compara a lista de títulos/textos com a spec (Task 1).
2. Fonte declarada e não usada, ou usada e não declarada → teste (Task 1).
3. Chave de i18n faltando para frase de `conteudo/` → teste existente da cartilha (Task 1) e paridade (Task 2).
4. SOS com dois números estourando em 320 px → verificação no navegador (Task 2).
5. Leitor de tela não sabe que o link abre nova aba/PDF → Task 2.

---

### Task 1: Conteúdo e fontes da cartilha

**Files:**
- Modify: `frontend/src/conteudo/cartilha.ts`, `frontend/src/conteudo/cartilha.test.ts`
- Modify: `frontend/src/i18n/es.json`, `frontend/src/i18n/en.json` (frases do conteúdo)
- Modify (mínimo para compilar): `frontend/src/components/Cartilha.tsx` — só o rodapé, que hoje usa `FONTES.rj`/`FONTES.sp`: troque pela frase "Textos baseados nas fontes oficiais citadas em cada seção." (Task 2 faz o resto)

**Interfaces:**
- Produces:
  - `type ChaveFonte = "mdr" | "sgb" | "sc" | "mcom" | "pr" | "sp"`
  - `FONTES: Record<ChaveFonte, { nome: string; url: string; pdf?: true }>`
  - `SECOES` com `fontes: readonly ChaveFonte[]` em cada item (sinais: sgb, mdr, sc, sp; fases: sgb, mdr, mcom, pr, sp; kit: pr; evitar: sgb, mdr)
  - `EMERGENCIA = "199"`, `BOMBEIROS = "193"`
  - `NAO_FACA: readonly (Bloco & { detalhe?: string })[]`
  - `Bloco.vars` aceita `{ N: string[] }` (já aceita via `Vars`; confira)

- [ ] **Step 1: testes** em `cartilha.test.ts` (leia o arquivo atual e mantenha o estilo):
  - contagens: fases `[5, 5, 2]`, `MOCHILA` 11, `SINAIS` 6, `NAO_FACA` 6;
  - `SINAIS.map((s) => s.titulo)` igual à lista da spec, na ordem; `FASES` textos iguais aos da spec;
  - toda seção de `SECOES` tem ≥ 1 fonte; toda chave usada existe em `FONTES`; todo `url` começa com `https://`; toda chave de `FONTES` é usada por alguma seção;
  - o teste existente de chaves de i18n do conteúdo continua passando (todas as frases novas em es/en).
- [ ] **Step 2:** rodar e ver falhar.
- [ ] **Step 3: implementar** `cartilha.ts` com os textos da spec (sinais com as mesmas chaves de ilustração; verso dos cartões é responsabilidade da Task 2, mas a frase "Depois avise a Defesa Civil ({N}), os Bombeiros ({N}) e os vizinhos" pode ser exportada como constante aqui se ajudar), ícones lucide (`Utensils`, `BriefcaseMedical`, `Banknote`, `BedDouble`, `Users`, `Megaphone`, `Search`, `Smartphone` e os já usados), comentário do topo atualizado. Ajuste mínimo do rodapé em `Cartilha.tsx`.
- [ ] **Step 4:** es/en para todas as frases novas do conteúdo; remova as que saíram (ex.: "Fotografe os danos", "Roupa e agasalho", "Carregador", "Receba alertas (SMS {N} ou Telegram)", "Não atravesse lama correndo", "Defesa Civil RJ", "SP Sempre Alerta", "Baseado nas cartilhas da", "e do" — confira com grep se não são usadas em outro lugar antes de remover).
- [ ] **Step 5:** `npx vitest run`, `npx tsc --noEmit` → PASS. **Commit** `git commit -m "Cartilha: textos e fontes oficiais por seção"`.

### Task 2: Renderização — fontes por seção, hero, SOS e detalhes

**Files:**
- Modify: `frontend/src/components/Cartilha.tsx`, o CSS da cartilha (procure o arquivo importado no componente), `frontend/src/i18n/es.json`, `en.json`, `README.md`

**Interfaces:**
- Consumes: tudo da Task 1.

- [ ] **Step 1:** em cada `<section>`, depois do `<p>` de introdução: `<p className="fontes-sec">{t("Fonte:")} …</p>` listando `SECOES[i].fontes` separados por vírgula; cada link `<a href={url} target="_blank" rel="noopener noreferrer">{t(nome)}{pdf && " (PDF)"}<span className="sr-only"> {t("(abre em nova aba)")}</span></a>`. Na seção da mochila, também a frase "Lista de referência da Defesa Civil do Paraná (não há lista nacional nem de SC)."
- [ ] **Step 2: hero e SOS:** primeiro parágrafo do hero "Em perigo agora? Saia do local e ligue {N}." (`{N}` = 199), depois o texto atual. SOS: `<b>{EMERGENCIA}</b>` e, abaixo, `<small>{t("Bombeiros {N}", { N: BOMBEIROS })}</small>`, `aria-label={t("Emergência: Defesa Civil {N}, Bombeiros {N} — ver contatos", { N: [EMERGENCIA, BOMBEIROS] })}`. CSS: abaixo de 600 px o bloco não estoura (número menor/empilhado); confira 320 px.
- [ ] **Step 3:** verso dos cartões: "Depois avise a Defesa Civil ({N}), os Bombeiros ({N}) e os vizinhos" com os dois números (remova a chave antiga "Depois ligue {N}" se ficar sem uso). "Não faça": `<small>` com `t(detalhe)` quando existir.
- [ ] **Step 4: CSS** `.fontes-sec` ≥ 13 px, cor com contraste AA nos dois temas (use tokens existentes, ex.: `--muted` só se ≥ 4.5:1 — confira; senão `--ink`), links sublinhados; nada de largura fixa.
- [ ] **Step 5: i18n** de todas as frases novas do componente (ES/EN, mesmos `{N}`), remoção das sem uso; **README**: onde cita as cartilhas RJ/SP, passe a citar as fontes oficiais da spec.
- [ ] **Step 6:** `npx vitest run`, `npx tsc --noEmit`, `npm run build` → PASS. **Commit** `git commit -m "Cartilha: fonte em cada seção, 199 e 193 no topo e detalhes"`.
- [ ] **Step 7 (controlador):** verificação no navegador (PT/ES/EN, 320/390/1366, claro/escuro, abas pelo teclado, mochila 11/11 "pronta", links de fonte).
