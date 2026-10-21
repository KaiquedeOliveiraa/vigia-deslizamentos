# Plano de implementação: tela "Áreas de risco"

> **Para agentes:** use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para executar tarefa por tarefa. Os passos usam caixas `- [ ]` para acompanhamento.

**Objetivo:** trocar a tela Estações por "Áreas de risco", com os setores de risco geológico do SGB e o histórico de ocorrências do Atlas por município.

**Arquitetura:**
- **Dados:** um script offline gera `setores_risco.geojson`, que o site carrega com `carregar()`.
- **Lógica:** funções puras em `lib/setores.ts` (leitura, resumos e estado na URL).
- **Mapa:** o `MapaLeaflet` ganha uma camada de setores (marcador por município, marcadores por forma e polígonos) e a camada INMET passa a poder ser ligada e desligada.
- **Tela:** `AreasRisco.tsx` monta mapa, painel e o cartão de ocorrências extraído de `Dados.tsx`.

**Stack:**
- Python 3.12 (pytest `-W error`, requests);
- Astro 7.3.5 + React 19 + react-leaflet;
- vitest no ambiente node.

**Especificação (obrigatória):** `docs/superpowers/specs/2026-10-21-areas-de-risco-design.md`

## Restrições globais

- **Branch:** `feat/areas-de-risco`, que sai de `feat/ocorrencias-atlas`.
- **Escopo:** 27 municípios em `backend/config/municipios.json`.
- **Tipos (códigos do contrato):** `deslizamento`, `rastejo`, `corrida_massa`, `queda`.
- **Graus:** `alto`, `muito_alto`.
- **Movimento de massa:** pode estar em qualquer uma das tipologias `tipolo_g1` a `tipolo_g5`. O tipo é a primeira tipologia de movimento de massa encontrada.
- **Mapa do SGB para os códigos:**
  - Deslizamento → `deslizamento`
  - Rastejo → `rastejo`
  - Corrida de massa → `corrida_massa`
  - Queda, Tombamento e Rolamento → `queda`
- **Nome do risco nos textos:** "risco geológico alto" e "risco geológico muito alto" (SGB). Nunca usar as cores nem os nomes das classes do índice.
- **Forma:** alto é **círculo** e muito alto é **losango**. Os polígonos de muito alto têm hachura.
- **Cores:** tokens novos `--setor-alto` e `--setor-muito-alto`, nos temas claro e escuro.
- **Faixa de segurança, exata em PT:** "Mapeamento parcial do SGB: fora dos setores também pode haver risco. Isto é o terreno, não o alerta de chuva de hoje. Em perigo, ligue 199."
- **Rota:** `areas-de-risco`; nome "Áreas de risco"; rótulo curto "Áreas"; ícone `Mountain` do lucide-react.
- **URL:** `?municipio=<ibge>&setor=<id>` com `history.replaceState`. Valor inválido é ignorado. O `setor` implica o município dele.
- **Redirecionamento:** `redirects` do Astro com o destino incluindo o base, `/vigia-deslizamentos/areas-de-risco/` (e `/es/`, `/en/`).
- **Idiomas:** frases novas em `frontend/src/i18n/es.json` **e** `en.json`, com as mesmas chaves (há um teste de paridade). Os textos do SGB (`local`, `descricao`, `recomendacao`) ficam em português, com `lang="pt-BR"`.
- **Comandos:**
  - backend, a partir de `backend/`: `C:/Users/guilh/AppData/Local/Temp/claude/C--Users-guilh-OneDrive-Desktop-spec-vigia/20bf7d94-685d-4168-93f9-07af761ca54a/scratchpad/venv/Scripts/python -m pytest -W error -q`;
  - frontend, a partir de `frontend/`: `npm test && npm run typecheck && npm run build`.
- **Commits:** em português, sem linha de atribuição ao Claude.

## Pontos de atenção na revisão

1. **Falha ao carregar o arquivo de setores:** a tela mostra o erro, nunca "0 setores", e as ocorrências continuam aparecendo (Tarefa 5, teste de `estadoDoPainel`).
2. **`?setor=` de um setor que não existe mais:** cai para a visão da região sem quebrar (Tarefa 2, `lerSelecao`).
3. **Município sem nenhum setor:** aparece a mensagem de "mapeamento parcial", não uma lista vazia sem explicação (Tarefa 2, `resumoMunicipio` com zero, e Tarefa 5).
4. **`pessoas` nulo em alguns setores:** a soma usa só os conhecidos, e o texto fala em "pessoas nos setores mapeados" (Tarefa 2).
5. **Teclado:** quem não usa mouse chega a cada setor pela lista do painel e volta com o foco no mesmo botão (Tarefa 5, conferência no navegador e `aria`).

---

### Tarefa 1: script `gerar_setores_risco` e o arquivo de setores

**Arquivos:**
- Criar: `backend/scripts/gerar_setores_risco.py`
- Criar: `backend/tests/test_gerar_setores_risco.py`
- Criar (gerado): `frontend/public/data/setores_risco.geojson`
- Modificar: `docs/contratos-de-dados.md`, com a seção nova depois da do `ocorrencias.json`

**Interfaces:**
- Consome:
  - `scripts.gerar_municipios.dentro(anel, lon, lat)`;
  - `scripts.gerar_municipios.centroide(anel)`;
  - `app.config.carregar_municipios`.
- Produz: o arquivo do contrato da especificação, com feições cujas propriedades são `{id, ibge, centro:[lon,lat], local, tipo, grau, descricao, recomendacao, pessoas, moradias, data}`.

- [ ] **Passo 1: escrever os testes**

```python
"""Testes do gerador de setores de risco do SGB (sem rede: respostas fixas)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.gerar_setores_risco import (
    centro_do_setor, data_de, feicao_de, gerar, limpar_texto, numero_de, tipo_de,
)

RAIZ = Path(__file__).resolve().parents[2]
QUAD = [[-49.6, -27.1], [-49.4, -27.1], [-49.4, -26.9], [-49.6, -26.9], [-49.6, -27.1]]


def bruta(**props):
    base = {
        "num_setor": "SC_X_SR_001_CPRM", "cd_geocmu": "4206900", "local": " Rua A ",
        "tipolo_g1": "Deslizamento", "tipolo_g2": " ", "tipolo_g3": " ", "tipolo_g4": " ", "tipolo_g5": " ",
        "grau_risco": "Alto", "descricao": "Encosta\nexposta", "sug_interv": "1 - Remoção\n2 - Drenagem",
        "num_pess": 16.0, "num_domi": 4.0, "data_setor": 1540425600000,
    }
    base.update(props)
    return {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [QUAD]}, "properties": base}


def test_tipo_primeiro_movimento_de_massa_em_qualquer_tipologia():
    assert tipo_de({"tipolo_g1": "Inundação", "tipolo_g2": "Rastejo", "tipolo_g3": " "}) == "rastejo"
    assert tipo_de({"tipolo_g1": "Tombamento"}) == "queda"
    assert tipo_de({"tipolo_g1": "Inundação", "tipolo_g2": "Erosão"}) is None


def test_limpar_texto():
    assert limpar_texto("  a\n b   c ") == "a · b c"
    assert limpar_texto(" ") is None
    assert limpar_texto(None) is None


def test_numero_e_data():
    assert numero_de(16.0) == 16 and numero_de(0) == 0 and numero_de(" ") is None and numero_de(None) is None
    assert data_de(1540425600000) == "2018-10-25" and data_de(None) is None


def test_centro_dentro_de_poligono_concavo():
    u = [[0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3], [0, 0]]
    lon, lat = centro_do_setor({"type": "Polygon", "coordinates": [u]})
    from scripts.gerar_municipios import dentro
    assert dentro(u, lon, lat)


def test_feicao_de_mapeia_e_limpa():
    f = feicao_de(bruta())
    p = f["properties"]
    assert p["id"] == "SC_X_SR_001_CPRM" and p["ibge"] == "4206900" and p["tipo"] == "deslizamento"
    assert p["grau"] == "alto" and p["local"] == "Rua A" and p["descricao"] == "Encosta · exposta"
    assert p["recomendacao"] == "1 - Remoção · 2 - Drenagem" and p["pessoas"] == 16 and p["moradias"] == 4
    assert p["data"] == "2018-10-25" and len(p["centro"]) == 2


def test_feicao_de_descarta_fora_e_grau_desconhecido():
    assert feicao_de(bruta(tipolo_g1="Inundação")) is None
    assert feicao_de(bruta(grau_risco="Médio")) is None


def test_gerar_ordena_e_recusa_id_repetido():
    a = bruta(num_setor="B", cd_geocmu="4206900")
    b = bruta(num_setor="A", cd_geocmu="4206900")
    assert [f["properties"]["id"] for f in gerar([a, b], {"4206900"})] == ["A", "B"]
    with pytest.raises(ValueError, match="repetido"):
        gerar([a, a], {"4206900"})
    assert gerar([bruta(cd_geocmu="9999999")], {"4206900"}) == []


def test_aviso_de_telefone(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        feicao_de(bruta(local="Rua A, tel (47) 99999-1234"))
    assert "telefone ou CPF" in caplog.text


def test_feicao_sem_campos_obrigatorios_e_descartada():
    sem = bruta()
    del sem["properties"]["num_setor"]
    assert feicao_de(sem) is None
    assert tipo_de({"tipolo_g1": None, "tipolo_g2": 3}) is None


class _Resposta:
    def __init__(self, status, dados):
        self.status_code, self._dados = status, dados

    def json(self):
        return self._dados


class _Sessao:
    def __init__(self, respostas):
        self.respostas = list(respostas)

    def get(self, *_a, **_k):
        return self.respostas.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_main_falha_com_contagem_diferente(monkeypatch, tmp_path):
    import scripts.gerar_setores_risco as g
    monkeypatch.setattr(g.requests, "Session", lambda: _Sessao([_Resposta(200, {"count": 2}), _Resposta(200, {"type": "FeatureCollection", "features": [bruta()]})]))
    with pytest.raises(RuntimeError, match="incompleta"):
        g.main(["--saida", str(tmp_path / "x.geojson")])


def test_main_falha_com_http_e_com_error(monkeypatch, tmp_path):
    import scripts.gerar_setores_risco as g
    monkeypatch.setattr(g.requests, "Session", lambda: _Sessao([_Resposta(500, {})]))
    with pytest.raises(RuntimeError, match="HTTP 500"):
        g.main(["--saida", str(tmp_path / "x.geojson")])
    monkeypatch.setattr(g.requests, "Session", lambda: _Sessao([_Resposta(200, {"error": {"code": 400}})]))
    with pytest.raises(RuntimeError, match="SGB"):
        g.main(["--saida", str(tmp_path / "x.geojson")])


def test_arquivo_versionado():
    d = json.loads((RAIZ / "frontend" / "public" / "data" / "setores_risco.geojson").read_text(encoding="utf-8"))
    ibges = {m["ibge"] for m in json.loads((RAIZ / "backend" / "config" / "municipios.json").read_text(encoding="utf-8"))}
    fs = d["features"]
    assert d["type"] == "FeatureCollection" and d["fonte"].startswith("Serviço Geológico do Brasil") and len(fs) > 80
    ids = [f["properties"]["id"] for f in fs]
    assert len(ids) == len(set(ids))
    for f in fs:
        p = f["properties"]
        assert p["ibge"] in ibges
        assert p["tipo"] in {"deslizamento", "rastejo", "corrida_massa", "queda"}
        assert p["grau"] in {"alto", "muito_alto"}
        assert f["geometry"]["type"] in {"Polygon", "MultiPolygon"}
```

