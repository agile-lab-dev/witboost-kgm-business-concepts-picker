"""
Dependency injection wiring.

All service instances are created here and injected into routers via
FastAPI's ``Depends`` mechanism.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from src.services.external_service import ExternalService
from src.services.kgm_service import KgmService
from src.settings import AppSettings, load_settings


@lru_cache
def get_settings() -> AppSettings:
    """Singleton — configuration is loaded once and cached."""
    return load_settings()


def get_external_service(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> ExternalService:
    """Factory that returns the KGM service implementation."""
    return KgmService(settings)


# Handy type alias for route signatures
ExternalServiceDep = Annotated[ExternalService, Depends(get_external_service)]
