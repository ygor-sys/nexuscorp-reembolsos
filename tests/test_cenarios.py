"""Cenários de homologação 01 a 08 do enunciado."""
from datetime import datetime, timedelta, timezone

import jwt
from sqlmodel import Session, select

from app.enums import Decisao, Etapa, Perfil, Situacao
from app.models import HistoricoAnalise, Reembolso, Usuario
from tests.helpers import acao, criar, criar_e_enviar, dados_reembolso, enviar


def test_cenario_01_acesso_indevido(client, entrar):
    """Ana (Comercial) tenta ler a solicitação de Bruno (Tecnologia) pelo identificador."""
    ana, bruno = entrar("ana"), entrar("bruno")
    do_bruno = criar(client, bruno, valor=999.90, justificativa="Hospedagem confidencial do Bruno")
    url = f"/reembolsos/{do_bruno['id']}"

    resposta = client.get(url, headers=ana)
    assert resposta.status_code == 404
    assert "999" not in resposta.text and "Bruno" not in resposta.text

    # Mesma resposta de um id que não existe: não revela que a solicitação existe.
    inexistente = client.get("/reembolsos/987654", headers=ana)
    assert inexistente.status_code == 404
    assert inexistente.json() == resposta.json()

    # Nenhuma operação sobre o registro alheio é possível.
    assert client.get(f"{url}/historico", headers=ana).status_code == 404
    assert client.patch(url, json={"valor": 1}, headers=ana).status_code == 404
    assert client.delete(url, headers=ana).status_code == 404
    assert client.post(f"{url}/enviar", headers=ana).status_code == 404
    assert client.get("/reembolsos", headers=ana).json() == []


def test_cenario_02_gestor_de_outro_departamento(client, engine, entrar):
    """Patrícia (gestora do Comercial) tenta aprovar despesa de Tecnologia."""
    patricia, tiago, bruno = entrar("patricia"), entrar("tiago"), entrar("bruno")
    r = criar_e_enviar(client, bruno)

    acao(client, patricia, r["id"], "gestor/aprovar", esperado=403)
    acao(client, patricia, r["id"], "gestor/recusar", json={"observacao": "Não é minha área"}, esperado=403)
    assert client.get(f"/reembolsos/{r['id']}", headers=patricia).status_code == 404

    with Session(engine) as s:  # nada foi alterado no banco
        assert s.get(Reembolso, r["id"]).situacao == Situacao.AGUARDANDO_GESTOR
        historico = s.exec(select(HistoricoAnalise).where(HistoricoAnalise.reembolso_id == r["id"])).all()
        assert [h.etapa for h in historico] == [Etapa.SUBMISSAO]

    # O gestor do departamento correto consegue.
    assert acao(client, tiago, r["id"], "gestor/aprovar").json()["situacao"] == "aguardando_financeiro"


def test_cenario_03_credenciais_incorretas(client, entrar):
    senha_errada = client.post("/auth/login", json={"email": "ana@nexuscorp.com", "senha": "SenhaErrada1"})
    email_inexistente = client.post("/auth/login", json={"email": "ninguem@nexuscorp.com", "senha": "Senha@123"})

    assert senha_errada.status_code == 401
    assert email_inexistente.status_code == 401
    assert senha_errada.json() == email_inexistente.json()  # não revela se o e-mail existe
    for texto in (senha_errada.text, email_inexistente.text):
        assert "scrypt" not in texto and "hash" not in texto.lower()
    assert "access_token" not in senha_errada.text

    # Sem token, nenhuma rota restrita responde.
    assert client.get("/reembolsos").status_code == 401


def test_cenario_04_tentativa_de_alteracao_de_permissoes(client, engine, demo, entrar):
    ana = entrar("ana")
    comercial = demo["departamentos"]["Comercial"]
    financeiro = demo["departamentos"]["Financeiro"]

    # a) Autocadastro tentando nascer como financeiro.
    corpo = {
        "nome": "Intruso Teste",
        "email": "intruso@nexuscorp.com",
        "senha": "Senha@123",
        "departamento_id": comercial,
        "perfil": "financeiro",
    }
    assert client.post("/auth/cadastro", json=corpo).status_code == 422
    with Session(engine) as s:
        assert s.exec(select(Usuario).where(Usuario.email == "intruso@nexuscorp.com")).first() is None

    # b) Atualização de cadastro tentando mudar perfil, departamento ou status.
    for extra in ({"perfil": "financeiro"}, {"departamento_id": financeiro}, {"ativo": True}):
        assert client.patch("/usuarios/me", json={"nome": "Ana Souza", **extra}, headers=ana).status_code == 422
    eu = client.get("/usuarios/me", headers=ana).json()
    assert eu["perfil"] == "colaborador" and eu["departamento_id"] == comercial

    # c) Token forjado com perfil financeiro, assinado com outra chave.
    agora = datetime.now(timezone.utc)
    forjado = jwt.encode(
        {"sub": str(demo["usuarios"]["ana"]), "jti": "x", "tv": 0, "iat": agora,
         "exp": agora + timedelta(minutes=5), "perfil": "financeiro"},
        "outra-chave-qualquer-com-mais-de-32-bytes-123456",
        algorithm="HS256",
    )
    assert client.get("/reembolsos", headers={"Authorization": f"Bearer {forjado}"}).status_code == 401

    # d) Enviar campos de controle ao registrar uma solicitação.
    for extra in ({"solicitante_id": 2}, {"situacao": "aprovada"}, {"departamento_id": financeiro}):
        r = client.post("/reembolsos", json=dados_reembolso(**extra), headers=ana)
        assert r.status_code == 422

    # e) Colaborador não alcança as rotas de financeiro nem de gestor.
    solicitacao = criar_e_enviar(client, ana)
    acao(client, ana, solicitacao["id"], "financeiro/pagar", esperado=403)
    acao(client, ana, solicitacao["id"], "gestor/aprovar", esperado=403)

    # f) O autocadastro legítimo sempre resulta em colaborador.
    ok = client.post("/auth/cadastro", json={k: v for k, v in corpo.items() if k != "perfil"})
    assert ok.status_code == 201 and ok.json()["perfil"] == "colaborador"


