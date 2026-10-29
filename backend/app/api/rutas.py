"""Endpoints REST del módulo de fiscalización (prefijo /api)."""
import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from ..container import Container
from ..deps import TODOS, actor_actual, contenedor, requiere
from ..domain.models import Actor
from ..errors import ReglaNegocio
from ..services.difusion import resumen_flota
from .schemas import LoginIn, MfaIn, RefreshIn, ResolverIn, UmbralIn

router = APIRouter(prefix="/api")
Estado = Literal["DETECTADA", "EN_REVISION", "CURSADA", "DESCARTADA"]
Tipo = Literal["EXCESO_VELOCIDAD", "DESVIO_RUTA", "PERDIDA_SENAL"]


# ── Autenticación ────────────────────────────────────────────────────────────
@router.post("/auth/login")
async def login(datos: LoginIn, c: Container = Depends(contenedor)):
    return await c.auth.login(datos.email, datos.password)


@router.post("/auth/mfa")
async def mfa(datos: MfaIn, c: Container = Depends(contenedor)):
    return await c.auth.verificar_mfa(datos.mfa_token, datos.codigo)


@router.post("/auth/refresh")
async def refrescar(datos: RefreshIn, c: Container = Depends(contenedor)):
    return await c.auth.refrescar(datos.refresh_token)


@router.get("/auth/yo")
async def yo(actor: Actor = Depends(actor_actual)):
    return {"id": actor.id, "email": actor.email, "rol": actor.rol}


# ── Flota en vivo (Redis) ────────────────────────────────────────────────────
@router.get("/flota")
async def flota(_: Actor = Depends(requiere(*TODOS)), c: Container = Depends(contenedor)):
    return resumen_flota(await c.repos.flota.snapshot())


# ── Infracciones ─────────────────────────────────────────────────────────────
@router.get("/infracciones")
async def listar_infracciones(
        estado: Estado | None = None, tipo: Tipo | None = None, bus_id: str | None = Query(None, max_length=20),
        desde: datetime | None = None, hasta: datetime | None = None,
        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
        _: Actor = Depends(requiere(*TODOS)), c: Container = Depends(contenedor)):
    items, total = await c.infracciones.listar(estado=estado, tipo=tipo, bus_id=bus_id, desde=desde,
                                               hasta=hasta, limit=limit, offset=offset)
    return {"items": items, "total": total}


@router.get("/infracciones/{id}")
async def obtener_infraccion(id: UUID, _: Actor = Depends(requiere(*TODOS)), c: Container = Depends(contenedor)):
    return await c.infracciones.obtener(str(id))


@router.post("/infracciones/{id}/revision")
async def tomar_en_revision(id: UUID, actor: Actor = Depends(requiere("OPERADOR", "FISCALIZADOR")),
                            c: Container = Depends(contenedor)):
    return await c.infracciones.marcar_en_revision(str(id), actor)


@router.post("/infracciones/{id}/resolver")
async def resolver(id: UUID, datos: ResolverIn, actor: Actor = Depends(requiere("FISCALIZADOR")),
                   c: Container = Depends(contenedor)):
    sancion = datos.sancion.model_dump() if datos.sancion else None
    return await c.infracciones.resolver(str(id), actor, datos.resolucion, datos.observaciones, sancion)


@router.get("/actas")
async def actas(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                _: Actor = Depends(requiere("FISCALIZADOR", "ADMIN")), c: Container = Depends(contenedor)):
    async with c.db.tx() as conn:
        return {"items": await c.repos.actas.listar(conn, limit, offset)}


# ── Auditoría (lectura desde la réplica) ─────────────────────────────────────
@router.get("/auditoria")
async def auditoria(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                    accion: str | None = Query(None, max_length=40),
                    _: Actor = Depends(requiere("FISCALIZADOR", "ADMIN")), c: Container = Depends(contenedor)):
    async with c.db.lectura() as conn:
        items, total = await c.repos.auditoria.listar(conn, limit, offset, accion)
    return {"items": items, "total": total}