- [ ] **Passo 2: rodar e ver falhar**

Rode `<python> -m pytest -W error -q tests/test_gerar_setores_risco.py`. Deve falhar com `ModuleNotFoundError`.

- [ ] **Passo 3: implementar**

```python
"""Gera `frontend/public/data/setores_risco.geojson`: setores de risco geológico do SGB.

Roda sob demanda, não no pipeline; o arquivo é versionado. Fonte: serviço
público do SGB (setorização de riscos geológicos):

    python -m scripts.gerar_setores_risco

Só setores de movimento de massa (em qualquer tipologia tipolo_g1..g5) nos
municípios de backend/config/municipios.json. Os textos (local, descrição,
recomendação) são do SGB, em português, e públicos; o script avisa se algum
parecer dado pessoal (telefone, CPF).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

RAIZ_BACKEND = Path(__file__).resolve().parent.parent
if str(RAIZ_BACKEND) not in sys.path:
    sys.path.insert(0, str(RAIZ_BACKEND))

from app.config import carregar_municipios  # noqa: E402
from scripts.gerar_municipios import centroide, dentro  # noqa: E402

URL_SGB = "https://geoportal.sgb.gov.br/server/rest/services/gestaoterritorial/risco/MapServer/0/query"
SAIDA = RAIZ_BACKEND.parent / "frontend" / "public" / "data" / "setores_risco.geojson"
FONTE = "Serviço Geológico do Brasil (SGB), setorização de riscos geológicos"
TIPOS = {"Deslizamento": "deslizamento", "Rastejo": "rastejo", "Corrida de massa": "corrida_massa",
         "Queda": "queda", "Tombamento": "queda", "Rolamento": "queda"}
GRAUS = {"Alto": "alto", "Muito alto": "muito_alto"}
TIMEOUT_S = 60
_PESSOAL = re.compile(r"\(?\d{2}\)?\s?\d{4,5}-?\d{4}|\d{3}\.\d{3}\.\d{3}-\d{2}")

_log = logging.getLogger(__name__)


def limpar_texto(valor) -> str | None:
    if not isinstance(valor, str):
        return None
    texto = re.sub(r"[ \t]+", " ", " · ".join(p.strip() for p in valor.strip().splitlines() if p.strip()))
    return texto or None


def numero_de(valor) -> int | None:
    try:
        return int(float(valor))
    except (TypeError, ValueError, OverflowError):
        return None


def data_de(epoch_ms) -> str | None:
    if not isinstance(epoch_ms, (int, float)):
        return None
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def tipo_de(props: dict) -> str | None:
    for i in range(1, 6):
        valor = props.get(f"tipolo_g{i}")
        rotulo = valor.strip() if isinstance(valor, str) else ""
        if rotulo in TIPOS:
            return TIPOS[rotulo]
    return None


def _maior_anel(geometria: dict) -> list:
    if geometria["type"] == "Polygon":
        return geometria["coordinates"][0]
    poligonos = geometria["coordinates"]
    return max(poligonos, key=lambda p: abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(p[0], p[0][1:]))))[0]


def centro_do_setor(geometria: dict) -> list[float]:
    """Ponto garantido dentro do polígono: centroide, ou o meio do maior trecho interno da horizontal dele."""
    anel = _maior_anel(geometria)
    lon, lat = centroide(anel)
    if not dentro(anel, lon, lat):
        cortes = sorted(
            x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            for (x1, y1), (x2, y2) in zip(anel, anel[1:]) if (y1 > lat) != (y2 > lat)
        )
        trechos = list(zip(cortes[0::2], cortes[1::2]))
        a, b = max(trechos, key=lambda t: t[1] - t[0])
        lon = (a + b) / 2
    return [round(lon, 5), round(lat, 5)]


def feicao_de(bruta: dict) -> dict | None:
    p = bruta.get("properties") or {}
    if not isinstance(p.get("num_setor"), str) or not isinstance(p.get("cd_geocmu"), str) or not bruta.get("geometry"):
        _log.warning("feição do SGB sem num_setor, cd_geocmu ou geometria, descartada")
        return None
    tipo = tipo_de(p)
    if tipo is None:
        return None
    grau_bruto = p.get("grau_risco")
    grau = GRAUS.get(grau_bruto.strip() if isinstance(grau_bruto, str) else "")
    if grau is None:
        _log.warning("setor %s: grau desconhecido %r, descartado", p.get("num_setor"), p.get("grau_risco"))
        return None
    props = {
        "id": p["num_setor"], "ibge": p["cd_geocmu"], "centro": centro_do_setor(bruta["geometry"]),
        "local": limpar_texto(p.get("local")), "tipo": tipo, "grau": grau,
        "descricao": limpar_texto(p.get("descricao")), "recomendacao": limpar_texto(p.get("sug_interv")),
        "pessoas": numero_de(p.get("num_pess")), "moradias": numero_de(p.get("num_domi")),
        "data": data_de(p.get("data_setor")),
    }
    for campo in ("local", "descricao", "recomendacao"):
        if props[campo] and _PESSOAL.search(props[campo]):
            _log.warning("setor %s: %s parece ter telefone ou CPF; confira antes de publicar", props["id"], campo)
    return {"type": "Feature", "geometry": bruta["geometry"], "properties": props}


def gerar(brutas: list[dict], ibges: set[str]) -> list[dict]:
    feicoes = [f for b in brutas if b["properties"].get("cd_geocmu") in ibges if (f := feicao_de(b))]
    vistos: set[str] = set()
    for f in feicoes:
        if f["properties"]["id"] in vistos:
            raise ValueError(f"id de setor repetido: {f['properties']['id']}")
        vistos.add(f["properties"]["id"])
    return sorted(feicoes, key=lambda f: (f["properties"]["ibge"], f["properties"]["id"]))


def _consultar(http: requests.Session, onde: str, **extra) -> dict:
    params = {"where": onde, "outFields": "*", "returnGeometry": "true", "outSR": "4326",
              "geometryPrecision": "5", "f": "geojson", **extra}
    r = http.get(URL_SGB, params=params, timeout=TIMEOUT_S)
    if r.status_code != 200:
        raise RuntimeError(f"SGB: HTTP {r.status_code}")
    dados = r.json()
    if "error" in dados:
        raise RuntimeError(f"SGB: {dados['error']}")
    return dados


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(prog="python -m scripts.gerar_setores_risco", description=__doc__)
    analisador.add_argument("--saida", default=str(SAIDA))
    args = analisador.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    ibges = {m.ibge for m in carregar_municipios(RAIZ_BACKEND / "config" / "municipios.json")}
    onde = "cd_geocmu IN (" + ",".join(f"'{i}'" for i in sorted(ibges)) + ")"
    with requests.Session() as http:
        total = _consultar(http, onde, returnCountOnly="true", f="json")["count"]
        brutas = _consultar(http, onde)["features"]
    if len(brutas) != total:
        raise RuntimeError(f"SGB devolveu {len(brutas)} de {total} setores; consulta incompleta")
    feicoes = gerar(brutas, ibges)
    saida = {"type": "FeatureCollection", "fonte": FONTE,
             "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "features": feicoes}
    Path(args.saida).write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")) + "\n",
                                encoding="utf-8", newline="\n")
    print(f"{len(feicoes)} setor(es) de {total} gravado(s) em {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Em `_consultar`, o `**extra` com `f="json"` substitui o `f` padrão. Na contagem, a resposta do ArcGIS vem como `{"count": N}`.

- [ ] **Passo 4: rodar os testes de função pura**

Rode `<python> -m pytest -W error -q tests/test_gerar_setores_risco.py -k "not arquivo_versionado"`. Todos passam.

- [ ] **Passo 5: gerar com rede e conferir**

Rode `<python> -m scripts.gerar_setores_risco`. O esperado é algo como "98 setor(es) de 249" (cerca de 94 a 98).

- [ ] **Passo 6: contrato**

Em `docs/contratos-de-dados.md`, depois da seção do `ocorrencias.json`, crie a seção `frontend/public/data/setores_risco.geojson` com:
- o bloco de contrato da especificação, seção 1;
- a frase "Gerado por `backend/scripts/gerar_setores_risco.py` a partir do serviço público do SGB. Só setores de movimento de massa. Textos do SGB em português.";
- a tabela de códigos de `tipo` e `grau`.

- [ ] **Passo 7: suíte completa e commit**

Rode `<python> -m pytest -W error -q`. Tudo passa.

```bash
git add backend/scripts/gerar_setores_risco.py backend/tests/test_gerar_setores_risco.py frontend/public/data/setores_risco.geojson docs/contratos-de-dados.md
git commit -m "feat(dados): setores de risco geológico do SGB (movimento de massa) nos 27 municípios"
```

---

### Tarefa 2: `lib/setores.ts`, com leitura, resumos e seleção na URL

**Arquivos:**
- Criar: `frontend/src/lib/setores.ts`
- Criar: `frontend/src/lib/setores.test.ts`

**Interfaces:**
- Consome: `Resultado` de `./dados` (`{ ok: true; dados } | { ok: false; erro }`) e `NOMES` de `./municipios`.
- Produz:

```ts
export type TipoSetor = "deslizamento" | "rastejo" | "corrida_massa" | "queda";
export type GrauSetor = "alto" | "muito_alto";
export interface Setor {
  id: string; ibge: string; centro: [number, number]; local: string | null; tipo: TipoSetor; grau: GrauSetor;
  descricao: string | null; recomendacao: string | null; pessoas: number | null; moradias: number | null; data: string | null;
  /** Anéis do polígono em [lat, lon], prontos para o Leaflet (MultiPolygon: um item por parte). */
  aneis: [number, number][][][];
}
export interface ColecaoSetores { setores: Setor[]; fonte: string; geradoEm: string }
export function lerSetores(json: unknown): Resultado<ColecaoSetores>;
export const ROTULO_TIPO: Record<TipoSetor, string>; // "Deslizamento", "Rastejo", "Corrida de massa", "Queda"
export const ROTULO_GRAU: Record<GrauSetor, string>; // "risco geológico alto", "risco geológico muito alto"
export interface Resumo { setores: number; muitoAlto: number; alto: number; pessoas: number; municipios: number; anoMin: number | null; anoMax: number | null }
export function resumo(setores: Setor[]): Resumo;
export function porMunicipio(setores: Setor[]): { ibge: string; setores: Setor[] }[]; // mais setores primeiro, desempate por nome
export function lerSelecao(busca: string, setores: Setor[], ibgesMonitorados: ReadonlySet<string>): { municipio: string | null; setor: string | null };
export function escreverSelecao(busca: string, sel: { municipio: string | null; setor: string | null }): string; // devolve "?..." ou ""
export const mostrarSetoresIndividuais: (municipioSelecionado: boolean, longe: boolean) => boolean;
```

- [ ] **Passo 1: escrever os testes** (`setores.test.ts`)

```ts
import { describe, expect, it } from "vitest";
import { escreverSelecao, lerSelecao, lerSetores, mostrarSetoresIndividuais, porMunicipio, resumo, type Setor } from "./setores";