def test_cenario_05_aprovacao_fora_da_sequencia(client, entrar):
    ana, carla = entrar("ana"), entrar("carla")
    r = criar_e_enviar(client, ana)  # aguardando_gestor

    resposta = acao(client, carla, r["id"], "financeiro/aprovar", esperado=409)
    assert "gestor" in resposta.json()["detail"]
    acao(client, carla, r["id"], "financeiro/recusar", json={"observacao": "Tentando pular etapa"}, esperado=409)
    acao(client, carla, r["id"], "financeiro/pagar", esperado=409)
    assert client.get(f"/reembolsos/{r['id']}", headers=ana).json()["situacao"] == "aguardando_gestor"


def test_cenario_06_manipulacao_apos_envio(client, engine, entrar):
    ana = entrar("ana")
    r = criar(client, ana, valor=180.00)
    enviar(client, ana, r["id"])
    url = f"/reembolsos/{r['id']}"

    alteracao = client.patch(url, json={"valor": 1800.00}, headers=ana)
    assert alteracao.status_code == 409
    assert client.patch(url, json={"justificativa": "Texto novo qualquer"}, headers=ana).status_code == 409
    assert client.delete(url, headers=ana).status_code == 409

    assert client.get(url, headers=ana).json()["valor"] == 180.0
    with Session(engine) as s:
        assert s.get(Reembolso, r["id"]).valor_centavos == 18000


def test_cenario_07_consulta_com_filtros(client, demo, entrar):
    ana, bruno, patricia, tiago = entrar("ana"), entrar("bruno"), entrar("patricia"), entrar("tiago")
    r1 = criar_e_enviar(client, ana, categoria="transporte")
    r2 = criar_e_enviar(client, ana, categoria="alimentacao")
    criar(client, ana, categoria="hospedagem")  # rascunho: privado do autor
    r4 = criar_e_enviar(client, bruno, categoria="materiais")

    pendentes = client.get("/reembolsos", params={"situacao": "aguardando_gestor"}, headers=patricia).json()
    assert {x["id"] for x in pendentes} == {r1["id"], r2["id"]}
    assert {x["departamento_id"] for x in pendentes} == {demo["departamentos"]["Comercial"]}

    sem_filtro = client.get("/reembolsos", headers=patricia).json()
    assert {x["id"] for x in sem_filtro} == {r1["id"], r2["id"]}  # sem rascunho e sem Tecnologia

    outro_dep = client.get("/reembolsos", params={"departamento_id": demo["departamentos"]["Tecnologia"]}, headers=patricia)
    assert outro_dep.status_code == 200 and outro_dep.json() == []

    transporte = client.get(
        "/reembolsos", params={"situacao": "aguardando_gestor", "categoria": "transporte"}, headers=patricia
    ).json()
    assert [x["id"] for x in transporte] == [r1["id"]]

    do_tiago = client.get("/reembolsos", headers=tiago).json()
    assert [x["id"] for x in do_tiago] == [r4["id"]]


def test_cenario_08_historico_completo(client, entrar, demo):
    ana, patricia, carla = entrar("ana"), entrar("patricia"), entrar("carla")
    r = criar_e_enviar(client, ana)
    acao(client, patricia, r["id"], "gestor/aprovar", json={"observacao": "Conferido com o cliente"})
    acao(client, carla, r["id"], "financeiro/aprovar", json={"observacao": "Valor dentro da política"})
    pago = acao(client, carla, r["id"], "financeiro/pagar", json={"observacao": "Pago via PIX interno"}).json()
    assert pago["situacao"] == "paga"

    for quem in (ana, patricia, carla):  # todos os envolvidos enxergam o histórico
        historico = client.get(f"/reembolsos/{r['id']}/historico", headers=quem)
        assert historico.status_code == 200

    h = client.get(f"/reembolsos/{r['id']}/historico", headers=ana).json()
    assert [(x["etapa"], x["decisao"], x["responsavel_nome"]) for x in h] == [
        ("submissao", "enviada", "Ana Souza"),
        ("gestor", "aprovada", "Patrícia Alves"),
        ("financeiro", "aprovada", "Carla Mendes"),
        ("pagamento", "paga", "Carla Mendes"),
    ]
    assert [x["responsavel_perfil"] for x in h] == ["colaborador", "gestor", "financeiro", "financeiro"]
    assert h[1]["observacao"] == "Conferido com o cliente"
    assert all(x["data_hora"] for x in h)

    # Processo encerrado: nenhuma nova operação.
    acao(client, patricia, r["id"], "gestor/aprovar", esperado=409)
    acao(client, carla, r["id"], "financeiro/pagar", esperado=409)
    assert client.patch(f"/reembolsos/{r['id']}", json={"valor": 5}, headers=ana).status_code == 409
    assert client.delete(f"/reembolsos/{r['id']}", headers=ana).status_code == 409
