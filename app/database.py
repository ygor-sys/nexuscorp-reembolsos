"""Conexão com o banco relacional e sessão por requisição."""
import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_args)


@event.listens_for(Engine, "connect")
def _ativar_chaves_estrangeiras(dbapi_conexao, _registro):
    """O SQLite ignora FOREIGN KEY por padrão; aqui os vínculos passam a ser impostos."""
    if isinstance(dbapi_conexao, sqlite3.Connection):
        cursor = dbapi_conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def criar_tabelas() -> None:
    from . import models  # noqa: F401  (registra as tabelas no metadata)

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
