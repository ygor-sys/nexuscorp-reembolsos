"""Regras de negócio RN01 a RN15 e requisitos técnicos."""
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.models import Usuario
from app.security import criar_token
from app.utils import hoje
from tests.helpers import acao, criar, criar_e_enviar, dados_reembolso, enviar


# --------------------------------------------------------------------------- RN01
@pytest.mark.parametrize(
    "metodo,caminho",
    [
        ("GET", "/reembolsos"),
        ("POST", "/reembolsos"),
        ("GET", "/reembolsos/1"),
        ("GET", "/reembolsos/1/historico"),
        ("PATCH", "/reembolsos/1"),
        ("DELETE", "/reembolsos/1"),
        ("POST", "/reembolsos/1/enviar"),
        ("POST", "/reembolsos/1/gestor/aprovar"),
        ("POST", "/reembolsos/1/financeiro/pagar"),
        ("GET", "/usuarios/me"),
        ("POST", "/auth/logout"),
    ],
)
def test_rn01_sem_token_nao_acessa_rotas_restritas(client, metodo, caminho):
    resposta = client.request(metodo, caminho)
    assert resposta.status_code == 401
    assert resposta.headers.get("www-authenticate") == "Bearer"


def test_rn01_token_invalido_e_rejeitado(client):
    assert client.get("/reembolsos", headers={"Authorization": "Bearer lixo.lixo.lixo"}).status_code == 401
    assert client.get("/reembolsos", headers={"Authorization": "Basic abc"}).status_code == 401


# --------------------------------------------------------------------------- RN04
@pytest.mark.parametrize("valor", [0, -1, -180.5])
def test_rn04_valor_deve_ser_positivo(client, entrar, valor):
    r = client.post("/reembolsos", json=dados_reembolso(valor=valor), headers=entrar("ana"))
    assert r.status_code == 422


def test_rn04_valor_com_mais_de_duas_casas_e_rejeitado(client, entrar):
    r = client.post("/reembolsos", json=dados_reembolso(valor=10.999), headers=entrar("ana"))
    assert r.status_code == 422


# --------------------------------------------------------------------------- RN05
def test_rn05_comprovante_duplicado_do_mesmo_colaborador(client, entrar):
    ana, bruno = entrar("ana"), entrar("bruno")
    criar(client, ana, comprovante_ref="NF-12345")

    repetido = client.post("/reembolsos", json=dados_reembolso(comprovante_ref="NF-12345"), headers=ana)
    assert repetido.status_code == 409
    variacao = client.post("/reembolsos", json=dados_reembolso(comprovante_ref="  nf-12345 "), headers=ana)
    assert variacao.status_code == 409

    # Outro colaborador pode usar a mesma referência.
    assert client.post("/reembolsos", json=dados_reembolso(comprovante_ref="NF-12345"), headers=bruno).status_code == 201


def test_rn05_duplicidade_tambem_vale_na_edicao(client, entrar):
    ana = entrar("ana")
    criar(client, ana, comprovante_ref="NF-AAA")
    outro = criar(client, ana, comprovante_ref="NF-BBB")
    assert client.patch(f"/reembolsos/{outro['id']}", json={"comprovante_ref": "NF-AAA"}, headers=ana).status_code == 409
    # Reaplicar a própria referência não é duplicidade.
    assert client.patch(f"/reembolsos/{outro['id']}", json={"comprovante_ref": "NF-BBB"}, headers=ana).status_code == 200


# --------------------------------------------------------------------------- RN06
def test_rn06_data_futura_e_rejeitada(client, entrar):
    ana = entrar("ana")
    amanha = (hoje() + timedelta(days=1)).isoformat()
    assert client.post("/reembolsos", json=dados_reembolso(data_despesa=amanha), headers=ana).status_code == 422
    assert client.post("/reembolsos", json=dados_reembolso(data_despesa=hoje().isoformat()), headers=ana).status_code == 201
    ontem = (hoje() - timedelta(days=1)).isoformat()
    assert client.post("/reembolsos", json=dados_reembolso(data_despesa=ontem), headers=ana).status_code == 201


def test_rn06_data_futura_tambem_e_rejeitada_na_edicao(client, entrar):
    ana = entrar("ana")
    r = criar(client, ana)
    amanha = (hoje() + timedelta(days=1)).isoformat()
    assert client.patch(f"/reembolsos/{r['id']}", json={"data_despesa": amanha}, headers=ana).status_code == 422


