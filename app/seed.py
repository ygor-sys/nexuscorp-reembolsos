"""Provisionamento de dados fora da API HTTP.

Gestores e financeiro só podem ser criados aqui (acesso ao servidor), nunca por rotas
públicas: é isso que garante a RN15.

    python -m app.seed demo
    python -m app.seed criar-usuario --nome "Maria" --email maria@empresa.com \
        --perfil gestor --departamento Comercial
"""
import argparse
from getpass import getpass
from typing import Optional

from sqlmodel import Session, select

from .database import criar_tabelas, engine
from .enums import Perfil
from .models import Departamento, Usuario
from .security import hash_senha

SENHA_DEMO = "Senha@123"
DEPARTAMENTOS_DEMO = ["Comercial", "Tecnologia", "Financeiro"]
# (chave -> e-mail chave@nexuscorp.com, nome, perfil, departamento)
USUARIOS_DEMO = [
    ("ana", "Ana Souza", Perfil.COLABORADOR, "Comercial"),
    ("bruno", "Bruno Lima", Perfil.COLABORADOR, "Tecnologia"),
    ("patricia", "Patrícia Alves", Perfil.GESTOR, "Comercial"),
    ("tiago", "Tiago Rocha", Perfil.GESTOR, "Tecnologia"),
    ("gabriel", "Gabriel Costa", Perfil.GESTOR, "Financeiro"),
    ("carla", "Carla Mendes", Perfil.FINANCEIRO, "Financeiro"),
    ("fabio", "Fábio Nunes", Perfil.FINANCEIRO, "Financeiro"),
]


def garantir_departamento(session: Session, nome: str) -> Departamento:
    dep = session.exec(select(Departamento).where(Departamento.nome == nome)).first()
    if dep is None:
        dep = Departamento(nome=nome)
        session.add(dep)
        session.commit()
        session.refresh(dep)
    return dep


def criar_usuario(
    session: Session,
    *,
    nome: str,
    email: str,
    perfil: Perfil,
    departamento_id: int,
    senha: Optional[str] = None,
    senha_hash: Optional[str] = None,
) -> Usuario:
    if senha_hash is None:
        if not senha:
            raise ValueError("Informe a senha.")
        senha_hash = hash_senha(senha)
    usuario = Usuario(
        nome=nome,
        email=email.strip().lower(),
        senha_hash=senha_hash,
        perfil=perfil,
        departamento_id=departamento_id,
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


def popular_demo(session: Session, senha_hash: Optional[str] = None) -> dict:
    """Cria departamentos e usuários de demonstração (idempotente). Retorna os ids."""
    senha_hash = senha_hash or hash_senha(SENHA_DEMO)
    departamentos = {nome: garantir_departamento(session, nome).id for nome in DEPARTAMENTOS_DEMO}
    usuarios = {}
    for chave, nome, perfil, departamento in USUARIOS_DEMO:
        email = f"{chave}@nexuscorp.com"
        existente = session.exec(select(Usuario).where(Usuario.email == email)).first()
        if existente is None:
            existente = criar_usuario(
                session,
                nome=nome,
                email=email,
                perfil=perfil,
                departamento_id=departamentos[departamento],
                senha_hash=senha_hash,
            )
        usuarios[chave] = existente.id
    return {"departamentos": departamentos, "usuarios": usuarios}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Provisionamento de dados da plataforma de reembolsos.")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("demo", help=f"cria departamentos e usuários de demonstração (senha: {SENHA_DEMO})")
    cu = sub.add_parser("criar-usuario", help="cria um usuário com qualquer perfil")
    cu.add_argument("--nome", required=True)
    cu.add_argument("--email", required=True)
    cu.add_argument("--perfil", required=True, choices=[p.value for p in Perfil])
    cu.add_argument("--departamento", required=True, help="nome do departamento (criado se não existir)")
    args = parser.parse_args(argv)

    criar_tabelas()
    with Session(engine) as session:
        if args.comando == "demo":
            popular_demo(session)
            print("Dados de demonstração criados.")
            print(f"Usuários: {', '.join(f'{c}@nexuscorp.com' for c, *_ in USUARIOS_DEMO)}")
            print(f"Senha de todos: {SENHA_DEMO}  (use apenas em ambiente de demonstração)")
        else:
            senha = getpass("Senha do novo usuário: ")
            dep = garantir_departamento(session, args.departamento)
            usuario = criar_usuario(
                session,
                nome=args.nome,
                email=args.email,
                perfil=Perfil(args.perfil),
                departamento_id=dep.id,
                senha=senha,
            )
            print(f"Usuário criado: id={usuario.id} perfil={usuario.perfil.value}")


if __name__ == "__main__":
    main()
