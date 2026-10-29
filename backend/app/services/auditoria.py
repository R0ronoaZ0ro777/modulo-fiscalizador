"""Auditoría forense: log append-only con HASH ENCADENADO.

Cada entrada incluye el hash de la anterior; alterar o borrar una fila rompe la
cadena desde ese punto y `verificar()` lo detecta. Además la base de datos
rechaza UPDATE/DELETE/TRUNCATE mediante triggers (ver db/init/20_schema.sql).
"""
import hashlib
import json
from datetime import datetime, timezone

from ..domain.models import Actor

GENESIS = "0" * 64


def canonico(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def calcular_hash(prev_hash: str, ts: datetime, actor_id: str | None, accion: str,
                  entidad: str | None, entidad_id: str | None, payload_canonico: str) -> str:
    base = "|".join([prev_hash, ts.astimezone(timezone.utc).isoformat(timespec="microseconds"),
                     actor_id or "", accion, entidad or "", entidad_id or "", payload_canonico])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class AuditoriaService:
    def __init__(self, repo) -> None:
        self.repo = repo

    async def registrar(self, conn, *, actor: Actor | None, accion: str, entidad: str | None = None,
                        entidad_id: str | None = None, payload: dict | None = None) -> dict:
        """Debe invocarse dentro de la MISMA transacción que la operación auditada:
        si esta se revierte, el registro de auditoría también."""
        await self.repo.bloquear(conn)                       # serializa: la cadena no se bifurca
        prev = (await self.repo.ultimo_hash(conn)) or GENESIS
        ts = datetime.now(timezone.utc)
        canon = canonico(payload or {})
        h = calcular_hash(prev, ts, actor.id if actor else None, accion, entidad, entidad_id, canon)
        return await self.repo.insertar(conn, {
            "ts": ts, "actor_id": actor.id if actor else None, "actor_rol": actor.rol if actor else "SISTEMA",
            "accion": accion, "entidad": entidad, "entidad_id": entidad_id,
            "payload_canonico": canon, "prev_hash": prev, "hash": h})

    async def verificar(self, conn, lote: int = 1000) -> dict:
        esperado, total, ultimo_id = GENESIS, 0, 0
        while True:
            filas = await self.repo.recorrer(conn, ultimo_id, lote)
            if not filas:
                break
            for f in filas:
                total += 1
                if f["prev_hash"].strip() != esperado:
                    return {"valida": False, "total": total, "primer_invalido": f["id"],
                            "motivo": "Enlace roto: falta o se modificó una entrada anterior."}
                h = calcular_hash(f["prev_hash"].strip(), f["ts"], f["actor_id"], f["accion"],
                                  f["entidad"], f["entidad_id"], f["payload_canonico"])
                if h != f["hash"].strip():
                    return {"valida": False, "total": total, "primer_invalido": f["id"],
                            "motivo": "El contenido de la entrada no coincide con su hash."}
                esperado = f["hash"].strip()
            ultimo_id = filas[-1]["id"]
        # `ultimo_hash` puede anclarse externamente para detectar truncamiento de la cola.
        return {"valida": True, "total": total, "primer_invalido": None, "motivo": None,
                "ultimo_hash": esperado if total else None}