# --------------------------------------------------------------------------- RN07
def test_rn07_rascunho_pode_ser_alterado_e_excluido(client, entrar):
    ana = entrar("ana")
    r = criar(client, ana, valor=50)
    alterado = client.patch(f"/reembolsos/{r['id']}", json={"valor": 75.5, "categoria": "materiais"}, headers=ana)
    assert alterado.status_code == 200
    assert alterado.json()["valor"] == 75.5 and alterado.json()["categoria"] == "materiais"

    assert client.delete(f"/reembolsos/{r['id']}", headers=ana).status_code == 204
    assert client.get(f"/reembolsos/{r['id']}", headers=ana).status_code == 404


def test_rn07_atualizacao_vazia_ou_nula_e_invalida(client, entrar):
    ana = entrar("ana")
    r = criar(client, ana)
    assert client.patch(f"/reembolsos/{r['id']}", json={}, headers=ana).status_code == 422
    assert client.patch(f"/reembolsos/{r['id']}", json={"valor": None}, headers=ana).status_code == 422


def test_rn07_solicitacao_recusada_e_imutavel(client, entrar):
    ana, patricia = entrar("ana"), entrar("patricia")
    r = criar_e_enviar(client, ana)
    acao(client, patricia, r["id"], "gestor/recusar", json={"observacao": "Fora da política da empresa"})
    assert client.patch(f"/reembolsos/{r['id']}", json={"valor": 2}, headers=ana).status_code == 409
    assert client.delete(f"/reembolsos/{r['id']}", headers=ana).status_code == 409
    assert client.post(f"/reembolsos/{r['id']}/enviar", headers=ana).status_code == 409


def test_enviar_duas_vezes_e_conflito(client, entrar):
    ana = entrar("ana")
    r = criar_e_enviar(client, ana)
    assert client.post(f"/reembolsos/{r['id']}/enviar", headers=ana).status_code == 409


# ----------------------------------------------------------------------- RN08 / RN10
def test_rn08_rn10_pagamento_so_apos_aprovacao_financeira(client, entrar):
    ana, patricia, carla = entrar("ana"), entrar("patricia"), entrar("carla")
    r = criar_e_enviar(client, ana)
    acao(client, carla, r["id"], "financeiro/pagar", esperado=409)  # aguardando gestor
    acao(client, patricia, r["id"], "gestor/aprovar")
    resposta = acao(client, carla, r["id"], "financeiro/pagar", esperado=409)  # aguardando financeiro
    assert "RN10" in resposta.json()["detail"]
    acao(client, carla, r["id"], "financeiro/aprovar")
    assert acao(client, carla, r["id"], "financeiro/pagar").json()["situacao"] == "paga"


def test_gestor_nao_decide_duas_vezes(client, entrar):
    ana, patricia = entrar("ana"), entrar("patricia")
    r = criar_e_enviar(client, ana)
    acao(client, patricia, r["id"], "gestor/aprovar")
    acao(client, patricia, r["id"], "gestor/aprovar", esperado=409)
    acao(client, patricia, r["id"], "gestor/recusar", json={"observacao": "Mudei de ideia agora"}, esperado=409)


def test_rascunho_alheio_nao_pode_ser_analisado(client, entrar):
    ana, patricia = entrar("ana"), entrar("patricia")
    r = criar(client, ana)  # continua em rascunho
    acao(client, patricia, r["id"], "gestor/aprovar", esperado=404)
    assert client.get("/reembolsos", headers=patricia).json() == []


# --------------------------------------------------------------------------- RN09
def test_rn09_gestor_nao_aprova_a_propria_solicitacao(client, entrar):
    patricia = entrar("patricia")
    r = criar_e_enviar(client, patricia)  # gestor também pode registrar despesas
    acao(client, patricia, r["id"], "gestor/aprovar", esperado=403)
    acao(client, patricia, r["id"], "gestor/recusar", json={"observacao": "Recusando a mim mesma"}, esperado=403)
    assert client.get(f"/reembolsos/{r['id']}", headers=patricia).json()["situacao"] == "aguardando_gestor"


def test_rn09_financeiro_nao_aprova_nem_paga_a_propria_solicitacao(client, entrar):
    carla, gabriel, fabio = entrar("carla"), entrar("gabriel"), entrar("fabio")
    r = criar_e_enviar(client, carla)
    acao(client, carla, r["id"], "gestor/aprovar", esperado=403)  # perfil errado
    acao(client, gabriel, r["id"], "gestor/aprovar")  # gestor do departamento Financeiro
    acao(client, carla, r["id"], "financeiro/aprovar", esperado=403)  # própria autoria
    acao(client, fabio, r["id"], "financeiro/aprovar")
    acao(client, carla, r["id"], "financeiro/pagar", esperado=403)  # própria autoria
    assert acao(client, fabio, r["id"], "financeiro/pagar").json()["situacao"] == "paga"


