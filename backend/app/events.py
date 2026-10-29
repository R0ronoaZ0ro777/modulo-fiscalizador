"""Bus de eventos en proceso — patrón OBSERVER.

Los productores (servicios de dominio) publican hechos sin conocer a quién
le interesan; los suscriptores (hub de WebSocket, caché de umbrales, ...) se
registran por tópico. Agregar un nuevo consumidor no modifica al productor.
"""
import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)
Handler = Callable[[str, Any], Awaitable[None] | None]


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topico: str, handler: Handler) -> Callable[[], None]:
        self._subs[topico].append(handler)
        return lambda: self._subs[topico].remove(handler)

    async def publish(self, topico: str, payload: Any) -> None:
        for handler in list(self._subs.get(topico, [])):
            try:
                r = handler(topico, payload)
                if asyncio.iscoroutine(r):
                    await r
            except Exception:  # un observador defectuoso no rompe al productor
                log.exception("Observador falló en tópico %s", topico)


# Tópicos del dominio
INFRACCION_CREADA = "infraccion.creada"
INFRACCION_ACTUALIZADA = "infraccion.actualizada"
UMBRAL_ACTUALIZADO = "umbral.actualizado"
FLOTA_SNAPSHOT = "flota.snapshot"
