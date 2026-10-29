"""Autenticación: contraseña (Argon2id) → MFA TOTP (si corresponde) → JWT de vida corta."""
from datetime import timedelta

from ..config import Settings
from ..domain.models import Actor
from ..errors import CredencialesInvalidas, TokenInvalido
from ..security import (LoginGuard, crear_token, decodificar_token, hash_password,
                        verificar_totp, verify_password)

# Hash señuelo: iguala el tiempo de respuesta cuando el correo no existe (evita enumerar usuarios).
_DUMMY = hash_password("no-importa")


class AuthService:
    def __init__(self, settings: Settings, db, usuarios, guard: LoginGuard, auditoria) -> None:
        self.s, self.db, self.usuarios, self.guard, self.auditoria = settings, db, usuarios, guard, auditoria

    def _token(self, u: dict, scope: str, ttl: timedelta) -> tuple[str, int]:
        return crear_token(secret=self.s.jwt_secret, alg=self.s.jwt_alg, sub=u["id"], rol=u["rol"],
                           email=u["email"], scope=scope, ttl=ttl)

    def _sesion(self, u: dict) -> dict:
        access, exp = self._token(u, "access", timedelta(minutes=self.s.access_ttl_min))
        refresh, _ = self._token(u, "refresh", timedelta(hours=self.s.refresh_ttl_h))
        return {"mfa_required": False, "access_token": access, "refresh_token": refresh,
                "token_type": "bearer", "expires_in": exp,
                "usuario": {"nombre": u["nombre"], "email": u["email"], "rol": u["rol"]}}

    async def _usuario(self, email: str) -> dict | None:
        async with self.db.tx() as conn:
            return await self.usuarios.por_email(conn, email)

    async def _auditar(self, accion: str, u: dict | None, payload: dict) -> None:
        actor = Actor(u["id"], u["email"], u["rol"]) if u else None
        async with self.db.tx() as conn:
            await self.auditoria.registrar(conn, actor=actor, accion=accion, entidad="usuario",
                                           entidad_id=u["id"] if u else None, payload=payload)

    async def login(self, email: str, password: str) -> dict:
        await self.guard.verificar(email)
        u = await self._usuario(email)
        ok = verify_password(password, u["password_hash"] if u else _DUMMY) and bool(u and u["activo"])
        if not ok:
            await self.guard.fallo(email)
            await self._auditar("LOGIN_FALLIDO", u, {"email": email.lower()})
            raise CredencialesInvalidas("Correo o contraseña incorrectos.")
        if u["mfa_enabled"]:
            tok, _ = self._token(u, "mfa", timedelta(minutes=self.s.mfa_ttl_min))
            return {"mfa_required": True, "mfa_token": tok}
        await self.guard.exito(email)
        await self._auditar("LOGIN_OK", u, {"mfa": False})
        return self._sesion(u)

    async def verificar_mfa(self, mfa_token: str, codigo: str) -> dict:
        claims = decodificar_token(mfa_token, secret=self.s.jwt_secret, alg=self.s.jwt_alg, scope="mfa")
        await self.guard.verificar(claims["email"])
        u = await self._usuario(claims["email"])
        if not u or not u["activo"] or not u.get("totp_secret") or not verificar_totp(u["totp_secret"], codigo):
            await self.guard.fallo(claims["email"])
            await self._auditar("MFA_FALLIDO", u, {"email": claims["email"]})
            raise CredencialesInvalidas("Código de verificación incorrecto.")
        await self.guard.exito(claims["email"])
        await self._auditar("LOGIN_OK", u, {"mfa": True})
        return self._sesion(u)

    async def refrescar(self, refresh_token: str) -> dict:
        claims = decodificar_token(refresh_token, secret=self.s.jwt_secret, alg=self.s.jwt_alg, scope="refresh")
        u = await self._usuario(claims["email"])
        if not u or not u["activo"]:
            raise TokenInvalido("La cuenta ya no está activa.")
        return self._sesion(u)
