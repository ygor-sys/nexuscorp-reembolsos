"""Configurações lidas de variáveis de ambiente (ou de um arquivo .env na raiz do projeto)."""
import os
import secrets
import warnings
from dataclasses import dataclass
from pathlib import Path


def _carregar_dotenv() -> None:
    """Leitor mínimo de .env (CHAVE=valor). Variáveis já definidas no ambiente prevalecem."""
    caminho = Path(__file__).resolve().parent.parent / ".env"
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    token_minutos: int
    timezone: str
    scrypt_n: int


def _carregar() -> Settings:
    _carregar_dotenv()
    segredo = os.getenv("SECRET_KEY")
    if not segredo:
        # Nunca existe um segredo "padrão" no código: sem configuração, usa-se uma chave
        # aleatória e temporária (os tokens deixam de valer quando a aplicação reinicia).
        segredo = secrets.token_urlsafe(48)
        warnings.warn(
            "SECRET_KEY não definida: foi gerada uma chave temporária. "
            "Defina SECRET_KEY no ambiente ou no arquivo .env.",
            RuntimeWarning,
            stacklevel=2,
        )
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./reembolsos.db"),
        secret_key=segredo,
        token_minutos=int(os.getenv("TOKEN_MINUTOS", "30")),
        timezone=os.getenv("APP_TIMEZONE", "America/Sao_Paulo"),
        scrypt_n=int(os.getenv("SCRYPT_N", str(2**14))),
    )


settings = _carregar()
