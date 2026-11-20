"""Funções auxiliares para montar cenários de teste."""
from uuid import uuid4

from app.utils import hoje


def dados_reembolso(**alteracoes) -> dict:
    dados = {
        "categoria": "transporte",
        "valor": 180.00,
        "data_despesa": hoje().isoformat(),
        "justificativa": "Deslocamento para reunião com cliente",
        "comprovante_ref": f"NF-{uuid4().hex[:8]}",
    }
    dados.update(alteracoes)
    return dados


def criar(client, headers, **alteracoes) -> dict:
    resposta = client.post("/reembolsos", json=dados_reembolso(**alteracoes), headers=headers)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def enviar(client, headers, reembolso_id: int) -> dict:
    resposta = client.post(f"/reembolsos/{reembolso_id}/enviar", headers=headers)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def criar_e_enviar(client, headers, **alteracoes) -> dict:
    r = criar(client, headers, **alteracoes)
    return enviar(client, headers, r["id"])


def acao(client, headers, reembolso_id: int, caminho: str, json=None, esperado: int = 200):
    """Executa uma ação de análise (ex.: 'gestor/aprovar') e confere o status HTTP."""
    resposta = client.post(f"/reembolsos/{reembolso_id}/{caminho}", headers=headers, json=json)
    assert resposta.status_code == esperado, f"{caminho}: {resposta.status_code} {resposta.text}"
    return resposta
