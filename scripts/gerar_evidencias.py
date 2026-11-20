"""Executa os 8 cenários de homologação contra a API real (banco temporário) e gera
docs/EVIDENCIAS.md com cada requisição e resposta.

    python scripts/gerar_evidencias.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

_pasta = tempfile.mkdtemp(prefix="nexuscorp_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_pasta, 'evidencias.db').as_posix()}"
os.environ["SECRET_KEY"] = "evidencias-" + "x" * 48

from datetime import datetime  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import SENHA_DEMO, popular_demo  # noqa: E402
from app.utils import hoje  # noqa: E402

linhas: list[str] = []
tokens: dict[str, str] = {}
divergencias: list[str] = []


def titulo(texto: str, descricao: str = "") -> None:
    linhas.append(f"\n## {texto}\n")
    if descricao:
        linhas.append(f"{descricao}\n")


def chamar(client, metodo, caminho, usuario=None, corpo=None, params=None, esperado=None):
    headers = {"Authorization": f"Bearer {tokens[usuario]}"} if usuario else {}
    resposta = client.request(metodo, caminho, headers=headers, json=corpo, params=params)
    quem = usuario or "sem token"
    consulta = f"?{'&'.join(f'{k}={v}' for k, v in params.items())}" if params else ""
    linhas.append(f"**{metodo} {caminho}{consulta}** — usuário: `{quem}`\n")
    if corpo is not None:
        mostrado = {k: ("********" if k in ("senha", "senha_atual", "nova_senha") else v) for k, v in corpo.items()}
        linhas.append("```json\n" + json.dumps(mostrado, ensure_ascii=False, indent=2) + "\n```")
    try:
        dados = resposta.json()
        if isinstance(dados, dict) and "access_token" in dados:
            dados = {**dados, "access_token": "<jwt omitido>"}
        texto = json.dumps(dados, ensure_ascii=False, indent=2)
    except ValueError:
        texto = "(sem corpo)"
    marca = ""
    if esperado is not None and resposta.status_code != esperado:
        marca = f" ⚠️ ESPERADO {esperado}"
        divergencias.append(f"{metodo} {caminho}: esperado {esperado}, obtido {resposta.status_code}")
    linhas.append(f"Resposta: **HTTP {resposta.status_code}**{marca}\n\n```json\n{texto}\n```\n")
    return resposta


def entrar(client, chave):
    r = client.post("/auth/login", json={"email": f"{chave}@nexuscorp.com", "senha": SENHA_DEMO})
    tokens[chave] = r.json()["access_token"]


def novo(valor, categoria, ref, justificativa):
    return {"categoria": categoria, "valor": valor, "data_despesa": hoje().isoformat(),
            "justificativa": justificativa, "comprovante_ref": ref}


def main() -> int:
    with TestClient(app) as client:  # o lifespan cria as tabelas no banco temporário
        with Session(engine) as s:
            popular_demo(s)
        for chave in ("ana", "bruno", "patricia", "tiago", "carla", "fabio"):
            entrar(client, chave)

        titulo("Cenário 01 — Acesso indevido",
               "Ana (Comercial) tenta consultar a solicitação de Bruno (Tecnologia).")
        bruno = chamar(client, "POST", "/reembolsos", "bruno",
                       novo(999.90, "hospedagem", "NF-BRUNO-01", "Hospedagem em evento de tecnologia"), esperado=201).json()
        chamar(client, "GET", f"/reembolsos/{bruno['id']}", "ana", esperado=404)
        chamar(client, "GET", "/reembolsos/987654", "ana", esperado=404)

        titulo("Cenário 02 — Gestor de outro departamento",
               "Patrícia (gestora do Comercial) tenta aprovar despesa de Tecnologia.")
        chamar(client, "POST", f"/reembolsos/{bruno['id']}/enviar", "bruno", esperado=200)
        chamar(client, "POST", f"/reembolsos/{bruno['id']}/gestor/aprovar", "patricia", esperado=403)
        chamar(client, "GET", f"/reembolsos/{bruno['id']}/historico", "bruno", esperado=200)

        titulo("Cenário 03 — Credenciais incorretas")
        chamar(client, "POST", "/auth/login", None,
               {"email": "ana@nexuscorp.com", "senha": "SenhaErrada1"}, esperado=401)
        chamar(client, "POST", "/auth/login", None,
               {"email": "naoexiste@nexuscorp.com", "senha": "SenhaErrada1"}, esperado=401)
        chamar(client, "GET", "/reembolsos", None, esperado=401)

        titulo("Cenário 04 — Tentativa de alteração de permissões")
        chamar(client, "POST", "/auth/cadastro", None,
               {"nome": "Intruso Teste", "email": "intruso@nexuscorp.com", "senha": "Senha@123",
                "departamento_id": 1, "perfil": "financeiro"}, esperado=422)
        chamar(client, "PATCH", "/usuarios/me", "ana", {"perfil": "financeiro"}, esperado=422)
        chamar(client, "PATCH", "/usuarios/me", "ana", {"departamento_id": 3}, esperado=422)
        chamar(client, "GET", "/usuarios/me", "ana", esperado=200)

        titulo("Cenário 05 — Aprovação fora da sequência",
               "O financeiro (Carla) tenta aprovar uma solicitação que ainda aguarda o gestor.")
        ana1 = chamar(client, "POST", "/reembolsos", "ana",
                      novo(180.00, "transporte", "NF-ANA-01", "Táxi para reunião com cliente"), esperado=201).json()
        chamar(client, "POST", f"/reembolsos/{ana1['id']}/enviar", "ana", esperado=200)
        chamar(client, "POST", f"/reembolsos/{ana1['id']}/financeiro/aprovar", "carla", esperado=409)

        titulo("Cenário 06 — Manipulação de solicitação",
               "Após o envio, Ana tenta mudar o valor de R$ 180,00 para R$ 1.800,00.")
        chamar(client, "PATCH", f"/reembolsos/{ana1['id']}", "ana", {"valor": 1800.00}, esperado=409)
        chamar(client, "GET", f"/reembolsos/{ana1['id']}", "ana", esperado=200)

        titulo("Cenário 07 — Consulta com filtros",
               "Patrícia consulta as pendentes do seu departamento; nada de Tecnologia aparece.")
        chamar(client, "POST", "/reembolsos", "ana",
               novo(60.00, "alimentacao", "NF-ANA-02", "Almoço com cliente em visita externa"), esperado=201)
        chamar(client, "GET", "/reembolsos", "patricia", params={"situacao": "aguardando_gestor"}, esperado=200)
        chamar(client, "GET", "/reembolsos", "patricia",
               params={"situacao": "aguardando_gestor", "categoria": "transporte"}, esperado=200)
        chamar(client, "GET", "/reembolsos", "patricia", params={"departamento_id": 2}, esperado=200)

        titulo("Cenário 08 — Histórico financeiro",
               "Aprovação do gestor, aprovação do financeiro e pagamento, com todos os responsáveis.")
        chamar(client, "POST", f"/reembolsos/{ana1['id']}/gestor/aprovar", "patricia",
               {"observacao": "Conferido com o cliente"}, esperado=200)
        chamar(client, "POST", f"/reembolsos/{ana1['id']}/financeiro/aprovar", "carla",
               {"observacao": "Valor dentro da política"}, esperado=200)
        chamar(client, "POST", f"/reembolsos/{ana1['id']}/financeiro/pagar", "carla",
               {"observacao": "Pagamento registrado"}, esperado=200)
        chamar(client, "GET", f"/reembolsos/{ana1['id']}/historico", "ana", esperado=200)
        chamar(client, "PATCH", f"/reembolsos/{ana1['id']}", "ana", {"valor": 5}, esperado=409)

        titulo("Extra — Recusa exige justificativa (RN11) e logout encerra o token (RN14)")
        ana3 = chamar(client, "POST", "/reembolsos", "ana",
                      novo(75.00, "materiais", "NF-ANA-03", "Material de escritório para o cliente"), esperado=201).json()
        chamar(client, "POST", f"/reembolsos/{ana3['id']}/enviar", "ana", esperado=200)
        chamar(client, "POST", f"/reembolsos/{ana3['id']}/gestor/recusar", "patricia", {}, esperado=422)
        chamar(client, "POST", f"/reembolsos/{ana3['id']}/gestor/recusar", "patricia",
               {"observacao": "Despesa sem relação com o serviço prestado"}, esperado=200)
        chamar(client, "POST", "/auth/logout", "ana", esperado=204)
        chamar(client, "GET", "/reembolsos", "ana", esperado=401)

    cabecalho = [
        "# Evidências de execução",
        "",
        f"Geradas automaticamente por `scripts/gerar_evidencias.py` em {datetime.now():%d/%m/%Y %H:%M}, "
        "executando a API real contra um banco SQLite temporário.",
        "",
        f"Divergências em relação ao esperado: **{len(divergencias)}**",
    ]
    destino = RAIZ / "docs" / "EVIDENCIAS.md"
    destino.write_text("\n".join(cabecalho + linhas) + "\n", encoding="utf-8")
    print(f"Arquivo gerado: {destino}")
    for d in divergencias:
        print("DIVERGÊNCIA:", d)
    return 1 if divergencias else 0


if __name__ == "__main__":
    sys.exit(main())
