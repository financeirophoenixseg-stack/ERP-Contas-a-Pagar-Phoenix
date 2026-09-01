import json
from datetime import date
from unittest.mock import MagicMock, patch

import assistente_financeiro as af
from conftest import FakeSupabaseClient


# ---------- funções de consulta (sem IA) ----------


def test_consultar_contas_filtra_por_tipo_e_soma():
    client = FakeSupabaseClient(
        {
            "lancamentos_previstos": [
                {
                    "descricao": "Aluguel",
                    "valor": 1000.0,
                    "data_vencimento": "2026-08-05",
                    "status": "previsto",
                    "tipo": "pagar",
                    "fornecedores": {"nome": "Imobiliária X"},
                },
                {
                    "descricao": "Comissão Suhai",
                    "valor": 500.0,
                    "data_vencimento": "2026-08-10",
                    "status": "previsto",
                    "tipo": "receber",
                    "clientes": {"nome": "Cliente Y"},
                },
            ]
        }
    )
    resultado = af.consultar_contas(client, tipo="pagar")
    assert resultado["total_valor"] == 1000.0
    assert resultado["quantidade_total"] == 1
    assert resultado["itens"][0]["cliente_ou_fornecedor"] == "Imobiliária X"


def test_consultar_contas_atrasado_filtra_por_data_vencida():
    client = FakeSupabaseClient(
        {
            "lancamentos_previstos": [
                {"descricao": "Vencido", "valor": 100.0, "data_vencimento": "2020-01-01", "status": "previsto", "tipo": "pagar"},
                {"descricao": "Futuro", "valor": 200.0, "data_vencimento": "2099-01-01", "status": "previsto", "tipo": "pagar"},
            ]
        }
    )
    resultado = af.consultar_contas(client, situacao="atrasado")
    assert resultado["quantidade_total"] == 1
    assert resultado["itens"][0]["descricao"] == "Vencido"


def test_consultar_contas_busca_por_nome_do_fornecedor():
    client = FakeSupabaseClient(
        {
            "lancamentos_previstos": [
                {
                    "descricao": "Aluguel",
                    "valor": 100.0,
                    "data_vencimento": "2026-08-05",
                    "status": "previsto",
                    "tipo": "pagar",
                    "fornecedores": {"nome": "Imobiliária XPTO"},
                },
                {
                    "descricao": "Outra",
                    "valor": 50.0,
                    "data_vencimento": "2026-08-06",
                    "status": "previsto",
                    "tipo": "pagar",
                    "fornecedores": {"nome": "Outro Fornecedor"},
                },
            ]
        }
    )
    resultado = af.consultar_contas(client, busca="xpto")
    assert resultado["quantidade_total"] == 1


def test_resolver_empresa_id_busca_parcial_e_ausencia():
    client = FakeSupabaseClient({"empresas": [{"id": "emp-1", "nome": "Phoenix Seg"}]})
    assert af._resolver_empresa_id(client, "phoenix") == "emp-1"
    assert af._resolver_empresa_id(client, None) is None
    assert af._resolver_empresa_id(client, "inexistente") is None


def test_consultar_ranking_devedores_ordena_do_maior_pro_menor():
    client = FakeSupabaseClient(
        {
            "lancamentos_previstos": [
                {"valor": 300.0, "status": "previsto", "tipo": "receber", "clientes": {"nome": "Cliente A"}},
                {"valor": 100.0, "status": "previsto", "tipo": "receber", "clientes": {"nome": "Cliente A"}},
                {"valor": 500.0, "status": "previsto", "tipo": "receber", "clientes": {"nome": "Cliente B"}},
            ]
        }
    )
    resultado = af.consultar_ranking_devedores(client, tipo="receber")
    assert resultado["ranking"][0] == {"nome": "Cliente B", "valor": 500.0}
    assert resultado["ranking"][1] == {"nome": "Cliente A", "valor": 400.0}


def test_consultar_comissoes_soma_e_filtra_por_seguradora():
    client = FakeSupabaseClient(
        {
            "lotes_comissao": [
                {
                    "data_pagamento": "2026-08-10",
                    "valor_bruto": 1000.0,
                    "valor_liquido": 900.0,
                    "valor_irrf": 50.0,
                    "valor_iss": 30.0,
                    "valor_inss": 0.0,
                    "valor_pis_cofins_csll": 20.0,
                    "status": "conciliado",
                    "seguradoras": {"nome": "Suhai"},
                },
                {
                    "data_pagamento": "2026-08-11",
                    "valor_bruto": 500.0,
                    "valor_liquido": 480.0,
                    "valor_irrf": 10.0,
                    "valor_iss": 5.0,
                    "valor_inss": 0.0,
                    "valor_pis_cofins_csll": 5.0,
                    "status": "pendente",
                    "seguradoras": {"nome": "Porto Seguro"},
                },
            ]
        }
    )
    resultado = af.consultar_comissoes(client, seguradora="suhai")
    assert resultado["quantidade_lotes"] == 1
    assert resultado["total_liquido"] == 900.0


