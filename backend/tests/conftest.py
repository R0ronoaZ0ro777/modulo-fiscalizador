import uuid
from datetime import datetime, timezone

import fakeredis.aioredis
import httpx
import pytest

from app.config import Settings
from app.container import Repos, ensamblar
from app.domain.catalogo import RUTAS, USUARIOS_DEMO
from app.domain.models import Telemetria
from app.main import create_app
from app.repositories import memoria as m
from app.repositories.redis_flota import FlotaRedis
from app.security import hash_password

UMBRALES = {"velocidad_max_kmh": 60.0, "desvio_max_m": 250.0, "senal_perdida_s": 180.0}


def tel(bus_id="BUS-001", seq=1, speed=40.0, lat=-33.4519, lon=-70.6786, ts=None, backfill=False) -> Telemetria:
    return Telemetria(event_id=uuid.uuid4(), bus_id=bus_id, sequence_number=seq,
                      ts=ts or datetime.now(timezone.utc), lat=lat, lon=lon, speed_kmh=speed, is_backfill=backfill)


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest.fixture
def usuarios():
    out = []
    for i, u in enumerate(USUARIOS_DEMO, start=1):
        out.append({"id": f"00000000-0000-0000-0000-00000000000{i}", "email": u["email"], "nombre": u["nombre"],
                    "password_hash": hash_password(u["password"]), "rol": u["rol"], "mfa_enabled": u["mfa_enabled"],
                    "totp_secret": u["totp_secret"], "activo": True})
    return out


@pytest.fixture
async def container(redis, usuarios):
    s = Settings(jwt_secret="x" * 40, login_max_intentos=5)
    repos = Repos(usuarios=m.MemUsuarios(usuarios), infracciones=m.MemInfracciones(), actas=m.MemActas(),
                  auditoria=m.MemAuditoria(), telemetria=m.MemTelemetria(), umbrales=m.MemUmbrales(UMBRALES),
                  catalogo=m.MemCatalogo({k: v["geometria"] for k, v in RUTAS.items()}, {"BUS-001": "102"}),
                  reportes=m.MemReportes(), flota=FlotaRedis(redis, 45), cooldown=m.MemCooldown())
    return ensamblar(s, m.MemDatabase(), redis, repos)


@pytest.fixture
async def client(container):
    app = create_app(container=container, settings=container.settings)
    app.state.c = container
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as cl:
        yield cl
