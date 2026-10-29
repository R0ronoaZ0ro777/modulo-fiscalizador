"""Implementaciones en memoria de los repositorios: permiten probar la lógica
de negocio y la API sin PostgreSQL/Redis (se usan solo en tests)."""
import itertools
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from ..errors import ConflictoEstado
from ..domain.models import EstadoBus, InfraccionCandidata, Telemetria


class MemDatabase:
    @asynccontextmanager
    async def tx(self):
        yield None

    @asynccontextmanager
    async def lectura(self):
        yield None

    async def dispose(self): ...


class MemUsuarios:
    def __init__(self, usuarios: list[dict]):
        self.u = {x["email"].lower(): x for x in usuarios}

    async def por_email(self, conn, email):
        return self.u.get(email.lower())


class MemInfracciones:
    def __init__(self):
        self.items: dict[str, dict] = {}

    async def crear(self, conn, c: InfraccionCandidata):
        id_ = str(uuid.uuid4())
        d = {"id": id_, "bus_id": c.bus_id, "patente": "TEST01", "ruta_id": "102", "concesionaria": "Demo",
             "tipo": c.tipo, "severidad": c.severidad, "estado": "DETECTADA", "detectada_en": c.detectada_en,
             "valor_medido": c.valor_medido, "umbral": c.umbral, "lat": c.lat, "lon": c.lon,
             "detalle": c.detalle, "creada_en": datetime.now(timezone.utc),
             "actualizada_en": datetime.now(timezone.utc)}
        self.items[id_] = d
        return dict(d)

    async def obtener(self, conn, id):
        d = self.items.get(id)
        return dict(d) if d else None

    async def listar(self, conn, *, estado, tipo, bus_id, desde, hasta, limit, offset):
        xs = [x for x in self.items.values()
              if (not estado or x["estado"] == estado) and (not tipo or x["tipo"] == tipo)
              and (not bus_id or x["bus_id"] == bus_id)]
        xs.sort(key=lambda x: x["detectada_en"], reverse=True)
        return [dict(x) for x in xs[offset:offset + limit]], len(xs)

    async def cambiar_estado(self, conn, id, desde, hasta):
        d = self.items.get(id)
        if d and d["estado"] in desde:
            d["estado"] = hasta
            return True
        return False


class MemActas:
    def __init__(self):
        self.items: list[dict] = []

    async def crear(self, conn, *, infraccion_id, fiscalizador_id, resolucion, observaciones, sancion, evidencia):
        if any(a["infraccion_id"] == infraccion_id for a in self.items):
            raise ConflictoEstado("La infracción ya tiene un acta registrada.")
        a = {"id": str(uuid.uuid4()), "infraccion_id": infraccion_id, "fiscalizador_id": fiscalizador_id,
             "resolucion": resolucion, "observaciones": observaciones, "sancion": sancion,
             "evidencia": evidencia, "creada_en": datetime.now(timezone.utc)}
        self.items.append(a)
        return a

    async def listar(self, conn, limit, offset):
        return self.items[offset:offset + limit]


class MemAuditoria:
    def __init__(self):
        self.filas: list[dict] = []
        self._ids = itertools.count(1)

    async def bloquear(self, conn): ...

    async def ultimo_hash(self, conn):
        return self.filas[-1]["hash"] if self.filas else None

    async def insertar(self, conn, e):
        f = {**e, "id": next(self._ids), "payload": __import__("json").loads(e["payload_canonico"])}
        self.filas.append(f)
        return f

    async def listar(self, conn, limit, offset, accion):
        xs = [f for f in reversed(self.filas) if not accion or f["accion"] == accion]
        return xs[offset:offset + limit], len(xs)

    async def recorrer(self, conn, despues_de_id, limite):
        return [f for f in self.filas if f["id"] > despues_de_id][:limite]


class MemTelemetria:
    def __init__(self):
        self.filas: list[Telemetria] = []

    async def insertar_lote(self, conn, lote):
        self.filas.extend(lote)

    async def muestras_alrededor(self, conn, bus_id, ts, minutos, limite):
        return [{"ts": t.ts.isoformat(), "sequence_number": t.sequence_number, "lat": t.lat, "lon": t.lon,
                 "speed_kmh": t.speed_kmh, "heading": t.heading} for t in self.filas if t.bus_id == bus_id][:limite]


class MemUmbrales:
    def __init__(self, datos: dict[str, float]):
        self.d = {k: {"clave": k, "valor": v, "unidad": "", "descripcion": k, "version": 1,
                      "actualizado_en": datetime.now(timezone.utc)} for k, v in datos.items()}

    async def listar(self, conn):
        return list(self.d.values())

    async def actualizar(self, conn, clave, valor, version, actor_id):
        u = self.d.get(clave)
        if not u or u["version"] != version:
            return None
        u.update(valor=valor, version=version + 1)
        return dict(u)


class MemCatalogo:
    def __init__(self, rutas: dict, bus_ruta: dict):
        self._r, self._b = rutas, bus_ruta

    async def rutas(self, conn): return self._r
    async def bus_ruta(self, conn): return self._b


class MemReportes:
    async def cumplimiento(self, conn, desde, hasta, vmax): return []
    async def serie_horaria(self, conn, concesionaria_id, desde, hasta): return []


class MemFlota:
    def __init__(self, offline_after_s: int = 45):
        self.estado: dict[str, Telemetria] = {}
        self.offline_after_s = offline_after_s

    async def actualizar(self, t):
        prev = self.estado.get(t.bus_id)
        if prev and prev.ts >= t.ts:
            return False
        self.estado[t.bus_id] = t
        return True

    async def snapshot(self, ahora=None):
        ahora = ahora or datetime.now(timezone.utc)
        out = []
        for t in self.estado.values():
            edad = (ahora - t.ts).total_seconds()
            out.append(EstadoBus(t.bus_id, t.lat, t.lon, t.speed_kmh, t.heading, t.ts, max(edad, 0),
                                 "SIN_SENAL" if edad > self.offline_after_s else "EN_RUTA"))
        return out


class MemCooldown:
    def __init__(self):
        self.vistos: set[str] = set()

    async def adquirir(self, clave, segundos):
        if clave in self.vistos:
            return False
        self.vistos.add(clave)
        return True
