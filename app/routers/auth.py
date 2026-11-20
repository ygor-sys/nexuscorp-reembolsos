"""Autenticação: cadastro, login e logout."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from ..database import get_session
from ..deps import SessaoAutenticada, sessao_atual
from ..enums import Perfil
from ..models import Departamento, TokenRevogado, Usuario
from ..schemas import CadastroIn, LoginIn, TokenOut, UsuarioOut, usuario_saida
from ..security import criar_token, hash_falso, hash_senha, verificar_senha
from ..utils import agora

router = APIRouter(prefix="/auth", tags=["Autenticação"])
Sessao = Annotated[Session, Depends(get_session)]


@router.post(
    "/cadastro",
    response_model=UsuarioOut,
    status_code=201,
    summary="Autocadastro de colaborador",
    responses={409: {"description": "E-mail já cadastrado"}, 422: {"description": "Dados inválidos"}},
)
def cadastro(dados: CadastroIn, session: Sessao):
    """Cria SEMPRE um usuário com perfil `colaborador`. Gestores e financeiro são provisionados
    fora da API (`python -m app.seed criar-usuario`), o que impede a elevação de permissões (RN15)."""
    if session.get(Departamento, dados.departamento_id) is None:
        raise HTTPException(status_code=422, detail="Departamento informado não existe.")
    if session.exec(select(Usuario).where(Usuario.email == dados.email)).first() is not None:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado.")
    usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        perfil=Perfil.COLABORADOR,
        departamento_id=dados.departamento_id,
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario_saida(usuario)


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Autentica e devolve um token JWT",
    responses={401: {"description": "Credenciais inválidas"}},
)
def login(dados: LoginIn, session: Sessao):
    usuario = session.exec(select(Usuario).where(Usuario.email == dados.email)).first()
    # Verifica sempre um hash (real ou descartável): tempo e resposta iguais para e-mail
    # inexistente e para senha errada (Cenário 03).
    senha_ok = verificar_senha(dados.senha, usuario.senha_hash if usuario else hash_falso())
    if usuario is None or not usuario.ativo or not senha_ok:
        raise HTTPException(
            status_code=401, detail="Credenciais inválidas.", headers={"WWW-Authenticate": "Bearer"}
        )
    token, expira_em = criar_token(usuario)
    return TokenOut(access_token=token, expires_in=expira_em)


@router.post(
    "/logout",
    status_code=204,
    summary="Encerra o token atual (RN14)",
    responses={401: {"description": "Não autenticado"}},
)
def logout(sessao: Annotated[SessaoAutenticada, Depends(sessao_atual)], session: Sessao):
    expira_em = datetime.fromtimestamp(sessao.payload["exp"], timezone.utc)
    session.add(TokenRevogado(jti=sessao.payload["jti"], expira_em=expira_em))
    # Limpeza: tokens revogados que já expiraram não precisam mais ficar na lista.
    for velho in session.exec(select(TokenRevogado).where(TokenRevogado.expira_em < agora())).all():
        session.delete(velho)
    session.commit()
    return Response(status_code=204)
