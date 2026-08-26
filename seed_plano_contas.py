"""Popula um plano de contas padrão para corretora de seguros.

Idempotente: pula contas cujo código já existe. Rodar uma vez após criar
as tabelas no Supabase (`python seed_plano_contas.py`).
"""

from db import get_client

# (codigo, nome, tipo, codigo_pai)
CONTAS = [
    ("1", "ATIVO", "ativo", None),
    ("1.1", "Ativo Circulante", "ativo", "1"),
    ("1.1.1", "Caixa e Bancos", "ativo", "1.1"),
    ("1.1.2", "Comissões a Receber", "ativo", "1.1"),
    ("1.2", "Ativo Não Circulante", "ativo", "1"),
    ("1.2.1", "Imobilizado", "ativo", "1.2"),
    ("2", "PASSIVO", "passivo", None),
    ("2.1", "Passivo Circulante", "passivo", "2"),
    ("2.1.1", "Fornecedores a Pagar", "passivo", "2.1"),
    ("2.1.2", "Impostos a Recolher", "passivo", "2.1"),
    ("2.1.2.1", "IRRF a Recolher", "passivo", "2.1.2"),
    ("2.1.2.2", "ISS a Recolher", "passivo", "2.1.2"),
    ("2.1.2.3", "INSS a Recolher", "passivo", "2.1.2"),
    ("2.1.2.4", "PIS/COFINS/CSLL a Recolher", "passivo", "2.1.2"),
    ("2.1.3", "Salários e Encargos a Pagar", "passivo", "2.1"),
    ("3", "PATRIMÔNIO LÍQUIDO", "patrimonio_liquido", None),
    ("3.1", "Capital Social", "patrimonio_liquido", "3"),
    ("3.2", "Lucros/Prejuízos Acumulados", "patrimonio_liquido", "3"),
    ("4", "RECEITA", "receita", None),
    ("4.1", "Receita de Comissões", "receita", "4"),
    ("4.1.1", "Comissão de Corretagem", "receita", "4.1"),
    ("4.1.2", "Adiantamento de Comissão", "receita", "4.1"),
    ("4.1.3", "Recuperação de Comissão", "receita", "4.1"),
    ("4.2", "Outras Receitas", "receita", "4"),
    ("5", "DESPESA", "despesa", None),
    ("5.1", "Despesas Operacionais", "despesa", "5"),
    ("5.1.1", "Aluguel", "despesa", "5.1"),
    ("5.1.2", "Salários e Encargos", "despesa", "5.1"),
    ("5.1.3", "Serviços de Terceiros", "despesa", "5.1"),
    ("5.1.4", "Marketing", "despesa", "5.1"),
    ("5.1.5", "Tecnologia e Software", "despesa", "5.1"),
    ("5.2", "Despesas Tributárias", "despesa", "5"),
    ("5.2.1", "IRRF sobre Comissões", "despesa", "5.2"),
    ("5.2.2", "ISS sobre Comissões", "despesa", "5.2"),
    ("5.2.3", "INSS", "despesa", "5.2"),
    ("5.2.4", "PIS/COFINS/CSLL", "despesa", "5.2"),
    ("5.3", "Despesas Financeiras", "despesa", "5"),
    ("5.4", "Cancelamentos e Estornos de Comissão", "despesa", "5"),
]


def seed():
    client = get_client()
    existentes = {
        c["codigo"]: c["id"] for c in client.table("plano_contas").select("id, codigo").execute().data or []
    }
    for codigo, nome, tipo, codigo_pai in CONTAS:
        if codigo in existentes:
            continue
        pai_id = existentes.get(codigo_pai) if codigo_pai else None
        resp = (
            client.table("plano_contas")
            .insert({"codigo": codigo, "nome": nome, "tipo": tipo, "conta_pai_id": pai_id})
            .execute()
        )
        existentes[codigo] = resp.data[0]["id"]
        print(f"criada: {codigo} {nome}")


if __name__ == "__main__":
    seed()
