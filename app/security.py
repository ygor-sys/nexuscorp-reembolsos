"""Hash de senhas (scrypt, biblioteca padrão) e tokens JWT."""
import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

import jwt

from .config import settings

ALGORITMO_JWT = "HS256"
_R = 8
_P = 1
_MAXMEM = 128 * 1024 * 1024


def hash_senha(senha: str) -> str:
    """Gera 'scrypt$n$r$p$salt$hash' com salt aleatório. O texto da senha não é guardado (RN13)."""
    n = settings.scrypt_n
    salt = os.urandom(16)
    derivada = hashlib.scrypt(senha.encode("utf-8"), salt=salt, n=n, r=_R, p=_P, dklen=32, maxmem=_MAXMEM)
    return "$".join(
        ["scrypt", str(n), str(_R), str(_P), base64.b64encode(salt).decode(), base64.b64encode(derivada).decode()]
    )


def verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        algoritmo, n, r, p, salt_b64, hash_b64 = armazenado.split("$")
        if algoritmo != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        esperado = base64.b64decode(hash_b64)
        calculado = hashlib.scrypt(
            senha.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(esperado), maxmem=_MAXMEM
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculado, esperado)


@lru_cache(maxsize=1)
def hash_falso() -> str:
    """Hash descartável: permite gastar o mesmo tempo de verificação quando o e-mail não existe."""
    return hash_senha(uuid.uuid4().hex)


def criar_token(usuario, validade: Optional[timedelta] = None) -> tuple[str, int]:
    """Cria o JWT. O perfil NÃO vai no token: é sempre lido do banco a cada requisição."""
    validade = validade if validade is not None else timedelta(minutes=settings.token_minutos)
    emitido_em = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario.id),
        "jti": uuid.uuid4().hex,
        "tv": usuario.token_version,
        "iat": emitido_em,
        "exp": emitido_em + validade,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITMO_JWT)
    return token, int(validade.total_seconds())


def decodificar_token(token: str) -> dict:
    """Valida assinatura e expiração. Lança jwt.PyJWTError se o token não for aceitável."""
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[ALGORITMO_JWT],
        options={"require": ["exp", "iat", "sub", "jti"]},
    )
