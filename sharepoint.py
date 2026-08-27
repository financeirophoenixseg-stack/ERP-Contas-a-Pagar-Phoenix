"""Sincronização de anexos com o SharePoint (Microsoft Graph API).

Fluxo: o anexo é salvo primeiro no Supabase Storage (fonte principal). Depois,
uma cópia é enviada para a biblioteca de documentos do site SharePoint da
empresa, organizada em pastas por ano/mês/tipo (mesma estrutura do
storage_path usado no Supabase).

Autenticação: client-credentials (app-only), via app registrado no Entra ID
com permissão de aplicativo `Sites.Selected`, autorizada especificamente para
este site (concedido uma vez via Graph API com um token delegado de admin —
ver histórico do projeto). Não depende de nenhum usuário logado.

Se as variáveis MS_TENANT_ID/MS_CLIENT_ID/MS_CLIENT_SECRET/MS_SITE_ID não
estiverem configuradas, `esta_configurado()` retorna False e o chamador deve
simplesmente pular o envio ao SharePoint (o Supabase Storage continua
funcionando normalmente sem isso).
"""

from __future__ import annotations

import os
import time

import msal
import requests

GRAPH_URL = "https://graph.microsoft.com/v1.0"

_token_cache: dict = {"access_token": None, "expira_em": 0}


def esta_configurado() -> bool:
    return all(
        os.environ.get(v)
        for v in ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET", "MS_SITE_ID")
    )


def _obter_token() -> str:
    agora = time.time()
    if _token_cache["access_token"] and agora < _token_cache["expira_em"] - 60:
        return _token_cache["access_token"]

    tenant_id = os.environ["MS_TENANT_ID"]
    client_id = os.environ["MS_CLIENT_ID"]
    client_secret = os.environ["MS_CLIENT_SECRET"]

    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Falha ao obter token do Microsoft Graph: {result}")

    _token_cache["access_token"] = result["access_token"]
    _token_cache["expira_em"] = agora + result.get("expires_in", 3600)
    return result["access_token"]


def enviar_arquivo(caminho_destino: str, conteudo: bytes) -> str:
    """Envia `conteudo` para `caminho_destino` (relativo à raiz da biblioteca
    de documentos padrão do site, ex.: '2026/08/boleto/xxx_arquivo.pdf').
    Cria as pastas intermediárias automaticamente. Retorna a webUrl do arquivo.

    Levanta RuntimeError se a chamada ao Graph falhar (chamador decide se
    trata como erro fatal ou apenas loga um aviso, já que o Supabase Storage
    é a cópia principal e não deve ser bloqueado por isso).
    """
    site_id = os.environ["MS_SITE_ID"]
    token = _obter_token()

    caminho_url = "/".join(
        requests.utils.quote(parte) for parte in caminho_destino.split("/")
    )
    url = f"{GRAPH_URL}/sites/{site_id}/drive/root:/{caminho_url}:/content"

    resp = requests.put(
        url,
        headers={"Authorization": f"Bearer {token}"},
        data=conteudo,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Erro ao enviar para o SharePoint ({resp.status_code}): {resp.text}")

    return resp.json().get("webUrl", "")


def remover_arquivo(caminho_destino: str) -> None:
    """Remove o arquivo correspondente no SharePoint. Silencioso se não existir."""
    site_id = os.environ["MS_SITE_ID"]
    token = _obter_token()

    caminho_url = "/".join(
        requests.utils.quote(parte) for parte in caminho_destino.split("/")
    )
    url = f"{GRAPH_URL}/sites/{site_id}/drive/root:/{caminho_url}"

    resp = requests.delete(url, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code not in (200, 204, 404):
        raise RuntimeError(f"Erro ao remover do SharePoint ({resp.status_code}): {resp.text}")
