"""Integração bancária via Open Finance, usando a Pluggy como agregador
certificado (conectar diretamente com cada banco exigiria virar um
participante registrado do Open Finance Brasil — certificado próprio,
homologação de segurança — inviável pra uma corretora pequena. A Pluggy já
fez essa parte pesada e expõe uma API simples).

Fluxo (documentado em https://docs.pluggy.ai):
1. `obter_api_key()` — autentica com client_id/client_secret, retorna uma
   API key temporária (válida ~2h, renovada automaticamente aqui).
2. `criar_connect_token()` — gera um token de uso único pro widget "Pluggy
   Connect" (a tela onde o usuário escolhe o banco e faz login/consentimento
   — a senha do banco nunca passa pelo nosso sistema, é tudo dentro do
   widget oficial da Pluggy/banco).
3. O widget roda no navegador (embutido via HTML/iframe na tela de
   Configurações) e, ao terminar, devolve um `item_id` — a conexão com
   aquele banco.
4. `listar_contas(item_id)` — lista as contas dentro daquele banco
   conectado, pra escolher qual é a conta cadastrada no nosso sistema.
5. `listar_transacoes(account_id, desde)` — busca o extrato, no mesmo
   formato que o importador de OFX já processa.

Nada disso foi testado contra a API real ainda — só existe conta de
desenvolvedor na Pluggy quando o usuário se cadastrar. Ver PLANO.md."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests

BASE_URL = "https://api.pluggy.ai"

_cache_api_key: dict = {"valor": None, "expira_em": 0}


def esta_configurado() -> bool:
    return bool(os.environ.get("PLUGGY_CLIENT_ID")) and bool(os.environ.get("PLUGGY_CLIENT_SECRET"))


def obter_api_key() -> str:
    """Autentica com client_id/client_secret e retorna a API key (cacheada
    em memória até perto de expirar)."""
    agora = time.time()
    if _cache_api_key["valor"] and agora < _cache_api_key["expira_em"] - 60:
        return _cache_api_key["valor"]

    resp = requests.post(
        f"{BASE_URL}/auth",
        json={
            "clientId": os.environ["PLUGGY_CLIENT_ID"],
            "clientSecret": os.environ["PLUGGY_CLIENT_SECRET"],
        },
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Erro ao autenticar na Pluggy ({resp.status_code}): {resp.text}")

    dados = resp.json()
    _cache_api_key["valor"] = dados["apiKey"]
    _cache_api_key["expira_em"] = agora + 2 * 60 * 60  # a Pluggy documenta ~2h de validade
    return dados["apiKey"]


def criar_connect_token(item_id: str | None = None) -> str:
    """Gera o token de uso único pro widget Pluggy Connect. Passar `item_id`
    reabre a conexão de um banco já ligado (ex.: quando expira/precisa
    reautenticar), sem isso abre a tela de escolher um banco novo."""
    api_key = obter_api_key()
    corpo = {"itemId": item_id} if item_id else {}

    resp = requests.post(f"{BASE_URL}/connect_token", json=corpo, headers={"X-API-KEY": api_key})
    if resp.status_code != 200:
        raise RuntimeError(f"Erro ao criar connect token ({resp.status_code}): {resp.text}")

    return resp.json()["accessToken"]


@dataclass
class ContaPluggy:
    id: str
    nome: str
    tipo: str
    numero: str | None
    saldo: float | None


def listar_contas(item_id: str) -> list[ContaPluggy]:
    """Lista as contas dentro de um banco já conectado (item_id)."""
    api_key = obter_api_key()
    resp = requests.get(f"{BASE_URL}/accounts", params={"itemId": item_id}, headers={"X-API-KEY": api_key})
    if resp.status_code != 200:
        raise RuntimeError(f"Erro ao listar contas ({resp.status_code}): {resp.text}")

    return [
        ContaPluggy(
            id=c["id"],
            nome=c.get("name", ""),
            tipo=c.get("subtype", c.get("type", "")),
            numero=c.get("number"),
            saldo=c.get("balance"),
        )
        for c in resp.json().get("results", [])
    ]


@dataclass
class TransacaoPluggy:
    id: str
    data: str
    descricao: str
    valor: float


def listar_transacoes(account_id: str, desde: str | None = None) -> list[TransacaoPluggy]:
    """Busca o extrato de uma conta (opcionalmente a partir de uma data,
    'AAAA-MM-DD') — mesmo formato que o importador de OFX processa
    (data/descrição/valor), pra alimentar o mesmo motor de conciliação."""
    api_key = obter_api_key()
    params = {"accountId": account_id, "pageSize": 500}
    if desde:
        params["from"] = desde

    resp = requests.get(f"{BASE_URL}/transactions", params=params, headers={"X-API-KEY": api_key})
    if resp.status_code != 200:
        raise RuntimeError(f"Erro ao listar transações ({resp.status_code}): {resp.text}")

    return [
        TransacaoPluggy(id=t["id"], data=t["date"][:10], descricao=t.get("description", ""), valor=t["amount"])
        for t in resp.json().get("results", [])
    ]