@router.get("/auditoria/verificar")
async def verificar_auditoria(_: Actor = Depends(requiere("FISCALIZADOR", "ADMIN")),
                              c: Container = Depends(contenedor)):
    async with c.db.lectura() as conn:
        return await c.auditoria.verificar(conn)


# ── Umbrales ─────────────────────────────────────────────────────────────────
@router.get("/umbrales")
async def umbrales(_: Actor = Depends(requiere(*TODOS)), c: Container = Depends(contenedor)):
    return {"items": await c.umbrales.listar()}


@router.put("/umbrales/{clave}")
async def actualizar_umbral(clave: str, datos: UmbralIn, actor: Actor = Depends(requiere("ADMIN")),
                            c: Container = Depends(contenedor)):
    return await c.umbrales.actualizar(clave, datos.valor, datos.version, actor)


# ── Reportes (lectura desde la réplica) ──────────────────────────────────────
def _rango(desde: datetime | None, hasta: datetime | None) -> tuple[datetime, datetime]:
    hasta = hasta or datetime.now(timezone.utc)
    desde = desde or hasta - timedelta(hours=24)
    desde, hasta = (x if x.tzinfo else x.replace(tzinfo=timezone.utc) for x in (desde, hasta))
    if desde >= hasta:
        raise ReglaNegocio("La fecha de inicio debe ser anterior a la de término.")
    if hasta - desde > timedelta(days=31):
        raise ReglaNegocio("El rango máximo de un reporte es de 31 días.")
    return desde, hasta


async def _cumplimiento(c: Container, desde, hasta) -> dict:
    vmax = (await c.umbral_provider.get())["velocidad_max_kmh"]
    async with c.db.lectura() as conn:
        filas = await c.repos.reportes.cumplimiento(conn, desde, hasta, vmax)
    for f in filas:
        for k in ("vel_prom", "vel_max"):
            f[k] = round(float(f[k]), 1)
        f["cumplimiento_velocidad_pct"] = round(100 * (1 - f["sobre_limite"] / f["muestras"]), 1) if f["muestras"] else None
    return {"desde": desde, "hasta": hasta, "limite_kmh": vmax, "items": filas}


@router.get("/reportes/cumplimiento")
async def cumplimiento(desde: datetime | None = None, hasta: datetime | None = None,
                       _: Actor = Depends(requiere(*TODOS)), c: Container = Depends(contenedor)):
    return await _cumplimiento(c, *_rango(desde, hasta))


@router.get("/reportes/cumplimiento.csv")
async def cumplimiento_csv(desde: datetime | None = None, hasta: datetime | None = None,
                           actor: Actor = Depends(requiere("FISCALIZADOR", "ADMIN")),
                           c: Container = Depends(contenedor)):
    d, h = _rango(desde, hasta)
    rep = await _cumplimiento(c, d, h)
    async with c.db.tx() as conn:                       # exportar datos de fiscalización queda auditado
        await c.auditoria.registrar(conn, actor=actor, accion="REPORTE_EXPORTADO", entidad="reporte",
                                    entidad_id="cumplimiento", payload={"desde": d.isoformat(), "hasta": h.isoformat()})
    cols = ["nombre", "buses", "muestras", "cumplimiento_velocidad_pct", "vel_prom", "vel_max",
            "infracciones", "exceso_velocidad", "desvio_ruta", "perdida_senal", "cursadas"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for f in rep["items"]:
        w.writerow([f[k] for k in cols])
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="cumplimiento.csv"'})


@router.get("/reportes/serie-horaria")
async def serie_horaria(concesionaria_id: int = Query(ge=1), desde: datetime | None = None,
                        hasta: datetime | None = None, _: Actor = Depends(requiere(*TODOS)),
                        c: Container = Depends(contenedor)):
    d, h = _rango(desde, hasta)
    async with c.db.lectura() as conn:
        filas = await c.repos.reportes.serie_horaria(conn, concesionaria_id, d, h)
    return {"items": [{**f, "vel_prom": round(float(f["vel_prom"]), 1), "vel_max": round(float(f["vel_max"]), 1)}
                      for f in filas]}
