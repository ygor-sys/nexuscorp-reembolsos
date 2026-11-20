"""Dados do próprio usuário."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..deps import UsuarioLogado
from ..models import Usuario
from ..schemas import UsuarioAtualizar, UsuarioOut, usuario_saida
from ..security import hash_senha, verificar_senha

router = APIRouter(prefix="/usuarios", tags=["Usuários"])
Sessao = Annotated[Session, Depends(get_session)]


@router.get("/me", response_model=UsuarioOut, summary="Dados do usuário autenticado")
def meu_cadastro(usuario: UsuarioLogado):
    return usuario_saida(usuario)


@router.patch(
    "/me",
    response_model=UsuarioOut,
    summary="Atualiza nome, e-mail ou senha do próprio usuário",
    responses={
        403: {"description": "Senha atual incorreta"},
        409: {"description": "E-mail já em uso"},
        422: {"description": "Dados inválidos ou campos não permitidos (perfil, departamento...)"},
    },
)
def atualizar_meu_cadastro(dados: UsuarioAtualizar, usuario: UsuarioLogado, session: Sessao):
    """Só aceita `nome`, `email`, `senha_atual` e `nova_senha`. Qualquer outro campo, como
    `perfil` ou `departamento_id`, é rejeitado com 422 e nada é alterado (RN15)."""
    if dados.email is not None and dados.email != usuario.email:
        existente = session.exec(select(Usuario).where(Usuario.email == dados.email)).first()
        if existente is not None:
            raise HTTPException(status_code=409, detail="E-mail já cadastrado.")
        usuario.email = dados.email
    if dados.nome is not None:
        usuario.nome = dados.nome
    if dados.nova_senha is not None:
        if not verificar_senha(dados.senha_atual, usuario.senha_hash):
            raise HTTPException(status_code=403, detail="Senha atual incorreta.")
        usuario.senha_hash = hash_senha(dados.nova_senha)
        usuario.token_version += 1  # invalida todos os tokens emitidos antes (RN14)
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario_saida(usuario)