const feicao = (props: Record<string, unknown>, geometry: unknown = { type: "Polygon", coordinates: [[[-49.5, -27], [-49.4, -27], [-49.4, -26.9], [-49.5, -27]]] }) => ({
  type: "Feature", geometry,
  properties: { id: "S1", ibge: "4206900", centro: [-49.45, -26.97], local: "Rua A", tipo: "deslizamento", grau: "alto", descricao: null, recomendacao: null, pessoas: 10, moradias: 3, data: "2018-10-25", ...props },
});
const colecao = (features: unknown[]) => ({ type: "FeatureCollection", fonte: "SGB", gerado_em: "2026-10-21T00:00:00Z", features });

describe("lerSetores", () => {
  it("lê e converte para [lat, lon]", () => {
    const r = lerSetores(colecao([feicao({})]));
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.dados.setores[0].aneis[0][0][0]).toEqual([-27, -49.5]);
    expect(r.dados.fonte).toBe("SGB");
  });
  it("descarta feição inválida e recusa raiz errada", () => {
    const r = lerSetores(colecao([feicao({ tipo: "inundacao" }), feicao({ grau: "medio" }), feicao({}, { type: "Point", coordinates: [0, 0] }), feicao({ id: "S2" })]));
    expect(r.ok && r.dados.setores.map((s) => s.id)).toEqual(["S2"]);
    expect(lerSetores([]).ok).toBe(false);
  });
});

const s = (p: Partial<Setor>): Setor => ({ id: "S", ibge: "4206900", centro: [0, 0], local: null, tipo: "deslizamento", grau: "alto", descricao: null, recomendacao: null, pessoas: null, moradias: null, data: null, aneis: [], ...p });

describe("resumo e porMunicipio", () => {
  it("soma só pessoas conhecidas, conta graus, municípios e anos", () => {
    expect(resumo([s({ id: "a", pessoas: 10, grau: "muito_alto", data: "2015-01-01" }), s({ id: "b", pessoas: null, data: "2021-05-02" }), s({ id: "c", ibge: "4214003", pessoas: 0 })])).toEqual({
      setores: 3, muitoAlto: 1, alto: 2, pessoas: 10, municipios: 2, anoMin: 2015, anoMax: 2021,
    });
    expect(resumo([])).toEqual({ setores: 0, muitoAlto: 0, alto: 0, pessoas: 0, municipios: 0, anoMin: null, anoMax: null });
  });
  it("mais setores primeiro, desempate pelo nome", () => {
    const lista = porMunicipio([s({ id: "1", ibge: "4214003" }), s({ id: "2", ibge: "4206900" }), s({ id: "3", ibge: "4214003" }), s({ id: "4", ibge: "4205100" })]);
    expect(lista.map((m) => [m.ibge, m.setores.length])).toEqual([["4214003", 2], ["4205100", 1], ["4206900", 1]]);
  });
});

describe("seleção na URL", () => {
  const setores = [s({ id: "SC_1", ibge: "4214003" })];
  const ibges = new Set(["4214003", "4206900"]);
  it("setor implica o município; inválidos são ignorados", () => {
    expect(lerSelecao("?setor=SC_1", setores, ibges)).toEqual({ municipio: "4214003", setor: "SC_1" });
    expect(lerSelecao("?municipio=4206900&setor=XX", setores, ibges)).toEqual({ municipio: "4206900", setor: null });
    expect(lerSelecao("?municipio=9999999", setores, ibges)).toEqual({ municipio: null, setor: null });
  });
  it("escreve preservando outros parâmetros", () => {
    expect(escreverSelecao("?x=1", { municipio: "4214003", setor: "SC_1" })).toBe("?x=1&municipio=4214003&setor=SC_1");
    expect(escreverSelecao("?municipio=4214003&setor=SC_1", { municipio: null, setor: null })).toBe("");
  });
});

