"""Dependencias de FastAPI: contenedor, usuario autenticado y control de acceso por rol (RBAC)."""
from fastapi import Depends, Request

from .container import Container
from .domain.models import Actor
from .errors import PermisoDenegado, TokenInvalido
from .security import decodificar_token

TODOS = ("ADMIN", "FISCALIZADOR", "OPERADOR")


def contenedor(request: Request) -> Container:
    return request.app.state.c


async def actor_actual(request: Request, c: Container = Depends(contenedor)) -> Actor:
    cab = request.headers.get("authorization", "")
    if not cab.lower().startswith("bearer "):
        raise TokenInvalido("Falta el token de acceso.")
    claims = decodificar_token(cab[7:], secret=c.settings.jwt_secret, alg=c.settings.jwt_alg, scope="access")
    return Actor(claims["sub"], claims["email"], claims["rol"])


def requiere(*roles: str):
    async def _dep(actor: Actor = Depends(actor_actual)) -> Actor:
        if actor.rol not in roles:
            raise PermisoDenegado(f"El rol {actor.rol} no tiene permiso para esta acción.")
        return actor
    return _dep
