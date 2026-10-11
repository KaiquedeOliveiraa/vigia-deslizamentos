"""Uma execução do pipeline só na máquina: sem bot e sem commit no GitHub.

Lê o `backend/.env` (TELEGRAM_TOKEN e GITHUB_TOKEN_DADOS são exigidos pela configuração, mas aqui
não são usados: qualquer valor serve), roda coleta → cálculo → gravação no SQLite → comparação com o
INMET, e grava o `indices.json` em `frontend/public/data/` em vez de publicá-lo,
para o `npm run dev` do site ler. Os avisos decididos são só contados no log.

    .venv\\Scripts\\python -m scripts.rodar_local
"""

from datetime import datetime, timezone
from pathlib import Path

import requests

from app.config import carregar_env, carregar_municipios
from app.main import CAMINHO_MUNICIPIOS, configurar_log, encerrar_log
from app.modelos import banco
from app.pipeline import executar_pipeline

BACKEND = Path(__file__).resolve().parent.parent
DESTINO = BACKEND.parent / "frontend" / "public" / "data" / "indices.json"


def _ler_env(caminho: Path) -> dict[str, str]:
    linhas = caminho.read_text(encoding="utf-8-sig").splitlines()
    pares = (linha.split("=", 1) for linha in linhas if "=" in linha and not linha.lstrip().startswith("#"))
    return {chave.strip(): valor.strip().strip("\"'") for chave, valor in pares}


def _gravar(conteudo: bytes, _config, _http) -> bool:
    DESTINO.write_bytes(conteudo)
    return True


def main() -> None:
    config = carregar_env(_ler_env(BACKEND / ".env"))
    municipios = carregar_municipios(CAMINHO_MUNICIPIOS)
    Path(config.db_path).parent.mkdir(parents=True, exist_ok=True)
    configurar_log(config.log_path)
    conexao = banco.abrir(config.db_path)
    try:
        with requests.Session() as http:
            execucao = executar_pipeline(
                datetime.now(timezone.utc), municipios, conexao, http, config, publicar=_gravar
            )
    finally:
        conexao.close()
        encerrar_log()
    print(f"indices.json gravado em {DESTINO}" if execucao.publicado else "nada gravado")
    print(f"avisos decididos (não enviados): {len(execucao.avisos)}")


if __name__ == "__main__":
    main()