it("setores individuais com município escolhido ou de perto", () => {
  expect(mostrarSetoresIndividuais(false, true)).toBe(false);
  expect(mostrarSetoresIndividuais(true, true)).toBe(true);
  expect(mostrarSetoresIndividuais(false, false)).toBe(true);
});
```

- [ ] **Passo 2: rodar e ver falhar**

Rode `npx vitest run src/lib/setores.test.ts`. Deve falhar porque o módulo não existe.

- [ ] **Passo 3: implementar**

```ts
// Setores de risco geológico do SGB (tela Áreas de risco): leitura do GeoJSON, resumos e seleção na URL.
import type { Resultado } from "./dados";
import { NOMES } from "./municipios";

export type TipoSetor = "deslizamento" | "rastejo" | "corrida_massa" | "queda";
export type GrauSetor = "alto" | "muito_alto";

export interface Setor {
  id: string;
  ibge: string;
  centro: [number, number];
  local: string | null;
  tipo: TipoSetor;
  grau: GrauSetor;
  descricao: string | null;
  recomendacao: string | null;
  pessoas: number | null;
  moradias: number | null;
  data: string | null;
  /** Anéis do polígono em [lat, lon], prontos para o Leaflet (MultiPolygon: um item por parte). */
  aneis: [number, number][][][];
}

export interface ColecaoSetores {
  setores: Setor[];
  fonte: string;
  geradoEm: string;
}

export const ROTULO_TIPO: Record<TipoSetor, string> = {
  deslizamento: "Deslizamento",
  rastejo: "Rastejo",
  corrida_massa: "Corrida de massa",
  queda: "Queda",
};

/** Nunca "alto"/"muito alto" sozinhos: são também nomes das classes do índice de chuva. */
export const ROTULO_GRAU: Record<GrauSetor, string> = {
  alto: "risco geológico alto",
  muito_alto: "risco geológico muito alto",
};

const TIPOS = new Set(Object.keys(ROTULO_TIPO));
const GRAUS = new Set(Object.keys(ROTULO_GRAU));
const erro = (mensagem: string): Resultado<never> => ({ ok: false, erro: mensagem });
const textoOuNulo = (v: unknown) => (typeof v === "string" ? v : null);
const inteiroOuNulo = (v: unknown) => (Number.isInteger(v) ? (v as number) : null);
const inverter = (anel: [number, number][]) => anel.map(([lon, lat]) => [lat, lon] as [number, number]);

function aneisDe(g: { type?: unknown; coordinates?: unknown } | undefined): [number, number][][][] | null {
  if (g?.type === "Polygon" && Array.isArray(g.coordinates)) return [(g.coordinates as [number, number][][]).map(inverter)];
  if (g?.type === "MultiPolygon" && Array.isArray(g.coordinates))
    return (g.coordinates as [number, number][][][]).map((p) => p.map(inverter));
  return null;
}

/** Lê o setores_risco.geojson; feições inválidas são descartadas (um setor ruim não derruba a tela). */
export function lerSetores(json: unknown): Resultado<ColecaoSetores> {
  const raiz = json as { type?: unknown; features?: unknown; fonte?: unknown; gerado_em?: unknown } | null;
  if (!raiz || raiz.type !== "FeatureCollection" || !Array.isArray(raiz.features))
    return erro("setores_risco.geojson: raiz não é FeatureCollection");
  const setores: Setor[] = [];
  for (const f of raiz.features as { geometry?: { type?: unknown; coordinates?: unknown }; properties?: Record<string, unknown> }[]) {
    const p = f?.properties;
    const aneis = aneisDe(f?.geometry);
    const centro = p?.centro;
    if (
      !p || !aneis || typeof p.id !== "string" || typeof p.ibge !== "string" ||
      !TIPOS.has(p.tipo as string) || !GRAUS.has(p.grau as string) ||
      !Array.isArray(centro) || centro.length !== 2 || !centro.every(Number.isFinite) ||
      setores.some((s) => s.id === p.id)
    )
      continue;
    setores.push({
      id: p.id,
      ibge: p.ibge,
      centro: centro as [number, number],
      local: textoOuNulo(p.local),
      tipo: p.tipo as TipoSetor,
      grau: p.grau as GrauSetor,
      descricao: textoOuNulo(p.descricao),
      recomendacao: textoOuNulo(p.recomendacao),
      pessoas: inteiroOuNulo(p.pessoas),
      moradias: inteiroOuNulo(p.moradias),
      data: textoOuNulo(p.data),
      aneis,
    });
  }
  return { ok: true, dados: { setores, fonte: String(raiz.fonte ?? ""), geradoEm: String(raiz.gerado_em ?? "") } };
}

export interface Resumo {
  setores: number;
  muitoAlto: number;
  alto: number;
  pessoas: number;
  municipios: number;
  anoMin: number | null;
  anoMax: number | null;
}

/** Pessoas: só valores conhecidos ("pessoas nos setores mapeados", nunca "em risco no município"). */
export function resumo(setores: Setor[]): Resumo {
  const anos = setores.flatMap((s) => (s.data ? [Number(s.data.slice(0, 4))] : []));
  return {
    setores: setores.length,
    muitoAlto: setores.filter((s) => s.grau === "muito_alto").length,
    alto: setores.filter((s) => s.grau === "alto").length,
    pessoas: setores.reduce((soma, s) => soma + (s.pessoas ?? 0), 0),
    municipios: new Set(setores.map((s) => s.ibge)).size,
    anoMin: anos.length ? Math.min(...anos) : null,
    anoMax: anos.length ? Math.max(...anos) : null,
  };
}

/** Municípios com setores: mais setores primeiro, desempate pelo nome. */
export function porMunicipio(setores: Setor[]): { ibge: string; setores: Setor[] }[] {
  const grupos = new Map<string, Setor[]>();
  for (const s of setores) grupos.set(s.ibge, [...(grupos.get(s.ibge) ?? []), s]);
  const nome = (ibge: string) => NOMES.get(ibge) ?? ibge;
  return [...grupos]
    .map(([ibge, lista]) => ({ ibge, setores: lista }))
    .sort((a, b) => b.setores.length - a.setores.length || nome(a.ibge).localeCompare(nome(b.ibge), "pt-BR"));
}

export function lerSelecao(
  busca: string,
  setores: Setor[],
  ibgesMonitorados: ReadonlySet<string>,
): { municipio: string | null; setor: string | null } {
  const q = new URLSearchParams(busca);
  const setor = setores.find((s) => s.id === q.get("setor"));
  if (setor) return { municipio: setor.ibge, setor: setor.id };
  const m = q.get("municipio");
  return { municipio: m && ibgesMonitorados.has(m) ? m : null, setor: null };
}

export function escreverSelecao(busca: string, sel: { municipio: string | null; setor: string | null }): string {
  const q = new URLSearchParams(busca);
  q.delete("municipio");
  q.delete("setor");
  if (sel.municipio) q.set("municipio", sel.municipio);
  if (sel.setor) q.set("setor", sel.setor);
  const texto = q.toString();
  return texto ? `?${texto}` : "";
}

/** De longe e sem município escolhido: um marcador por município (os 98 setores se sobreporiam). */
export const mostrarSetoresIndividuais = (municipioSelecionado: boolean, longe: boolean): boolean => municipioSelecionado || !longe;
```

O `NOMES` usado no desempate vem de `./municipios`, que já existe. Confira se `Resultado` é exportado por `./dados` (a Tarefa 5 da parte 2 já o importa de lá); se for exportado de outro lugar, ajuste o import.

- [ ] **Passo 4: rodar e ver passar**

Rode `npx vitest run src/lib/setores.test.ts`, depois `npm test && npm run typecheck`.

- [ ] **Passo 5: commit**

```bash
git add frontend/src/lib/setores.ts frontend/src/lib/setores.test.ts
git commit -m "feat(frontend): leitura dos setores do SGB, resumos e seleção na URL"
```

---

### Tarefa 3: camada de setores e camada INMET no mapa

**Arquivos:**
- Modificar: `frontend/src/components/Mapa.tsx` (props) e `frontend/src/components/MapaLeaflet.tsx` (renderização)
- Modificar: `frontend/src/lib/mapa.ts` (função pura `pontoInterno`) e `frontend/src/lib/mapa.test.ts`
- Modificar: `frontend/src/styles/tokens.css` (tokens) e `frontend/src/styles/mapa.css` (estilos)

**Interfaces:**
- Consome: `Setor` e `GrauSetor` de `../lib/setores`, e `rotulosDeLonge` de `../lib/mapa`.
- Produz:
  - em `PropsMapa`, novas props opcionais:

```ts
  /** Setores do SGB (tela Áreas de risco). Sem a prop, nada muda nas outras telas. */
  setores?: Setor[];
  setorSelecionado?: string | null;
  onSelecionarSetor?: (id: string) => void;
  /** false = um marcador por município com o nº de setores; true = setores individuais. */
  setoresIndividuais?: boolean;
  /** Avisado quando o zoom muda: `longe` segue rotulosDeLonge(zoom, zoomInicial) desta tela. */
  onLonge?: (longe: boolean) => void;
  /** Pinos visíveis (camada INMET ligada). Padrão: true. Com pinos ocultos, o enquadramento ignora os pinos. */
  pinosVisiveis?: boolean;
  /** Nome acessível do mapa nesta tela (padrão: o de hoje). */
  rotuloMapa?: string;
  /** Nome acessível de cada município nesta tela (padrão: rotuloAria com o índice). */
  rotuloMunicipio?: (ibge: string, nome: string) => string;