def test_consultar_fluxo_caixa_agrupa_por_mes():
    hoje_iso = date.today().isoformat()
    client = FakeSupabaseClient(
        {
            "ofx_transacoes": [
                {"data": hoje_iso, "valor": 1000.0, "contas_bancarias": {"empresa_id": "emp-1"}},
                {"data": hoje_iso, "valor": -400.0, "contas_bancarias": {"empresa_id": "emp-1"}},
            ]
        }
    )
    resultado = af.consultar_fluxo_caixa(client, meses=1)
    assert len(resultado["por_mes"]) == 1
    assert resultado["por_mes"][0]["receitas"] == 1000.0
    assert resultado["por_mes"][0]["despesas"] == 400.0


def test_consultar_dre_e_balanco_delegam_para_relatorios():
    client = FakeSupabaseClient({})
    dre = af.consultar_dre(client, "2026-08-01", "2026-08-31")
    assert dre["total_receitas"] == 0.0
    balanco = af.consultar_balanco(client)
    assert balanco["total_ativo"] == 0.0


def test_esta_configurado_depende_da_env_var(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert af.esta_configurado() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    assert af.esta_configurado() is True


def test_executar_tool_desconhecida_retorna_erro_sem_quebrar():
    resultado = af._executar_tool("nao_existe", {}, FakeSupabaseClient({}))
    assert "erro" in resultado


def test_executar_tool_excecao_e_capturada():
    def _falha(client, **kw):
        raise ValueError("boom")

    with patch.dict(af._FUNCOES, {"consultar_contas": _falha}):
        resultado = af._executar_tool("consultar_contas", {}, FakeSupabaseClient({}))
    assert "erro" in resultado


# ---------- loop de tool-use (IA mockada) ----------


def _bloco_texto(texto: str) -> MagicMock:
    bloco = MagicMock()
    bloco.type = "text"
    bloco.text = texto
    return bloco


def _bloco_tool_use(nome: str, entrada: dict, id_: str = "tool_1") -> MagicMock:
    bloco = MagicMock()
    bloco.type = "tool_use"
    bloco.name = nome
    bloco.input = entrada
    bloco.id = id_
    return bloco


def test_responder_sem_tool_use_retorna_texto_direto():
    with patch("assistente_financeiro.anthropic.Anthropic") as ClienteFalso:
        instancia = ClienteFalso.return_value
        resposta = MagicMock()
        resposta.stop_reason = "end_turn"
        resposta.content = [_bloco_texto("Você não tem nenhuma conta pendente.")]
        instancia.messages.create.return_value = resposta

        texto = af.responder(
            [{"role": "user", "content": "tenho algo pendente?"}], client=FakeSupabaseClient({})
        )

    assert texto == "Você não tem nenhuma conta pendente."


def test_responder_chama_tool_e_usa_resultado_real_nao_inventado():
    client = FakeSupabaseClient(
        {
            "lancamentos_previstos": [
                {"descricao": "Aluguel", "valor": 1000.0, "data_vencimento": "2026-08-05", "status": "previsto", "tipo": "pagar"},
            ]
        }
    )
    with patch("assistente_financeiro.anthropic.Anthropic") as ClienteFalso:
        instancia = ClienteFalso.return_value
        resposta_tool = MagicMock()
        resposta_tool.stop_reason = "tool_use"
        resposta_tool.content = [_bloco_tool_use("consultar_contas", {"tipo": "pagar"})]
        resposta_final = MagicMock()
        resposta_final.stop_reason = "end_turn"
        resposta_final.content = [_bloco_texto("Você tem R$ 1.000,00 a pagar (Aluguel).")]
        instancia.messages.create.side_effect = [resposta_tool, resposta_final]

        texto = af.responder([{"role": "user", "content": "quanto tenho a pagar?"}], client=client)

    assert "1.000,00" in texto
    segunda_chamada = instancia.messages.create.call_args_list[1].kwargs["messages"]
    tool_result = segunda_chamada[-1]["content"][0]["content"]
    dados = json.loads(tool_result)
    assert dados["total_valor"] == 1000.0  # veio da consulta real, não da IA


def test_responder_respeita_limite_de_rodadas():
    with patch("assistente_financeiro.anthropic.Anthropic") as ClienteFalso:
        instancia = ClienteFalso.return_value
        resposta_tool = MagicMock()
        resposta_tool.stop_reason = "tool_use"
        resposta_tool.content = [_bloco_tool_use("consultar_contas", {})]
        instancia.messages.create.return_value = resposta_tool

        texto = af.responder(
            [{"role": "user", "content": "pergunta"}], client=FakeSupabaseClient({}), max_rodadas=2
        )

    assert instancia.messages.create.call_count == 2
    assert "reformular" in texto.lower()
