"""Punto de entrada del monolito modular (back-office de fiscalización)."""
import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import rutas, ws
from .config import Settings, get_settings
from .container import Container, ensamblar, repos_reales
from .db import Database
from .errors import ErrorDominio
from .seed import sembrar
from .services.difusion import ticker_flota
from .services.motor import consumir_kafka, vigilante_periodico

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("fiscalizacion")


async def _con_reintentos(fn, intentos: int = 30, espera: float = 2.0):
    for i in range(1, intentos + 1):
        try:
            return await fn()
        except Exception as e:
            log.warning("Dependencia no disponible (%s). Intento %d/%d", e.__class__.__name__, i, intentos)
            await asyncio.sleep(espera)
    raise RuntimeError("No fue posible conectar con las dependencias")


def create_app(container: Container | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tareas: list[asyncio.Task] = []
        c = container
        if c is None:                                           # arranque real (no tests)
            db = Database(settings.database_url, settings.replica_url)
            redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            c = ensamblar(settings, db, redis, repos_reales(redis, settings))
            if settings.seed_demo:
                await _con_reintentos(lambda: sembrar(db, settings.sim_buses))
        app.state.c = c
        if container is None:
            tareas = [asyncio.create_task(ticker_flota(c.repos.flota, c.bus, c.hub))]
            if settings.motor_activo:                       # consumidor Kafka + vigilante de pérdida de señal
                tareas += [asyncio.create_task(consumir_kafka(settings, c.motor)),
                           asyncio.create_task(vigilante_periodico(c.motor))]
        yield
        for t in tareas:
            t.cancel()
        await asyncio.gather(*tareas, return_exceptions=True)
        if container is None:
            await c.db.dispose()
            await c.redis.aclose()

    app = FastAPI(title="Fiscalización — Centro de Control", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(ErrorDominio)
    async def _dominio(_: Request, e: ErrorDominio):
        return JSONResponse(status_code=e.status, content={"codigo": e.codigo, "mensaje": e.mensaje, **e.extra})

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, e: RequestValidationError):
        campos = [{"campo": ".".join(str(x) for x in err["loc"][1:]), "mensaje": err["msg"]} for err in e.errors()]
        return JSONResponse(status_code=422, content={"codigo": "VALIDACION", "mensaje": "Datos inválidos.", "campos": campos})

    @app.exception_handler(Exception)
    async def _inesperado(_: Request, e: Exception):
        log.exception("Error no controlado")
        return JSONResponse(status_code=500, content={"codigo": "ERROR_INTERNO", "mensaje": "Error interno. Intenta nuevamente."})

    @app.get("/health")
    async def health():
        return {"estado": "ok"}

    app.include_router(rutas.router)
    app.include_router(ws.router)
    return app


app = create_app()