```

  - em `lib/mapa.ts`: `export function pontoInterno(feicao: FeicaoMunicipio): LatLon`, o ponto interno do maior anel, que serve para o marcador do município.

- [ ] **Passo 1: escrever o teste de `pontoInterno`** (em `mapa.test.ts`)

```ts
import { pontoInterno } from "./mapa";

it("pontoInterno fica dentro de um polígono côncavo", () => {
  const u = [[[0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3], [0, 0]]];
  const f = { type: "Feature", properties: { ibge: "1", nome: "U", monitorado: true }, geometry: { type: "Polygon", coordinates: u } } as unknown as FeicaoMunicipio;
  const [lat, lon] = pontoInterno(f);
  // dentro de uma das pernas do "U": x em (0,1) ou (2,3), y em (1,3)
  expect((lon > 0 && lon < 1) || (lon > 2 && lon < 3) || (lat > 0 && lat < 1)).toBe(true);
});
```

Importe o tipo `FeicaoMunicipio`, se o teste ainda não o importa.

- [ ] **Passo 2: implementar `pontoInterno`** (em `lib/mapa.ts`)

```ts
/** Ponto dentro do município (marcador de contagem): centroide do anel externo ou, se cair fora, o meio do maior trecho interno da horizontal. */
export function pontoInterno(feicao: FeicaoMunicipio): LatLon {
  const anel = (feicao.geometry.coordinates as number[][][])[0];
  let a2 = 0, cx = 0, cy = 0;
  for (let i = 0; i < anel.length - 1; i++) {
    const [x1, y1] = anel[i], [x2, y2] = anel[i + 1];
    const c = x1 * y2 - x2 * y1;
    a2 += c; cx += (x1 + x2) * c; cy += (y1 + y2) * c;
  }
  const lat = cy / (3 * a2);
  let lon = cx / (3 * a2);
  const cortes: number[] = [];
  for (let i = 0; i < anel.length - 1; i++) {
    const [x1, y1] = anel[i], [x2, y2] = anel[i + 1];
    if ((y1 > lat) !== (y2 > lat)) cortes.push(x1 + ((lat - y1) * (x2 - x1)) / (y2 - y1));
  }
  cortes.sort((p, q) => p - q);
  const dentro = cortes.filter((x) => x < lon).length % 2 === 1;
  if (!dentro) {
    let melhor = [cortes[0], cortes[1]];
    for (let i = 0; i + 1 < cortes.length; i += 2) if (cortes[i + 1] - cortes[i] > melhor[1] - melhor[0]) melhor = [cortes[i], cortes[i + 1]];
    lon = (melhor[0] + melhor[1]) / 2;
  }
  return [lat, lon];
}
```

Confira o tipo da geometria em `FeicaoMunicipio`: ela é `Polygon` (a parte 1 garante isso). Rode `npx vitest run src/lib/mapa.test.ts`; o teste passa.

- [ ] **Passo 3: tokens e estilos**

Em `tokens.css`:
- defina em `:root` (tema claro) `--setor-alto: #b4581a;` e `--setor-muito-alto: #7a1e3a;`;
- defina no bloco escuro (`@media (prefers-color-scheme: dark) :root:not([data-theme="light"])` e `:root[data-theme="dark"]`) `--setor-alto: #e08a4a;` e `--setor-muito-alto: #e0718f;`.

Confira o contraste de pelo menos 3:1 contra `--surface-000` e contra a cor de preenchimento neutro dos municípios nos dois temas (calcule e anote no commit).

Em `mapa.css`:

```css
/* Setores do SGB: forma por grau (círculo = alto, losango = muito alto) além da cor (RN03). */
.setor-marca { display: grid; place-items: center; }
.setor-marca i { display: block; width: 14px; height: 14px; border: 2px solid var(--surface-000); box-shadow: 0 0 0 1px var(--ink); }
.setor-marca.alto i { border-radius: 50%; background: var(--setor-alto); }
.setor-marca.muito_alto i { transform: rotate(45deg); background: var(--setor-muito-alto); }
.setor-marca.sel i { box-shadow: 0 0 0 3px var(--ink); }
/* Contagem de setores do município: fundo neutro (conta altos e muito altos), contraste de pelo menos 4,5:1 nos dois temas. */
.setor-conta { display: grid; place-items: center; min-width: 28px; height: 28px; padding: 0 6px; border-radius: 14px; background: var(--ink); color: var(--surface-000); font: 700 13px/1 var(--font-mono); border: 2px solid var(--surface-000); }
.mapa .setor { stroke-width: 2; fill-opacity: 0.35; }
.mapa .setor.alto { stroke: var(--setor-alto); fill: var(--setor-alto); }
.mapa .setor.muito_alto { stroke: var(--setor-muito-alto); }
/* O fill url(#hachura-setor) vai inline no elemento (como as hachuras das classes), não aqui. */
.mapa .setor.sel { stroke-width: 4; }
```

Os ícones são `divIcon` de 44×44 com a forma de 14 px no centro: a área de toque é o ícone inteiro, que é maior que o mínimo de 24 px e chega a 44 px no toque. Dentro do `<Hachuras>`, que fica no SVG do overlayPane, o mesmo dos polígonos de setor, acrescente um `<pattern id="hachura-setor">` com linhas na cor `var(--setor-muito-alto)`, no mesmo formato das hachuras de classe.

- [ ] **Passo 4: renderização em `MapaLeaflet.tsx`**

1. Desestruture as props novas, com os padrões `setores = []`, `setorSelecionado = null`, `setoresIndividuais = true` e `pinosVisiveis = true`.
2. **Enquadramento:** `const comPinos = pinosVisiveis && pinos.length > 0;`. Com isso, pinos ocultos não entram no enquadramento nem no rótulo.
3. **Nome do mapa:** o `aria-label` passa a ser `rotuloMapa ?? (comPinos ? … : …)`.
4. **Zoom:** no efeito de "longe", depois de `marcar()`, chame `onLonge?.(rotulosDeLonge(mapa.getZoom(), zoomInicial))` dentro de `marcar`. Guarde o `onLonge` num ref, como já se faz com `onSelecionar`, para não refazer o efeito.
5. **Marcadores e polígonos:** antes de `<Hachuras />`, renderize:

