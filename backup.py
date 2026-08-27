"""Exporta todas as tabelas do Supabase para JSON local, como uma cópia de
segurança independente do backup do próprio Supabase.

Uso:
    python backup.py

Salva em backups/<data-hora>/<tabela>.json. Roda quando quiser (antes de
uma mudança arriscada, ou periodicamente) — os arquivos ficam em
`backups/`, que está no .gitignore (contém dados reais de clientes).
"""

import json
from datetime import datetime
from pathlib import Path

from db import get_client

TABELAS = [
    "empresas",
    "contas_bancarias",
    "clientes",
    "fornecedores",
    "plano_contas",
    "seguradoras",
    "apolice_clientes",
    "regras_identificacao",
    "regras_classificacao_comissao",
    "regras_parcelamento",
    "ofx_importacoes",
    "ofx_transacoes",
    "lotes_comissao",
    "movimentacoes_comissao",
    "lancamentos_previstos",
    "auditoria_alertas",
]


def backup() -> Path:
    client = get_client()
    destino = Path("backups") / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    destino.mkdir(parents=True, exist_ok=True)

    for tabela in TABELAS:
        linhas = client.table(tabela).select("*").execute().data or []
        (destino / f"{tabela}.json").write_text(
            json.dumps(linhas, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(f"{tabela}: {len(linhas)} registro(s)")

    print(f"\nBackup salvo em: {destino}")
    return destino


if __name__ == "__main__":
    backup()
