import os

# Precisam ser definidas ANTES de importar a aplicação.
os.environ.setdefault("SECRET_KEY", "chave-somente-para-testes-0123456789-abcdefghij")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SCRYPT_N", "1024")  # custo baixo só nos testes, para ficarem rápidos

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app.database import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_senha  # noqa: E402
from app.seed import SENHA_DEMO, popular_demo  # noqa: E402


@pytest.fixture(scope="session")
def hash_padrao():
    return hash_senha(SENHA_DEMO)


@pytest.fixture()
def engine():
    """Banco SQLite em memória, novo para cada teste."""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def client(engine):
    def _sessao():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _sessao
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def demo(engine, hash_padrao):
    """Departamentos Comercial/Tecnologia/Financeiro e os usuários de demonstração."""
    with Session(engine) as session:
        return popular_demo(session, senha_hash=hash_padrao)


@pytest.fixture()
def entrar(client, demo):
    """entrar('ana') -> cabeçalho Authorization com o token do usuário ana@nexuscorp.com."""

    def _entrar(chave: str) -> dict:
        resposta = client.post("/auth/login", json={"email": f"{chave}@nexuscorp.com", "senha": SENHA_DEMO})
        assert resposta.status_code == 200, resposta.text
        return {"Authorization": f"Bearer {resposta.json()['access_token']}"}

    return _entrar