```tsx
{setores.length > 0 && !setoresIndividuais &&
  CONTAGENS(setores).map(({ ibge, n, pos }) => (
    <Marker key={`c-${ibge}`} position={pos} keyboard={false}
      icon={divIcon({ className: "", html: `<span class="setor-conta" aria-hidden="true">${n}</span>`, iconSize: [44, 44], iconAnchor: [22, 22] })}
      eventHandlers={{ click: () => onSelecionar?.(ibge) }} />
  ))}
{setores.length > 0 && setoresIndividuais &&
  setores.map((s) =>
    longeAtual ? (
      <Marker key={s.id} position={[s.centro[1], s.centro[0]]} keyboard={false} zIndexOffset={s.id === setorSelecionado ? 1000 : 0}
        icon={divIcon({ className: `setor-marca ${s.grau}${s.id === setorSelecionado ? " sel" : ""}`, html: "<i></i>", iconSize: [44, 44], iconAnchor: [22, 22] })}
        eventHandlers={{ click: () => onSelecionarSetor?.(s.id) }} />
    ) : (
      <Polygon key={s.id} positions={s.aneis} className={`setor ${s.grau}${s.id === setorSelecionado ? " sel" : ""}`}
        eventHandlers={{ click: () => onSelecionarSetor?.(s.id) }}
        ref={(p) => { if (p && s.grau === "muito_alto") (p.getElement() as SVGPathElement | undefined)?.style.setProperty("fill", "url(#hachura-setor)"); }} />
    ),
  )}
```

   - `CONTAGENS`:
     - no nível do módulo, `const PONTO_INTERNO = new Map(MONITORADOS.map(({ feicao }) => [feicao.properties.ibge, pontoInterno(feicao)]));`;
     - no componente, `const contagens = useMemo(() => { const n = new Map<string, number>(); for (const s of setores) n.set(s.ibge, (n.get(s.ibge) ?? 0) + 1); return [...n].flatMap(([ibge, total]) => { const pos = PONTO_INTERNO.get(ibge); return pos ? [{ ibge, n: total, pos }] : []; }); }, [setores]);`;
     - no JSX, use `contagens.map(...)` no lugar de `CONTAGENS(setores).map(...)`.
   - Os `divIcon` dos marcadores ficam em cache de módulo por chave (`${grau}|${sel}` e `conta|${n}`), para o DOM não ser recriado a cada render.
   - `longeAtual` é um `useState` atualizado no mesmo `marcar()` do efeito de zoom. O `onLonge` é chamado ali direto, sem ref, porque o `setLonge` da tela é estável.
   - **Fora do Tab e do leitor de tela:** os marcadores têm `keyboard={false}`.
     - O `divIcon` da contagem usa `className: "setor-conta-icone"` e html `<span class="setor-conta">`; o dos setores, `className: "setor-marca …"`.
     - Num efeito com dependências `[mapa, setores, setoresIndividuais, longeAtual, setorSelecionado, selecionado]`, ponha `aria-hidden="true"` e `tabindex="-1"` em cada `.leaflet-marker-icon.setor-conta-icone`, cada `.leaflet-marker-icon.setor-marca` e cada `path.setor` do overlayPane.
   - **Ordem no SVG:** o `Municipio` selecionado chama `bringToFront()` no preenchimento opaco, o que cobre os polígonos de setor. No mesmo efeito, rode `mapa.getPanes().overlayPane.querySelectorAll("path.setor").forEach((el) => el.parentNode?.appendChild(el))`, para os setores voltarem para cima.
   - **Nome acessível do município:** em `Municipio`, quando `rotuloMunicipio` vier preenchida, use `rotuloMunicipio(ibge, nome)` no lugar de `rotuloAria(t, nome, valor)`. Repasse a prop do `MapaLeaflet` para cada `Municipio`.
   - As classes de `Polygon` só valem na criação. Para refletir a seleção, troque a `key` incluindo `sel` (`key={`${s.id}${sel ? "-s" : ""}`}`) ou faça um efeito que alterna a classe no elemento. Use a `key`, que é mais simples.
6. **Município selecionado** (só quando `setores.length > 0`): num efeito, quando `selecionado` mudar e não houver setor selecionado, faça `mapa.fitBounds(limites([feicao]), { padding: [24, 24] })` com a feição do município, tirada de `MONITORADOS`. As outras telas não passam `setores` e não são afetadas.
7. **Setor selecionado:** num efeito, quando `setorSelecionado` mudar e o setor existir, chame `mapa.fitBounds(L.polygon(setor.aneis).getBounds(), { maxZoom: 16, padding: [32, 32] })`. Importe `polygon` de "leaflet".
8. **Pinos:** renderize só se `pinosVisiveis`.

- [ ] **Passo 5: verificar**

Rode `npm test && npm run typecheck && npm run build`. As outras telas não passam `setores`, então nada muda nelas; confira que os testes de mapa que existem continuam passando.

- [ ] **Passo 6: commit**

```bash
git add frontend/src/components/Mapa.tsx frontend/src/components/MapaLeaflet.tsx frontend/src/lib/mapa.ts frontend/src/lib/mapa.test.ts frontend/src/styles/tokens.css frontend/src/styles/mapa.css
git commit -m "feat(frontend): camada de setores do SGB no mapa (marcador por município, forma por grau) e camada INMET opcional"
```

---

### Tarefa 4: cartão de ocorrências num componente próprio e link na tela Dados

**Arquivos:**
- Criar: `frontend/src/components/Ocorrencias.tsx`
- Modificar: `frontend/src/components/Dados.tsx`, que perde o cartão e o carregamento do `ocorrencias.json` e ganha o link

**Interfaces:**
- Produz: `export default function Ocorrencias({ t, ibge, nome }: { t: T; ibge: string; nome: string })`. O componente carrega o `ocorrencias.json` sozinho, com `carregar("ocorrencias.json", lerOcorrencias)`, e mostra os estados de carregando, erro e vazio.

- [ ] **Passo 1: extrair**

1. Mova as funções `contador` e `Ocorrencias` de `Dados.tsx` para `components/Ocorrencias.tsx`.
2. Troque o parâmetro `municipio: Municipio` por `ibge` e `nome`.
3. O carregamento passa para dentro do componente: `const [ocorrencias, setOcorrencias] = useState<Resultado<Ocorrencia[]>>(); useEffect(() => { carregar("ocorrencias.json", lerOcorrencias).then(setOcorrencias); }, []);`.
4. Logo abaixo do título do cartão, acrescente a frase `t("Inclui eventos de chuva que não são deslizamento (enxurrada, inundação, alagamento, chuva intensa).")`.
5. Os imports (`ClipboardList`, `TriangleAlert`, `formatarData`, `lerOcorrencias`, `ocorrenciasDoMunicipio`, `resumoOcorrencias`, `TIPO_DESLIZAMENTO`, `Ocorrencia`, `Resultado`, `carregar`) vão junto.
6. **CSS:** o cartão depende de regras que estão em `dados.css`, um arquivo que só a tela Dados importa:
   - as genéricas `.card`, `.card .ch`, `.card .ch h2`, `.card .ch > svg` e `.card .sub` (perto das linhas 85 a 140) vão para `frontend/src/styles/cartao.css`, importado por `Dados.tsx` e por `Ocorrencias.tsx`;
   - as do cartão (`.ocs`, `.ocs-rol`, `.desl`) vão para `frontend/src/styles/ocorrencias.css`, importado por `Ocorrencias.tsx`;
   - as duas saem de `dados.css`. A tela Dados continua com a mesma aparência.

- [ ] **Passo 2: Dados.tsx**

1. Apague o estado e o `useEffect` das ocorrências, e o `<Ocorrencias …/>`.
2. No lugar do cartão, acrescente:

```tsx
<p className="note">
  <a href={`${rota("areas-de-risco", lang)}?municipio=${destaque.ibge}`}>{t("Histórico de ocorrências e áreas de risco de {M}: ver em Áreas de risco", { M: destaque.nome })}</a>
</p>
```

   `rota` vem de `../lib/telas`; confira se `Dados` recebe `lang` (sim, pelas props) e se `destaque` existe nesse ponto, e use o mesmo guard que o resto do bloco usa.
3. Remova os imports que ficarem sem uso.

- [ ] **Passo 3: i18n**

Em `es.json` e `en.json`:
- "Inclui eventos de chuva que não são deslizamento (enxurrada, inundação, alagamento, chuva intensa)." → ES "Incluye eventos de lluvia que no son deslizamientos (torrente, inundación, anegamiento, lluvia intensa).", EN "Includes rain events that are not landslides (flash flood, river flood, urban flooding, heavy rain)."
- "Histórico de ocorrências e áreas de risco de {M}: ver em Áreas de risco" → ES "Historial de ocurrencias y áreas de riesgo de {M}: ver en Áreas de riesgo", EN "Occurrence history and risk areas for {M}: see Risk areas"

- [ ] **Passo 4: verificar e fazer commit**

Rode `npm test && npm run typecheck && npm run build`. O link aponta para uma rota que só passa a existir na Tarefa 5; o build não quebra por isso.

```bash
git add frontend/src/components/Ocorrencias.tsx frontend/src/components/Dados.tsx frontend/src/styles/ocorrencias.css frontend/src/styles/cartao.css frontend/src/styles/dados.css frontend/src/i18n/es.json frontend/src/i18n/en.json
git commit -m "refactor(frontend): cartão de ocorrências num componente próprio; Dados aponta para Áreas de risco"
```

---

### Tarefa 5: tela Áreas de risco, rota, menu e redirecionamento

**Arquivos:**
- Criar: `frontend/src/components/AreasRisco.tsx`
- Criar: `frontend/src/pages/[...lang]/areas-de-risco.astro`
- Renomear: `frontend/src/styles/estacoes.css` → `frontend/src/styles/areas.css`, trocando a classe raiz `.est` por `.areas`
- Apagar: `frontend/src/components/Estacoes.tsx` e `frontend/src/pages/[...lang]/estacoes.astro`
- Modificar:
  - `frontend/src/lib/telas.ts` e `frontend/src/lib/telas.test.ts`
  - `frontend/src/components/Menu.tsx`
  - `frontend/astro.config.mjs`
  - `frontend/src/i18n/es.json` e `en.json`
- Criar: `frontend/src/lib/areas.ts`, com uma função pura testável do estado do painel, e `frontend/src/lib/areas.test.ts`

**Interfaces:**
- Consome:
  - Tarefa 2: `lerSetores`, `resumo`, `porMunicipio`, `lerSelecao`, `escreverSelecao`, `mostrarSetoresIndividuais`, `ROTULO_TIPO` e `ROTULO_GRAU`;
  - Tarefa 3: as props do `Mapa`;
  - Tarefa 4: `Ocorrencias`.
