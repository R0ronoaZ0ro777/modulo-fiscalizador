"""Casos de uso de fiscalización: registrar, revisar y resolver infracciones."""
from datetime import datetime, timezone

from ..domain.models import Actor, InfraccionCandidata
from ..errors import ConflictoEstado, NoEncontrado, PermisoDenegado, ReglaNegocio
from ..events import INFRACCION_ACTUALIZADA, INFRACCION_CREADA, EventBus
from ..util import json_safe

MULTA_MAX_UF = 500.0
SANCIONES = {"AMONESTACION", "MULTA"}


class InfraccionService:
    def __init__(self, db, infracciones, actas, telemetria, auditoria, bus: EventBus) -> None:
        self.db, self.infracciones, self.actas = db, infracciones, actas
        self.telemetria, self.auditoria, self.bus = telemetria, auditoria, bus

    # ── Detección automática (la invoca el motor) ────────────────────────────
    async def registrar_detectada(self, c: InfraccionCandidata) -> dict:
        async with self.db.tx() as conn:
            inf = await self.infracciones.crear(conn, c)
            await self.auditoria.registrar(conn, actor=None, accion="INFRACCION_DETECTADA",
                                           entidad="infraccion", entidad_id=inf["id"],
                                           payload={"bus_id": c.bus_id, "tipo": c.tipo,
                                                    "severidad": c.severidad, "valor": c.valor_medido,
                                                    "umbral": c.umbral})
        await self.bus.publish(INFRACCION_CREADA, json_safe(inf))     # tras el commit
        return inf

    # ── Consultas ────────────────────────────────────────────────────────────
    async def listar(self, **filtros) -> tuple[list[dict], int]:
        async with self.db.tx() as conn:
            return await self.infracciones.listar(conn, **filtros)

    async def obtener(self, id: str) -> dict:
        async with self.db.tx() as conn:
            inf = await self.infracciones.obtener(conn, id)
        if not inf:
            raise NoEncontrado("La infracción no existe.")
        return inf

    # ── Operador / fiscalizador: pasar a revisión ────────────────────────────
    async def marcar_en_revision(self, id: str, actor: Actor) -> dict:
        if actor.rol not in ("OPERADOR", "FISCALIZADOR"):
            raise PermisoDenegado("Tu rol no puede tomar infracciones en revisión.")
        async with self.db.tx() as conn:
            if not await self.infracciones.obtener(conn, id):
                raise NoEncontrado("La infracción no existe.")
            if not await self.infracciones.cambiar_estado(conn, id, ["DETECTADA"], "EN_REVISION"):
                raise ConflictoEstado("Solo se pueden tomar en revisión infracciones recién detectadas.")
            await self.auditoria.registrar(conn, actor=actor, accion="INFRACCION_EN_REVISION",
                                           entidad="infraccion", entidad_id=id)
            inf = await self.infracciones.obtener(conn, id)
        await self.bus.publish(INFRACCION_ACTUALIZADA, json_safe(inf))
        return inf

    # ── Fiscalizador: resolver → genera acta ─────────────────────────────────
    async def resolver(self, id: str, actor: Actor, resolucion: str, observaciones: str,
                       sancion: dict | None) -> dict:
        if actor.rol != "FISCALIZADOR":                       # defensa en profundidad (además del RBAC de la API)
            raise PermisoDenegado("Solo un fiscalizador puede resolver infracciones.")
        obs = (observaciones or "").strip()
        self._validar_resolucion(resolucion, obs, sancion)

        async with self.db.tx() as conn:
            inf = await self.infracciones.obtener(conn, id)
            if not inf:
                raise NoEncontrado("La infracción no existe.")
            if (resolucion == "CURSAR" and inf["severidad"] == "CRITICA"
                    and sancion["tipo"] == "AMONESTACION"):
                raise ReglaNegocio("Una infracción crítica no puede resolverse solo con amonestación.")

            nuevo = "CURSADA" if resolucion == "CURSAR" else "DESCARTADA"
            if not await self.infracciones.cambiar_estado(conn, id, ["DETECTADA", "EN_REVISION"], nuevo):
                raise ConflictoEstado(f"La infracción ya fue resuelta (estado: {inf['estado']}).")

            muestras = await self.telemetria.muestras_alrededor(conn, inf["bus_id"], inf["detectada_en"], 2, 60)
            evidencia = json_safe({"infraccion": inf, "muestras_telemetria": muestras,
                                   "generada_en": datetime.now(timezone.utc)})
            acta = await self.actas.crear(conn, infraccion_id=id, fiscalizador_id=actor.id,
                                          resolucion=resolucion, observaciones=obs,
                                          sancion=sancion if resolucion == "CURSAR" else None,
                                          evidencia=evidencia)
            await self.auditoria.registrar(
                conn, actor=actor, accion="ACTA_CURSADA" if resolucion == "CURSAR" else "ACTA_DESCARTADA",
                entidad="infraccion", entidad_id=id,
                payload={"acta_id": acta["id"], "resolucion": resolucion, "sancion": sancion,
                         "muestras_evidencia": len(muestras)})
            final = await self.infracciones.obtener(conn, id)
        await self.bus.publish(INFRACCION_ACTUALIZADA, json_safe(final))
        return {"acta": json_safe(acta), "infraccion": final}

    @staticmethod
    def _validar_resolucion(resolucion: str, obs: str, sancion: dict | None) -> None:
        if resolucion == "CURSAR":
            if len(obs) < 20:
                raise ReglaNegocio("Para cursar una infracción debes fundamentarla (mínimo 20 caracteres).")
            if not sancion or sancion.get("tipo") not in SANCIONES:
                raise ReglaNegocio("Debes indicar la sanción: amonestación o multa.")
            if sancion["tipo"] == "MULTA":
                monto = sancion.get("monto_uf")
                if monto is None or not (0 < monto <= MULTA_MAX_UF):
                    raise ReglaNegocio(f"El monto de la multa debe ser mayor que 0 y hasta {MULTA_MAX_UF:.0f} UF.")
            elif sancion.get("monto_uf"):
                raise ReglaNegocio("Una amonestación no lleva monto.")
        elif resolucion == "DESCARTAR":
            if len(obs) < 10:
                raise ReglaNegocio("Para descartar debes indicar el motivo (mínimo 10 caracteres).")
            if sancion:
                raise ReglaNegocio("Una infracción descartada no puede llevar sanción.")
        else:
            raise ReglaNegocio("Resolución desconocida.")
