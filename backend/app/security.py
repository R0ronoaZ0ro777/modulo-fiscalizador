"""Contraseñas (Argon2id), JWT de vida corta, TOTP (MFA) y bloqueo por fuerza bruta."""
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .errors import CuentaBloqueada, TokenInvalido

_ph = PasswordHasher()


def hash_password(plano: str) -> str:
    return _ph.hash(plano)


def verify_password(plano: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plano)
    except (VerifyMismatchError, Exception):
        return False


# ── JWT ──────────────────────────────────────────────────────────────────────
def crear_token(*, secret: str, alg: str, sub: str, rol: str, email: str,
                scope: str, ttl: timedelta) -> tuple[str, int]:
    ahora = datetime.now(timezone.utc)
    exp = ahora + ttl
    claims = {"sub": sub, "rol": rol, "email": email, "scope": scope,
              "iat": int(ahora.timestamp()), "exp": int(exp.timestamp()), "jti": uuid.uuid4().hex}
    return jwt.encode(claims, secret, algorithm=alg), int(ttl.total_seconds())


def decodificar_token(token: str, *, secret: str, alg: str, scope: str) -> dict:
    try:
        claims = jwt.decode(token, secret, algorithms=[alg])
    except jwt.ExpiredSignatureError:
        raise TokenInvalido("La sesión expiró. Inicia sesión nuevamente.")
    except jwt.PyJWTError:
        raise TokenInvalido("Token inválido.")
    if claims.get("scope") != scope:
        raise TokenInvalido("Token no válido para esta operación.")
    return claims


# ── TOTP (MFA) ───────────────────────────────────────────────────────────────
def verificar_totp(secret: str, codigo: str) -> bool:
    codigo = (codigo or "").strip().replace(" ", "")
    return codigo.isdigit() and len(codigo) == 6 and pyotp.TOTP(secret).verify(codigo, valid_window=1)


def generar_secreto_totp() -> str:
    return pyotp.random_base32()


# ── Bloqueo por intentos fallidos (Redis) ────────────────────────────────────
class LoginGuard:
    def __init__(self, redis, max_intentos: int, bloqueo_min: int) -> None:
        self.r, self.max, self.ventana = redis, max_intentos, bloqueo_min * 60

    def _k(self, email: str) -> str:
        return f"login:fallos:{email.lower()}"

    async def verificar(self, email: str) -> None:
        n = await self.r.get(self._k(email))
        if n is not None and int(n) >= self.max:
            ttl = await self.r.ttl(self._k(email))
            raise CuentaBloqueada(
                f"Demasiados intentos fallidos. Intenta nuevamente en {max(ttl, 1) // 60 + 1} min.")

    async def fallo(self, email: str) -> int:
        k = self._k(email)
        n = await self.r.incr(k)
        if n == 1:
            await self.r.expire(k, self.ventana)
        return int(n)

    async def exito(self, email: str) -> None:
        await self.r.delete(self._k(email))


def ahora_s() -> float:
    return time.time()