- Produz: `estadoDoPainel(carga: Resultado<ColecaoSetores> | undefined, municipio: string | null, setor: string | null): "carregando" | "erro" | "regiao" | "municipio" | "setor"`.

- [ ] **Passo 1: estado do painel (TDD)**

`areas.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { estadoDoPainel } from "./areas";

describe("estadoDoPainel", () => {
  const ok = { ok: true as const, dados: { setores: [], fonte: "", geradoEm: "" } };
  it("erro de carga nunca vira 'sem setores'", () => {
    expect(estadoDoPainel({ ok: false, erro: "x" }, null, null)).toBe("erro");
    expect(estadoDoPainel({ ok: false, erro: "x" }, "4206900", null)).toBe("erro");
  });
  it("carregando, região, município, setor", () => {
    expect(estadoDoPainel(undefined, null, null)).toBe("carregando");
    expect(estadoDoPainel(ok, null, null)).toBe("regiao");
    expect(estadoDoPainel(ok, "4206900", null)).toBe("municipio");
    expect(estadoDoPainel(ok, "4206900", "S1")).toBe("setor");
  });
});
```

`areas.ts`:

```ts
// Tela Áreas de risco: qual painel mostrar. Erro de carga nunca vira "sem setores" (segurança).
import type { Resultado } from "./dados";
import type { ColecaoSetores } from "./setores";

export function estadoDoPainel(
  carga: Resultado<ColecaoSetores> | undefined,
  municipio: string | null,
  setor: string | null,
): "carregando" | "erro" | "regiao" | "municipio" | "setor" {
  if (!carga) return "carregando";
  if (!carga.ok) return "erro";
  if (setor) return "setor";
  return municipio ? "municipio" : "regiao";
}
```

Rode `npx vitest run src/lib/areas.test.ts`: primeiro falha, depois passa.

- [ ] **Passo 2: rota, menu e página**

- **`telas.ts`:** troque a entrada `{ rota: "estacoes", nome: "Estações", curto: "Estações" }` por `{ rota: "areas-de-risco", nome: "Áreas de risco", curto: "Áreas" }`, na mesma posição.
- **`telas.test.ts`:** troque `"estacoes"` por `"areas-de-risco"` na lista esperada.
- **`Menu.tsx`:** no `ICONES`, troque `estacoes: Gauge` por `"areas-de-risco": Mountain`, importe `Mountain` de lucide-react e remova `Gauge` se ficar sem uso.
- **Página:** crie `pages/[...lang]/areas-de-risco.astro` copiando a de Estações, com `<Base tela="areas-de-risco">`, `<h1 class="sr-only">{t("Áreas de risco")}</h1>` e `<AreasRisco client:only="react" lang={lang} />`. Apague `estacoes.astro`.
- **`astro.config.mjs`:** dentro do `defineConfig`, acrescente:

```js
  // Antiga tela Estações: o destino leva o base (sem ele o Astro gera um link que dá 404 no GitHub Pages).
  redirects: {
    "/estacoes": "/vigia-deslizamentos/areas-de-risco/",
    "/es/estacoes": "/vigia-deslizamentos/es/areas-de-risco/",
    "/en/estacoes": "/vigia-deslizamentos/en/areas-de-risco/",
  },
```

- [ ] **Passo 3: `AreasRisco.tsx`**

Implemente o componente seguindo a especificação, seções 2 e 3, com esta estrutura:
- **Estado:** `carga` (setores), `estacoes` (o `carregar("estacoes.json", lerEstacoes)` de hoje), `municipio`, `setor`, `inmet` (boolean, padrão false), `longe` (boolean, padrão true).
- **Carregamento:** ao carregar os setores, `lerSelecao(location.search, setores, IBGES)`, onde `IBGES = new Set(MONITORADOS.map((m) => m.ibge))` de `../lib/municipios`.
- **Seleção:**
  - escolher um município, no mapa ou na lista, limpa o `setor`;
  - escolher um setor define também o `municipio` dele;
  - em todo estado diferente de `regiao` há um botão "Ver toda a região" que limpa os dois;
  - toda mudança chama `history.replaceState(null, "", location.pathname + escreverSelecao(location.search, sel) + location.hash)`;
  - chama também `anunciar(...)` com o nome do município ou com o tipo e o grau do setor;
  - e faz `tituloPainel.current?.focus()` (o título do painel tem `tabIndex={-1}`);
  - **exceção:** a seleção inicial, lida da URL ao carregar, não anuncia, não move o foco e não rola a página. Use um ref `inicial` que fica falso depois da primeira aplicação.
- **Camada INMET:**
  - o `estacoes.json` é carregado só na primeira vez que a camada é ligada;
  - se o carregamento falhar, o botão volta a desligado e aparece a nota `t("Não foi possível carregar as estações do INMET.")`;
  - ligar a camada não muda o enquadramento.
- **Mapa:** `<Mapa lang valores={{}} selecionado={municipio} onSelecionar={escolherMunicipio} setores={setores} setorSelecionado={setor} onSelecionarSetor={escolherSetor} setoresIndividuais={mostrarSetoresIndividuais(!!municipio, longe)} onLonge={setLonge} pinos={pinosInmet} pinosVisiveis={inmet} rotuloMapa={t("Mapa dos setores de risco geológico. Use a lista ao lado para percorrer os setores.")} rotuloMunicipio={(ibge, nome) => rotuloSetoresMunicipio(t, nome, contagemPorIbge.get(ibge) ?? 0)} camadas={false}>`.
  - `rotuloSetoresMunicipio(t, nome, n)` é uma função pura em `lib/areas.ts`, com teste. Ela devolve:
    - com 0 setores: `t("{M}: nenhum setor mapeado pelo SGB", { M })`;
    - com 1: `t("{M}: 1 setor de risco geológico", { M })`;
    - com mais: `t("{M}: {N} setores de risco geológico", { M, N })`.
- **Dentro do mapa:**
  - uma legenda (forma do círculo e do losango com `ROTULO_GRAU`, o marcador de contagem, "Risco geológico mapeado pelo SGB");
  - um botão `aria-pressed` "Estações do INMET" que alterna `inmet`. Os pinos são montados como em `Estacoes.tsx` hoje (copie a montagem de `pinos` e o `balao`).
- **Painel** (`<aside className="side r">`):
  - **Faixa de segurança,** sempre: `<p className="aviso-risco" role="note">` com o texto exato das restrições globais, um link para Monitoramento (`rota("", lang)`) e a ressalva RN04 que as outras telas usam (procure "não constitui alerta oficial" e reaproveite a mesma frase e a mesma chave).
  - **`switch (estadoDoPainel(...))`:**
    - `carregando`: `t("Carregando os setores…")`;
    - `erro`: `t("Não foi possível carregar os setores de risco.")`, mais o `<Ocorrencias>` se houver município;
    - `regiao`: o resumo, "Mapeamentos de {N} a {N}", a lista `porMunicipio` (botões) e `<details>` com os municípios sem setores;
    - `municipio`: o resumo do município, a lista de setores (botões `aria-pressed`, mostrando `t(ROTULO_TIPO[s.tipo])`, `t(ROTULO_GRAU[s.grau])` e `s.local`), ou a mensagem de "mapeamento parcial" quando não há setores; depois o `<Ocorrencias t ibge nome>` e o link para Monitoramento com `?municipio=`;
    - `setor`: título com `<span className={`setor-marca ${s.grau}`}><i/></span>`, tipo e grau; os campos (`local`, `descricao` e `recomendacao` com `lang="pt-BR"` e, se `lang !== "pt"`, a nota `t("texto original do SGB, em português")`); "pessoas" e "moradias" com "não informado" quando nulos; "Mapeado em {N}" (`formatarData`) ou "data não informada"; a fonte com link `https://geoportal.sgb.gov.br/`; o botão "Voltar para {M}", que limpa o setor e devolve o foco ao botão do setor (guarde um `ref` por id). Esse foco acontece depois do novo render, com `requestAnimationFrame`, e nesse caso substitui o foco no título.
- **Plurais:** use chaves separadas para 1 ("1 setor", "1 pessoa").
- **Celular:** depois de qualquer seleção, `painel.current?.scrollIntoView({ block: "start", behavior: "smooth" })` quando `matchMedia("(max-width: 900px)").matches`.

O CSS fica em `styles/areas.css`, renomeado de `estacoes.css`, com `.est` trocado por `.areas`. Acrescente:
- `.aviso-risco`, com os tokens de aviso (`--alert-bg`, `--alert-line`) e o mesmo estilo de aviso já usado;
- `.lista-setores`, com `max-height: 22rem; overflow-y: auto;` num wrapper `div` com `tabIndex={0}`, `role="region"` e `aria-label`.

- [ ] **Passo 4: frases (i18n)**

