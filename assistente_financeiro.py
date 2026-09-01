"""Assistente financeiro via IA (Claude) — responde perguntas em linguagem
natural sobre a situação financeira da empresa (contas a pagar/receber,
comissões, fluxo de caixa, DRE/balanço), como se fosse um analista/diretor
financeiro.

Deliberadamente NUNCA deixa a IA "chutar" um número: cada pergunta é
respondida via tool-use — a IA escolhe quais das consultas abaixo chamar
(pode encadear várias), e cada uma delas é uma consulta determinística de
verdade ao Supabase (mesmas tabelas usadas pelas telas). A IA só recebe o
resultado dessas consultas pra formular a resposta em português; ela nunca
tem acesso direto ao banco nem escreve nada nele — todas as funções aqui
são somente leitura.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta

import anthropic

from relatorios import calcular_balanco, calcular_dre

MODELO = "claude-sonnet-5"

PROMPT_SISTEMA = """Você é o analista e diretor financeiro virtual do ERP da Phoenix Seg / \
Vizentim (corretora de seguros). Responda perguntas sobre a situação financeira da \
empresa de forma direta e executiva, em português — como um diretor financeiro \
explicaria pra um sócio, sem economês desnecessário e sem enrolação.

REGRAS OBRIGATÓRIAS:
- NUNCA invente, estime ou arredonde de cabeça um valor financeiro. Toda resposta \
numérica tem que vir de uma chamada de ferramenta. Se a ferramenta não trouxer o \
dado (ou vier vazio), diga que não há esse dado no sistema — não chute.
- Sempre que a pergunta puder ser respondida com dados reais, chame as ferramentas \
necessárias ANTES de responder. Pode chamar mais de uma ferramenta, em sequência, \
se a pergunta precisar cruzar informações (ex.: comissões + fluxo de caixa).
- Valores sempre em R$ no formato brasileiro (ex.: R$ 1.234,56), datas em DD/MM/AAAA.
- Seja objetivo: texto corrido ou lista curta, sem markdown pesado (sem tabelas \
gigantes, sem títulos com #).
- Se a pergunta for ambígua quanto ao período, assuma o mês atual (ou "hoje" quando \
fizer mais sentido) e deixe claro qual período você assumiu.
- Você só sabe o que as ferramentas trazem — não fale sobre cotação de mercado, \
notícias, ou qualquer coisa fora dos dados do sistema.
- As empresas do grupo são Phoenix e Vizentim — se o usuário não especificar uma \
empresa, considere os dados de todas juntas e deixe isso claro na resposta.
"""


def esta_configurado() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _resolver_empresa_id(client, nome_empresa: str | None) -> str | None:
    if not nome_empresa:
        return None
    encontradas = (
        client.table("empresas").select("id, nome").ilike("nome", f"%{nome_empresa}%").execute().data or []
    )
    return encontradas[0]["id"] if encontradas else None


def consultar_contas(
    client,
    tipo: str = "ambos",
    situacao: str = "todos",
    data_inicio: str | None = None,
    data_fim: str | None = None,
    busca: str | None = None,
    empresa: str | None = None,
    limite: int = 30,
) -> dict:
    """Lançamentos previstos de contas a pagar/receber, com total."""
    query = client.table("lancamentos_previstos").select(
        "descricao, valor, data_vencimento, status, tipo, clientes(nome), fornecedores(nome)"
    )
    if tipo in ("pagar", "receber"):
        query = query.eq("tipo", tipo)
    if situacao in ("previsto", "pago", "cancelado"):
        query = query.eq("status", situacao)
    elif situacao == "atrasado":
        query = query.eq("status", "previsto")
    if data_inicio:
        query = query.gte("data_vencimento", data_inicio)
    if data_fim:
        query = query.lte("data_vencimento", data_fim)
    empresa_id = _resolver_empresa_id(client, empresa)
    if empresa_id:
        query = query.eq("empresa_id", empresa_id)

    itens = query.order("data_vencimento").execute().data or []

    hoje_iso = date.today().isoformat()
    if situacao == "atrasado":
        itens = [i for i in itens if i["data_vencimento"] < hoje_iso]

    if busca:
        termo = busca.strip().lower()
        itens = [
            i
            for i in itens
            if termo in ((i.get("clientes") or {}).get("nome") or "").lower()
            or termo in ((i.get("fornecedores") or {}).get("nome") or "").lower()
            or termo in (i.get("descricao") or "").lower()
        ]

    total = round(sum(i["valor"] for i in itens), 2)
    resumo = [
        {
            "descricao": i["descricao"],
            "cliente_ou_fornecedor": (i.get("clientes") or {}).get("nome") or (i.get("fornecedores") or {}).get("nome"),
            "valor": i["valor"],
            "vencimento": i["data_vencimento"],
            "status": i["status"],
            "tipo": i["tipo"],
        }
        for i in itens[:limite]
    ]
    return {
        "total_valor": total,
        "quantidade_total": len(itens),
        "itens_mostrados": len(resumo),
        "itens": resumo,
    }


def consultar_ranking_devedores(client, tipo: str, empresa: str | None = None, limite: int = 10) -> dict:
    """Ranking de clientes (a receber) ou fornecedores (a pagar) com maior
    valor em aberto (status previsto), do maior pro menor."""
    query = (
        client.table("lancamentos_previstos")
        .select("valor, clientes(nome), fornecedores(nome)")
        .eq("status", "previsto")
        .eq("tipo", tipo)
    )
    empresa_id = _resolver_empresa_id(client, empresa)
    if empresa_id:
        query = query.eq("empresa_id", empresa_id)
    itens = query.execute().data or []

    por_nome: dict[str, float] = {}
    for i in itens:
        nome = (i.get("clientes") or {}).get("nome") or (i.get("fornecedores") or {}).get("nome") or "(sem nome cadastrado)"
        por_nome[nome] = por_nome.get(nome, 0.0) + i["valor"]

    ranking = sorted(por_nome.items(), key=lambda kv: -kv[1])[:limite]
    return {"tipo": tipo, "ranking": [{"nome": n, "valor": round(v, 2)} for n, v in ranking]}


def consultar_comissoes(
    client,
    seguradora: str | None = None,
    status: str = "todos",
    data_inicio: str | None = None,
    data_fim: str | None = None,
    empresa: str | None = None,
) -> dict:
    """Lotes de comissão de seguradoras — bruto, líquido, impostos retidos."""
    query = client.table("lotes_comissao").select(
        "data_pagamento, valor_bruto, valor_liquido, valor_irrf, valor_iss, valor_inss, "
        "valor_pis_cofins_csll, status, seguradoras(nome)"
    )
    if status in ("pendente", "conciliado", "divergente"):
        query = query.eq("status", status)
    if data_inicio:
        query = query.gte("data_pagamento", data_inicio)
    if data_fim:
        query = query.lte("data_pagamento", data_fim)
    empresa_id = _resolver_empresa_id(client, empresa)
    if empresa_id:
        query = query.eq("empresa_id", empresa_id)

    lotes = query.order("data_pagamento", desc=True).execute().data or []

    if seguradora:
        termo = seguradora.strip().lower()
        lotes = [l for l in lotes if termo in ((l.get("seguradoras") or {}).get("nome") or "").lower()]

    total_bruto = sum(l["valor_bruto"] or 0 for l in lotes)
    total_liquido = sum(l["valor_liquido"] or 0 for l in lotes)
    total_impostos = sum(
        (l["valor_irrf"] or 0) + (l["valor_iss"] or 0) + (l["valor_inss"] or 0) + (l["valor_pis_cofins_csll"] or 0)
        for l in lotes
    )
    return {
        "quantidade_lotes": len(lotes),
        "total_bruto": round(total_bruto, 2),
        "total_liquido": round(total_liquido, 2),
        "total_impostos_retidos": round(total_impostos, 2),
        "lotes": [
            {
                "seguradora": (l.get("seguradoras") or {}).get("nome"),
                "data_pagamento": l["data_pagamento"],
                "valor_liquido": l["valor_liquido"],
                "status": l["status"],
            }
            for l in lotes[:20]
        ],
    }


def consultar_fluxo_caixa(client, meses: int = 6, empresa: str | None = None) -> dict:
    """Fluxo de caixa mensal (créditos x débitos reais do OFX importado)
    dos últimos N meses — mesma base de dados usada no gráfico do Dashboard."""
    hoje = date.today()
    inicio = (hoje.replace(day=1) - timedelta(days=31 * max(meses, 1))).isoformat()
    transacoes = (
        client.table("ofx_transacoes").select("data, valor, contas_bancarias(empresa_id)").gte("data", inicio).execute().data
        or []
    )

    empresa_id = _resolver_empresa_id(client, empresa)
    if empresa_id:
        transacoes = [t for t in transacoes if (t.get("contas_bancarias") or {}).get("empresa_id") == empresa_id]

    por_mes: dict[str, dict[str, float]] = {}
    for t in transacoes:
        chave = t["data"][:7]
        por_mes.setdefault(chave, {"receitas": 0.0, "despesas": 0.0})
        if t["valor"] >= 0:
            por_mes[chave]["receitas"] += t["valor"]
        else:
            por_mes[chave]["despesas"] += abs(t["valor"])

    meses_ordenados = sorted(por_mes.keys())[-meses:]
    return {
        "por_mes": [
            {"mes": m, "receitas": round(por_mes[m]["receitas"], 2), "despesas": round(por_mes[m]["despesas"], 2)}
            for m in meses_ordenados
        ]
    }


def consultar_dre(client, data_inicio: str, data_fim: str, empresa: str | None = None) -> dict:
    """DRE (receitas/despesas por categoria, resultado) do período — mesmo
    cálculo da tela DRE e Balanço."""
    return calcular_dre(client, data_inicio, data_fim, empresa_id=_resolver_empresa_id(client, empresa))


def consultar_balanco(client, empresa: str | None = None) -> dict:
    """Balanço patrimonial simplificado (situação atual, não é por
    período) — mesmo cálculo da tela DRE e Balanço."""
    return calcular_balanco(client, empresa_id=_resolver_empresa_id(client, empresa))


TOOLS = [
    {
        "name": "consultar_contas",
        "description": "Consulta lançamentos de contas a pagar e/ou a receber (previstos, pagos, atrasados ou cancelados), com o total somado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["pagar", "receber", "ambos"], "description": "Default 'ambos'."},
                "situacao": {
                    "type": "string",
                    "enum": ["previsto", "pago", "atrasado", "cancelado", "todos"],
                    "description": "'atrasado' = previsto com vencimento já passado. Default 'todos'.",
                },
                "data_inicio": {"type": "string", "description": "Data de vencimento inicial, AAAA-MM-DD. Opcional."},
                "data_fim": {"type": "string", "description": "Data de vencimento final, AAAA-MM-DD. Opcional."},
                "busca": {"type": "string", "description": "Filtra por nome de cliente/fornecedor ou parte da descrição. Opcional."},
                "empresa": {"type": "string", "description": "Nome (ou parte) da empresa, ex. 'Phoenix'. Opcional — omitir mostra todas."},
                "limite": {"type": "integer", "description": "Quantos itens detalhar na lista, default 30."},
            },
        },
    },
    {
        "name": "consultar_ranking_devedores",
        "description": "Ranking de clientes (contas a receber) ou fornecedores (contas a pagar) com maior valor em aberto, do maior pro menor.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["receber", "pagar"]},
                "empresa": {"type": "string", "description": "Opcional."},
                "limite": {"type": "integer", "description": "Default 10."},
            },
            "required": ["tipo"],
        },
    },
    {
        "name": "consultar_comissoes",
        "description": "Consulta lotes de comissão de seguradoras (valor bruto, líquido, impostos retidos), filtrando por seguradora/status/período.",
        "input_schema": {
            "type": "object",
            "properties": {
                "seguradora": {"type": "string", "description": "Nome (ou parte) da seguradora. Opcional."},
                "status": {"type": "string", "enum": ["pendente", "conciliado", "divergente", "todos"]},
                "data_inicio": {"type": "string", "description": "AAAA-MM-DD. Opcional."},
                "data_fim": {"type": "string", "description": "AAAA-MM-DD. Opcional."},
                "empresa": {"type": "string", "description": "Opcional."},
            },
        },
    },
    {
        "name": "consultar_fluxo_caixa",
        "description": "Fluxo de caixa mensal real (créditos x débitos do extrato bancário/OFX importado) dos últimos N meses.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meses": {"type": "integer", "description": "Default 6."},
                "empresa": {"type": "string", "description": "Opcional."},
            },
        },
    },
    {
        "name": "consultar_dre",
        "description": "DRE de um período: receitas e despesas por categoria e o resultado (lucro/prejuízo).",
        "input_schema": {
            "type": "object",
            "properties": {
                "data_inicio": {"type": "string", "description": "AAAA-MM-DD."},
                "data_fim": {"type": "string", "description": "AAAA-MM-DD."},
                "empresa": {"type": "string", "description": "Opcional."},
            },
            "required": ["data_inicio", "data_fim"],
        },
    },
    {
        "name": "consultar_balanco",
        "description": "Balanço patrimonial simplificado na situação atual (caixa, contas a receber, contas a pagar, patrimônio líquido) — não é por período.",
        "input_schema": {
            "type": "object",
            "properties": {"empresa": {"type": "string", "description": "Opcional."}},
        },
    },
]

_FUNCOES = {
    "consultar_contas": consultar_contas,
    "consultar_ranking_devedores": consultar_ranking_devedores,
    "consultar_comissoes": consultar_comissoes,
    "consultar_fluxo_caixa": consultar_fluxo_caixa,
    "consultar_dre": consultar_dre,
    "consultar_balanco": consultar_balanco,
}


def _executar_tool(nome: str, entrada: dict, client) -> dict:
    funcao = _FUNCOES.get(nome)
    if not funcao:
        return {"erro": f"ferramenta desconhecida: {nome}"}
    try:
        return funcao(client, **entrada)
    except Exception as e:
        return {"erro": f"falha ao consultar: {e}"}


def responder(historico: list[dict], client, max_rodadas: int = 6) -> str:
    """Recebe o histórico da conversa (lista de {"role": "user"|"assistant",
    "content": str}, já incluindo a pergunta mais nova) e devolve a resposta
    em texto do assistente, chamando as ferramentas de consulta acima
    quantas vezes forem necessárias antes de responder."""
    ia = anthropic.Anthropic()
    mensagens = [{"role": m["role"], "content": m["content"]} for m in historico]

    for _ in range(max_rodadas):
        resposta = ia.messages.create(
            model=MODELO,
            max_tokens=1500,
            system=PROMPT_SISTEMA,
            tools=TOOLS,
            messages=mensagens,
        )

        if resposta.stop_reason != "tool_use":
            return "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()

        mensagens.append({"role": "assistant", "content": resposta.content})
        resultados_tool = []
        for bloco in resposta.content:
            if bloco.type == "tool_use":
                resultado = _executar_tool(bloco.name, bloco.input, client)
                resultados_tool.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": json.dumps(resultado, ensure_ascii=False, default=str),
                    }
                )
        mensagens.append({"role": "user", "content": resultados_tool})

    return (
        "Não consegui concluir a análise dentro do limite de consultas — tente reformular "
        "a pergunta de um jeito mais específico (ex.: um período ou uma empresa)."
    )
