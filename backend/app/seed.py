"""Siembra idempotente del catálogo, umbrales y usuarios de demostración."""
import json
import logging

from sqlalchemy import text

from .domain.catalogo import CONCESIONARIAS, RUTAS, UMBRALES, USUARIOS_DEMO, generar_buses
from .security import hash_password

log = logging.getLogger(__name__)


async def sembrar(db, n_buses: int, con_usuarios_demo: bool = True) -> None:
    async with db.tx() as conn:
        for id_, nombre in CONCESIONARIAS:
            await conn.execute(text("INSERT INTO concesionarias (id, nombre) VALUES (:i, :n) ON CONFLICT DO NOTHING"),
                               {"i": id_, "n": nombre})
        for id_, r in RUTAS.items():
            await conn.execute(text(
                "INSERT INTO rutas (id, nombre, concesionaria_id, geometria) VALUES (:i, :n, :c, CAST(:g AS jsonb)) "
                "ON CONFLICT (id) DO UPDATE SET geometria = EXCLUDED.geometria"),
                {"i": id_, "n": r["nombre"], "c": r["concesionaria_id"], "g": json.dumps(r["geometria"])})
        for b in generar_buses(n_buses):
            await conn.execute(text(
                "INSERT INTO buses (id, patente, ruta_id, concesionaria_id) VALUES (:id, :p, :r, :c) ON CONFLICT DO NOTHING"),
                {"id": b["id"], "p": b["patente"], "r": b["ruta_id"], "c": b["concesionaria_id"]})
        for clave, valor, unidad, desc in UMBRALES:
            await conn.execute(text(
                "INSERT INTO umbrales (clave, valor, unidad, descripcion) VALUES (:c, :v, :u, :d) ON CONFLICT DO NOTHING"),
                {"c": clave, "v": valor, "u": unidad, "d": desc})
        if con_usuarios_demo:
            for u in USUARIOS_DEMO:
                existe = (await conn.execute(text("SELECT 1 FROM usuarios WHERE email = :e"), {"e": u["email"]})).first()
                if not existe:
                    await conn.execute(text(
                        "INSERT INTO usuarios (email, nombre, password_hash, rol, mfa_enabled, totp_secret) "
                        "VALUES (:e, :n, :h, :r, :m, :t)"),
                        {"e": u["email"], "n": u["nombre"], "h": hash_password(u["password"]),
                         "r": u["rol"], "m": u["mfa_enabled"], "t": u["totp_secret"]})
    log.info("Catálogo sembrado (%d buses)", n_buses)
