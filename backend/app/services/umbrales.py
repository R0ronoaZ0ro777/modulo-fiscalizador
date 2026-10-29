"""Umbrales de fiscalización: dato maestro crítico con versionado optimista."""
import time

from ..domain.catalogo import RANGOS_UMBRAL
from ..domain.models import Actor
from ..errors import ConflictoVersion, NoEncontrado, ReglaNegocio
from ..events import UMBRAL_ACTUALIZADO, EventBus


class UmbralService:
    def __init__(self, db, repo, auditoria, bus: EventBus) -> None:
        self.db, self.repo, self.auditoria, self.bus = db, repo, auditoria, bus

    async def listar(self) -> list[dict]:
        async with self.db.tx() as conn:
            return await self.repo.listar(conn)

    async def actualizar(self, clave: str, valor: float, version: int, actor: Actor) -> dict:
        rango = RANGOS_UMBRAL.get(clave)
        if rango is None:
            raise NoEncontrado(f"El umbral '{clave}' no existe.")
        if not (rango[0] <= valor <= rango[1]):
            raise ReglaNegocio(f"'{clave}' debe estar entre {rango[0]} y {rango[1]}.")
        async with self.db.tx() as conn:
            anterior = next((u for u in await self.repo.listar(conn) if u["clave"] == clave), None)
            nuevo = await self.repo.actualizar(conn, clave, valor, version, actor.id)
            if nuevo is None:
                raise ConflictoVersion(
                    "Otro usuario modificó este umbral antes que tú. Recarga y vuelve a intentar.",
                    version_actual=anterior["version"] if anterior else None)
            await self.auditoria.registrar(conn, actor=actor, accion="UMBRAL_MODIFICADO", entidad="umbral",
                                           entidad_id=clave,
                                           payload={"anterior": anterior["valor"] if anterior else None,
                                                    "nuevo": valor, "version": nuevo["version"]})
        await self.bus.publish(UMBRAL_ACTUALIZADO, {"clave": clave})
        return nuevo


class UmbralProvider:
    """Caché con TTL de los umbrales vigentes; se invalida al recibir UMBRAL_ACTUALIZADO (Observer)."""
    def __init__(self, db, repo, bus: EventBus, ttl_s: float = 30) -> None:
        self.db, self.repo, self.ttl = db, repo, ttl_s
        self._cache: dict[str, float] | None = None
        self._t = 0.0
        bus.subscribe(UMBRAL_ACTUALIZADO, self._invalidar)

    def _invalidar(self, *_):
        self._cache = None

    async def get(self) -> dict[str, float]:
        if self._cache is None or time.monotonic() - self._t > self.ttl:
            async with self.db.tx() as conn:
                self._cache = {u["clave"]: float(u["valor"]) for u in await self.repo.listar(conn)}
            self._t = time.monotonic()
        return self._cache