Acrescente em `es.json` e `en.json` (mesmas chaves) **todas** as frases literais `t("…")` novas da tela. O teste de dicionário lista as que faltarem; rode `npm test` e complete até passar.
- **Traduções obrigatórias:**
  - "Áreas de risco" → "Áreas de riesgo" / "Risk areas"
  - "Áreas" → "Áreas" / "Areas"
  - "VIGIA · Áreas de risco" → "VIGIA · Áreas de riesgo" / "VIGIA · Risk areas"
  - "Tela Áreas de risco" → "Pantalla Áreas de riesgo" / "Risk areas screen"
  - "Deslizamento" → "Deslizamiento" / "Landslide"
  - "Rastejo" → "Reptación" / "Soil creep"
  - "Corrida de massa" → "Flujo de detritos" / "Debris flow"
  - "Queda" → "Caída de rocas" / "Rockfall"
  - "risco geológico alto" → "riesgo geológico alto" / "high geological risk"
  - "risco geológico muito alto" → "riesgo geológico muy alto" / "very high geological risk"
- **Faixa de segurança:** ES "Mapeo parcial del SGB: fuera de los sectores también puede haber riesgo. Esto es el terreno, no la alerta de lluvia de hoy. En peligro, llame al 199.", EN "Partial SGB mapping: there may be risk outside the sectors too. This is the terrain, not today's rain alert. In danger, call 199."
- **Demais frases da tela** (PT → ES / EN; marcadores `{N}` e `{M}` iguais nas três):
  - "{N} setores de risco geológico em {N} dos {N} municípios" → "{N} sectores de riesgo geológico en {N} de los {N} municipios" / "{N} geological risk sectors in {N} of the {N} municipalities"
  - "{N} pessoas nos setores mapeados" → "{N} personas en los sectores mapeados" / "{N} people in the mapped sectors"
  - "1 pessoa nos setores mapeados" → "1 persona en los sectores mapeados" / "1 person in the mapped sectors"
  - "{M}: {N} setores ({N} risco muito alto, {N} alto)" → "{M}: {N} sectores ({N} riesgo muy alto, {N} alto)" / "{M}: {N} sectors ({N} very high risk, {N} high)"
  - "{M}: 1 setor" → "{M}: 1 sector" / "{M}: 1 sector"
  - "Mapeamentos de {N} a {N}" → "Mapeos de {N} a {N}" / "Mapped between {N} and {N}"
  - "Sem setores mapeados:" → "Sin sectores mapeados:" / "No mapped sectors:"
  - "O SGB não mapeou setores em {M}. O mapeamento é parcial: isso não significa que não haja risco." → "El SGB no mapeó sectores en {M}. El mapeo es parcial: eso no significa que no haya riesgo." / "SGB has not mapped sectors in {M}. The mapping is partial: this does not mean there is no risk."
  - "Ver o índice de {M} em Monitoramento" → "Ver el índice de {M} en Monitoreo" / "See the index for {M} in Monitoring"
  - "Ver toda a região" → "Ver toda la región" / "See the whole region"
  - "Voltar para {M}" → "Volver a {M}" / "Back to {M}"
  - "não informado" → "no informado" / "not reported"
  - "data não informada" → "fecha no informada" / "date not reported"
  - "Mapeado em {N}" → "Mapeado el {N}" / "Mapped on {N}"
  - "Recomendação do SGB" → "Recomendación del SGB" / "SGB recommendation"
  - "Pessoas" → "Personas" / "People"
  - "Moradias" → "Viviendas" / "Homes"
  - "Local" → "Lugar" / "Location"
  - "Descrição de campo" → "Descripción de campo" / "Field description"
  - "texto original do SGB, em português" → "texto original del SGB, en portugués" / "original SGB text, in Portuguese"
  - "Risco geológico mapeado pelo SGB" → "Riesgo geológico mapeado por el SGB" / "Geological risk mapped by SGB"
  - "número de setores do município" → "número de sectores del municipio" / "number of sectors in the municipality"
  - "Estações do INMET" → "Estaciones del INMET" / "INMET stations"
  - "Carregando os setores…" → "Cargando los sectores…" / "Loading sectors…"
  - "Não foi possível carregar os setores de risco." → "No se pudieron cargar los sectores de riesgo." / "Risk sectors could not be loaded."
  - "Não foi possível carregar as estações do INMET." → "No se pudieron cargar las estaciones del INMET." / "INMET stations could not be loaded."
  - "Mapa dos setores de risco geológico. Use a lista ao lado para percorrer os setores." → "Mapa de los sectores de riesgo geológico. Use la lista al lado para recorrer los sectores." / "Map of geological risk sectors. Use the list beside it to go through the sectors."
  - "{M}: nenhum setor mapeado pelo SGB" → "{M}: ningún sector mapeado por el SGB" / "{M}: no sector mapped by SGB"
  - "{M}: 1 setor de risco geológico" → "{M}: 1 sector de riesgo geológico" / "{M}: 1 geological risk sector"
  - "{M}: {N} setores de risco geológico" → "{M}: {N} sectores de riesgo geológico" / "{M}: {N} geological risk sectors"
  - "Fonte: Serviço Geológico do Brasil (SGB), setorização de riscos geológicos." → "Fuente: Servicio Geológico de Brasil (SGB), sectorización de riesgos geológicos." / "Source: Geological Survey of Brazil (SGB), geological risk sectorization."
- **Confira à mão:** frases com `t(` quebrado em várias linhas escapam do teste automático. As 6 chaves dinâmicas de `ROTULO_TIPO` e `ROTULO_GRAU` também precisam estar no dicionário.
- **Remover** de ambos: "Estações", "VIGIA · Estações", "Tela Estações" e o parágrafo longo da tela Estações. As frases que a camada INMET ainda usa ficam: "Estações de monitoramento", os textos de distância e "INMET".

- [ ] **Passo 5: verificar o build e o redirecionamento**

Rode `npm test && npm run typecheck && npm run build`, depois:

```bash
grep -o 'url=[^"]*' dist/estacoes/index.html dist/es/estacoes/index.html dist/en/estacoes/index.html
```

Esta conferência é manual, porque o projeto não tem teste automatizado do `dist`, e depende do `npm run build` ter rodado antes. O esperado é `url=/vigia-deslizamentos/areas-de-risco/`, `…/es/areas-de-risco/` e `…/en/areas-de-risco/`. Se o caminho dos arquivos no `dist` for outro, procure com `ls dist`.

- [ ] **Passo 6: conferir no navegador**

Use um servidor de dev em `http://localhost:4330/vigia-deslizamentos/areas-de-risco/`, com `timeout 30` em todo comando do agent-browser e pulando o que travar. Confira em PT, ES e EN, a 320, 390 e 1366 px:
- a abertura com os marcadores de contagem;
- escolher Ibirama (setores individuais e lista);
- escolher um setor (polígono ao aproximar, `fitBounds`, painel do setor, "Voltar" devolvendo o foco);
- `?setor=` compartilhado;
- a camada INMET ligada e desligada;
- erro simulado (renomeie o arquivo de dados temporariamente e desfaça depois);
- nenhuma rolagem horizontal.

- [ ] **Passo 7: commit**

```bash
git add -A frontend/src frontend/astro.config.mjs
git commit -m "feat(frontend): tela Áreas de risco no lugar de Estações (setores do SGB, ocorrências, camada INMET)"
```

---

### Tarefa 6: documentação

**Arquivos:** `README.md` e `docs/pendencias.md`.

- [ ] **Passo 1:** no README:
  - **Telas:** trocar Estações por "Áreas de risco", na rota `/areas-de-risco`, com os setores do SGB e as ocorrências por município.
  - **RF07:** o histórico de ocorrências fica em Áreas de risco.
  - **RF09:** as estações do INMET passam a ser uma camada opcional em Áreas de risco.
  - **RF13:** os idiomas são PT, ES e EN.
  - **Tabela de fontes:** incluir o Serviço Geológico do Brasil, setorização de riscos geológicos (`backend/scripts/gerar_setores_risco.py`, versionado).
- [ ] **Passo 2:** em `pendencias.md`, acrescentar: "⚪ **Atualizar setores do SGB:** quando o SGB publicar mapeamento novo na região, rodar `gerar_setores_risco`."
- [ ] **Passo 3:** fazer o commit com `git commit -m "docs: Áreas de risco no README e pendência de atualização dos setores"`.

---

### Tarefa 7: validação final e PR

- [ ] **Passo 1:** rodar as três suítes (backend, frontend e bot-worker) e confirmar que todas passam.
- [ ] **Passo 2:** revisão final da branch inteira por subagente; corrigir o que ele apontar e re-revisar.
- [ ] **Passo 3:** abrir o PR com `git push -u origin feat/areas-de-risco` e `gh pr create --base feat/ocorrencias-atlas`.
  - O corpo do PR cita a dependência dos PRs #12 e #13, o número de setores e o tamanho do arquivo.
  - Sem atribuição ao Claude.
