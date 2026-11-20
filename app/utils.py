"""Funções utilitárias de data e hora."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import settings


def agora() -> datetime:
    """Momento atual em UTC, com fuso (exigido pelas versões novas do SQLModel)."""
    return datetime.now(timezone.utc)


def hoje() -> date:
    """Data de hoje no fuso da empresa (usada na regra RN06)."""
    try:
        fuso = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        fuso = timezone.utc
    return datetime.now(fuso).date()