# --------------------------------------------------------------------------- RN11
def test_rn11_recusa_exige_justificativa_registrada(client, entrar):
    ana, patricia = entrar("ana"), entrar("patricia")
    r = criar_e_enviar(client, ana)
    acao(client, patricia, r["id"], "gestor/recusar", esperado=422)
    acao(client, patricia, r["id"], "gestor/recusar", json={"observacao": "   "}, esperado=422)
    acao(client, patricia, r["id"], "gestor/recusar", json={}, esperado=422)
    assert client.get(f"/reembolsos/{r['id']}", headers=ana).json()["situacao"] == "aguardando_gestor"

    acao(client, patricia, r["id"], "gestor/recusar", json={"observacao": "Despesa sem relação com o serviço"})
    historico = client.get(f"/reembolsos/{r['id']}/historico", headers=ana).json()
    assert historico[-1]["decisao"] == "recusada"
    assert historico[-1]["observacao"] == "Despesa sem relação com o serviço"


def test_rn11_financeiro_tambem_exige_justificativa(client, entrar):
    ana, patricia, carla = entrar("ana"), entrar("patricia"), entrar("carla")
    r = criar_e_enviar(client, ana)
    acao(client, patricia, r["id"], "gestor/aprovar")
    acao(client, carla, r["id"], "financeiro/recusar", esperado=422)
    acao(client, carla, r["id"], "financeiro/recusar", json={"observacao": "Comprovante ilegível"})
    assert client.get(f"/reembolsos/{r['id']}", headers=ana).json()["situacao"] == "recusada"


# --------------------------------------------------------------------------- RN12
def test_rn12_historico_identifica_responsavel_momento_e_resultado(client, entrar, demo):
    ana, patricia = entrar("ana"), entrar("patricia")
    r = criar_e_enviar(client, ana)
    acao(client, patricia, r["id"], "gestor/aprovar")
    h = client.get(f"/reembolsos/{r['id']}/historico", headers=ana).json()
    assert h[1]["responsavel_id"] == demo["usuarios"]["patricia"]
    assert h[1]["responsavel_nome"] == "Patrícia Alves"
    assert h[1]["decisao"] == "aprovada" and h[1]["data_hora"]


# --------------------------------------------------------------------------- RN13
def test_rn13_credenciais_nunca_aparecem_nas_respostas(client, engine, entrar, demo):
    ana = entrar("ana")
    cadastro = client.post(
        "/auth/cadastro",
        json={"nome": "Novo Usuário", "email": "novo@nexuscorp.com", "senha": "Segredo123!",
              "departamento_id": demo["departamentos"]["Comercial"]},
    )
    assert cadastro.status_code == 201
    assert set(cadastro.json()) == {"id", "nome", "email", "perfil", "departamento_id"}
    assert set(client.get("/usuarios/me", headers=ana).json()) == {"id", "nome", "email", "perfil", "departamento_id"}

    # Erro de validação no login não devolve a senha recebida.
    invalido = client.post("/auth/login", json={"senha": "Segredo123!"})
    assert invalido.status_code == 422
    assert "Segredo123!" not in invalido.text

    with Session(engine) as s:  # no banco, só o hash
        novo = s.exec(select(Usuario).where(Usuario.email == "novo@nexuscorp.com")).first()
        assert novo.senha_hash.startswith("scrypt$")
        assert "Segredo123!" not in novo.senha_hash


def test_rn13_cadastro_valida_senha_e_dados(client, demo):
    base = {"nome": "Teste Um", "email": "teste@nexuscorp.com", "senha": "Senha@123",
            "departamento_id": demo["departamentos"]["Comercial"]}
    assert client.post("/auth/cadastro", json={**base, "senha": "curta1"}).status_code == 422
    assert client.post("/auth/cadastro", json={**base, "senha": "somenteletras"}).status_code == 422
    assert client.post("/auth/cadastro", json={**base, "email": "invalido"}).status_code == 422
    assert client.post("/auth/cadastro", json={**base, "departamento_id": 9999}).status_code == 422
    assert client.post("/auth/cadastro", json=base).status_code == 201
    assert client.post("/auth/cadastro", json=base).status_code == 409  # e-mail repetido


# --------------------------------------------------------------------------- RN14
def test_rn14_logout_invalida_o_token(client, entrar):
    ana = entrar("ana")
    assert client.get("/reembolsos", headers=ana).status_code == 200
    assert client.post("/auth/logout", headers=ana).status_code == 204
    assert client.get("/reembolsos", headers=ana).status_code == 401
    assert client.post("/reembolsos", json=dados_reembolso(), headers=ana).status_code == 401


def test_rn14_token_expirado_e_rejeitado(client, engine, demo):
    with Session(engine) as s:
        ana = s.get(Usuario, demo["usuarios"]["ana"])
        token, _ = criar_token(ana, validade=timedelta(seconds=-5))
    assert client.get("/reembolsos", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_rn14_usuario_desativado_perde_o_acesso(client, engine, demo, entrar):
    ana = entrar("ana")
    with Session(engine) as s:
        usuario = s.get(Usuario, demo["usuarios"]["ana"])
        usuario.ativo = False
        s.add(usuario)
        s.commit()
    assert client.get("/reembolsos", headers=ana).status_code == 401
    login = client.post("/auth/login", json={"email": "ana@nexuscorp.com", "senha": "Senha@123"})
    assert login.status_code == 401


def test_rn14_troca_de_senha_invalida_tokens_anteriores(client, entrar):
    ana = entrar("ana")
    troca = client.patch("/usuarios/me", json={"senha_atual": "Senha@123", "nova_senha": "NovaSenha@456"}, headers=ana)
    assert troca.status_code == 200
    assert client.get("/reembolsos", headers=ana).status_code == 401
    assert client.post("/auth/login", json={"email": "ana@nexuscorp.com", "senha": "Senha@123"}).status_code == 401
    assert client.post("/auth/login", json={"email": "ana@nexuscorp.com", "senha": "NovaSenha@456"}).status_code == 200


def test_troca_de_senha_exige_senha_atual_correta(client, entrar):
    ana = entrar("ana")
    errada = client.patch("/usuarios/me", json={"senha_atual": "Errada@123", "nova_senha": "NovaSenha@456"}, headers=ana)
    assert errada.status_code == 403
    assert client.patch("/usuarios/me", json={"nova_senha": "NovaSenha@456"}, headers=ana).status_code == 422
    assert client.get("/usuarios/me", headers=ana).status_code == 200  # token continua válido


# --------------------------------------------------------------------------- visibilidade
def test_financeiro_so_ve_o_que_foi_encaminhado_pelos_gestores(client, entrar):
    ana, patricia, carla = entrar("ana"), entrar("patricia"), entrar("carla")
    r1 = criar_e_enviar(client, ana)  # aguardando gestor
    r2 = criar_e_enviar(client, ana)  # recusada pelo gestor
    r3 = criar_e_enviar(client, ana)  # aprovada pelo gestor
    r4 = criar_e_enviar(client, ana)  # aprovada pelo gestor e recusada pelo financeiro
    criar(client, ana)  # rascunho
    acao(client, patricia, r2["id"], "gestor/recusar", json={"observacao": "Sem comprovante válido"})
    acao(client, patricia, r3["id"], "gestor/aprovar")
    acao(client, patricia, r4["id"], "gestor/aprovar")
    acao(client, carla, r4["id"], "financeiro/recusar", json={"observacao": "Valor acima do limite"})

    visiveis = {x["id"] for x in client.get("/reembolsos", headers=carla).json()}
    assert visiveis == {r3["id"], r4["id"]}
    assert client.get(f"/reembolsos/{r1['id']}", headers=carla).status_code == 404
    assert client.get(f"/reembolsos/{r2['id']}", headers=carla).status_code == 404


def test_colaborador_ve_apenas_as_proprias_solicitacoes(client, entrar):
    ana, bruno = entrar("ana"), entrar("bruno")
    a1, a2 = criar(client, ana), criar(client, ana)
    b1 = criar(client, bruno)
    assert {x["id"] for x in client.get("/reembolsos", headers=ana).json()} == {a1["id"], a2["id"]}
    assert [x["id"] for x in client.get("/reembolsos", headers=bruno).json()] == [b1["id"]]


def test_filtros_invalidos_e_paginacao(client, entrar):
    ana = entrar("ana")
    for _ in range(3):
        criar(client, ana)
    assert client.get("/reembolsos", params={"situacao": "inexistente"}, headers=ana).status_code == 422
    assert client.get("/reembolsos", params={"limit": 1000}, headers=ana).status_code == 422
    assert len(client.get("/reembolsos", params={"limit": 2}, headers=ana).json()) == 2
    assert len(client.get("/reembolsos", params={"skip": 2}, headers=ana).json()) == 1


def test_categoria_invalida_e_campos_obrigatorios(client, entrar):
    ana = entrar("ana")
    assert client.post("/reembolsos", json=dados_reembolso(categoria="viagem"), headers=ana).status_code == 422
    assert client.post("/reembolsos", json={"valor": 10}, headers=ana).status_code == 422


def test_departamentos_publicos_e_saude(client, demo):
    deps = client.get("/departamentos")
    assert deps.status_code == 200
    assert {d["nome"] for d in deps.json()} == {"Comercial", "Tecnologia", "Financeiro"}
    assert client.get("/saude").json() == {"status": "ok"}
