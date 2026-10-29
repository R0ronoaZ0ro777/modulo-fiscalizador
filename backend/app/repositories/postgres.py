"""Implementación de los repositorios sobre PostgreSQL + TimescaleDB (SQLAlchemy Core)."""
import json
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..domain.models import InfraccionCandidata, Telemetria
from ..errors import ConflictoEstado, ConflictoVersion


def _j(v):
    """jsonb puede llegar ya decodificado (dict) o como texto según el driver."""
    return json.loads(v) if isinstance(v, (str, bytes)) else v


def _row(r) -> dict | None:
    return dict(r) if r is not None else None


class PgUsuarios:
    async def por_email(self, conn, email):
        r = (await conn.execute(text(
            "SELECT id::text AS id, email, nombre, password_hash, rol, mfa_enabled, totp_secret, activo "
            "FROM usuarios WHERE lower(email) = lower(:e)"), {"e": email})).mappings().first()
        return _row(r)


_INF_SELECT = """
SELECT i.id::text AS id, i.bus_id, b.patente, b.ruta_id, c.nombre AS concesionaria,
       i.tipo, i.severidad, i.estado, i.detectada_en, i.valor_medido, i.umbral,
       i.lat, i.lon, i.detalle, i.creada_en, i.actualizada_en
FROM infracciones i
JOIN buses b ON b.id = i.bus_id
JOIN concesionarias c ON c.id = b.concesionaria_id
"""


class PgInfracciones:
    async def crear(self, conn, c: InfraccionCandidata) -> dict:
        nuevo = (await conn.execute(text(
            "INSERT INTO infracciones (bus_id, tipo, severidad, detectada_en, valor_medido, umbral, lat, lon, detalle) "
            "VALUES (:bus, :tipo, :sev, :det, :val, :umb, :lat, :lon, CAST(:detalle AS jsonb)) RETURNING id::text"),
            {"bus": c.bus_id, "tipo": c.tipo, "sev": c.severidad, "det": c.detectada_en,
             "val": c.valor_medido, "umb": c.umbral, "lat": c.lat, "lon": c.lon,
             "detalle": json.dumps(c.detalle)})).scalar_one()
        return await self.obtener(conn, nuevo)

    async def obtener(self, conn, id):
        r = (await conn.execute(text(_INF_SELECT + " WHERE i.id = CAST(:id AS uuid)"), {"id": id})).mappings().first()
        if not r:
            return None
        d = dict(r)
        d["detalle"] = _j(d["detalle"])
        return d

    async def listar(self, conn, *, estado, tipo, bus_id, desde, hasta, limit, offset):
        where, p = ["TRUE"], {"limit": limit, "offset": offset}
        for campo, col in (("estado", "i.estado"), ("tipo", "i.tipo"), ("bus_id", "i.bus_id")):
            v = locals()[campo]
            if v:
                where.append(f"{col} = :{campo}")
                p[campo] = v
        if desde:
            where.append("i.detectada_en >= :desde"); p["desde"] = desde
        if hasta:
            where.append("i.detectada_en < :hasta"); p["hasta"] = hasta
        w = " AND ".join(where)
        total = (await conn.execute(text(f"SELECT count(*) FROM infracciones i WHERE {w}"), p)).scalar_one()
        rows = (await conn.execute(text(
            _INF_SELECT + f" WHERE {w} ORDER BY i.detectada_en DESC LIMIT :limit OFFSET :offset"), p)).mappings().all()
        items = []
        for r in rows:
            d = dict(r); d["detalle"] = _j(d["detalle"]); items.append(d)
        return items, total

    async def cambiar_estado(self, conn, id, desde, hasta) -> bool:
        """UPDATE condicional: solo cambia si el estado actual es válido (control optimista)."""
        r = await conn.execute(text(
            "UPDATE infracciones SET estado = :hasta, actualizada_en = now() "
            "WHERE id = CAST(:id AS uuid) AND estado = ANY(:desde) RETURNING id"),
            {"id": id, "desde": desde, "hasta": hasta})
        return r.first() is not None


class PgActas:
    async def crear(self, conn, *, infraccion_id, fiscalizador_id, resolucion, observaciones, sancion, evidencia):
        try:
            r = (await conn.execute(text(
                "INSERT INTO actas (infraccion_id, fiscalizador_id, resolucion, observaciones, sancion, evidencia) "
                "VALUES (CAST(:i AS uuid), CAST(:f AS uuid), :res, :obs, CAST(:san AS jsonb), CAST(:ev AS jsonb)) "
                "RETURNING id::text AS id, infraccion_id::text AS infraccion_id, resolucion, creada_en"),
                {"i": infraccion_id, "f": fiscalizador_id, "res": resolucion, "obs": observaciones,
                 "san": json.dumps(sancion) if sancion else None,
                 "ev": json.dumps(evidencia, default=str)})).mappings().one()
        except IntegrityError:
            raise ConflictoEstado("La infracción ya tiene un acta registrada.")
        return dict(r)

    async def listar(self, conn, limit, offset):
        rows = (await conn.execute(text(
            "SELECT a.id::text AS id, a.infraccion_id::text AS infraccion_id, a.resolucion, a.observaciones, "
            "a.sancion, a.creada_en, u.nombre AS fiscalizador, i.bus_id, i.tipo, i.severidad "
            "FROM actas a JOIN usuarios u ON u.id = a.fiscalizador_id "
            "JOIN infracciones i ON i.id = a.infraccion_id "
            "ORDER BY a.creada_en DESC LIMIT :l OFFSET :o"), {"l": limit, "o": offset})).mappings().all()
        out = []
        for r in rows:
            d = dict(r); d["sancion"] = _j(d["sancion"]) if d["sancion"] else None; out.append(d)
        return out


class PgAuditoria:
    LOCK_KEY = 724_001

    async def bloquear(self, conn):
        """Serializa escrituras para que la cadena de hashes no se bifurque."""
        await conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": self.LOCK_KEY})

    async def ultimo_hash(self, conn):
        return (await conn.execute(text("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1"))).scalar()

    async def insertar(self, conn, e):
        r = (await conn.execute(text(
            "INSERT INTO audit_log (ts, actor_id, actor_rol, accion, entidad, entidad_id, payload, payload_canonico, prev_hash, hash) "
            "VALUES (:ts, CAST(:actor AS uuid), :rol, :accion, :entidad, :eid, CAST(:payload AS jsonb), :canon, :prev, :hash) "
            "RETURNING id"),
            {"ts": e["ts"], "actor": e["actor_id"], "rol": e["actor_rol"], "accion": e["accion"],
             "entidad": e["entidad"], "eid": e["entidad_id"], "payload": e["payload_canonico"],
             "canon": e["payload_canonico"], "prev": e["prev_hash"], "hash": e["hash"]})).scalar_one()
        return {**e, "id": r}

    async def listar(self, conn, limit, offset, accion):
        p = {"l": limit, "o": offset}
        w = ""
        if accion:
            w, p["a"] = "WHERE accion = :a", accion
        total = (await conn.execute(text(f"SELECT count(*) FROM audit_log {w}"), p)).scalar_one()
        rows = (await conn.execute(text(
            "SELECT id, ts, actor_id::text AS actor_id, actor_rol, accion, entidad, entidad_id, payload, hash, prev_hash "
            f"FROM audit_log {w} ORDER BY id DESC LIMIT :l OFFSET :o"), p)).mappings().all()
        out = []
        for r in rows:
            d = dict(r); d["payload"] = _j(d["payload"]); out.append(d)
        return out, total

    async def recorrer(self, conn, despues_de_id, limite):
        rows = (await conn.execute(text(
            "SELECT id, ts, actor_id::text AS actor_id, accion, entidad, entidad_id, payload_canonico, prev_hash, hash "
            "FROM audit_log WHERE id > :d ORDER BY id LIMIT :l"), {"d": despues_de_id, "l": limite})).mappings().all()
        return [dict(r) for r in rows]


class PgTelemetria:
    async def insertar_lote(self, conn, lote: list[Telemetria]) -> None:
        if not lote:
            return
        await conn.execute(text(
            "INSERT INTO telemetry (ts, bus_id, sequence_number, event_id, lat, lon, speed_kmh, heading, is_backfill) "
            "VALUES (:ts, :bus, :seq, CAST(:eid AS uuid), :lat, :lon, :spd, :hdg, :bf) "
            "ON CONFLICT (bus_id, ts, sequence_number) DO NOTHING"),
            [{"ts": t.ts, "bus": t.bus_id, "seq": t.sequence_number, "eid": str(t.event_id), "lat": t.lat,
              "lon": t.lon, "spd": t.speed_kmh, "hdg": t.heading, "bf": t.is_backfill} for t in lote])

    async def muestras_alrededor(self, conn, bus_id, ts: datetime, minutos, limite):
        rows = (await conn.execute(text(
            "SELECT ts, sequence_number, lat, lon, speed_kmh, heading FROM telemetry "
            "WHERE bus_id = :b AND ts BETWEEN :d AND :h ORDER BY ts LIMIT :l"),
            {"b": bus_id, "d": ts - timedelta(minutes=minutos),
             "h": ts + timedelta(minutes=minutos), "l": limite})).mappings().all()
        return [{**dict(r), "ts": r["ts"].isoformat()} for r in rows]


class PgUmbrales:
    async def listar(self, conn):
        return [dict(r) for r in (await conn.execute(text(
            "SELECT clave, valor, unidad, descripcion, version, actualizado_en FROM umbrales ORDER BY clave"))).mappings().all()]

    async def actualizar(self, conn, clave, valor, version, actor_id):
        """Versionado optimista: solo aplica si nadie lo modificó desde que el cliente lo leyó."""
        r = (await conn.execute(text(
            "UPDATE umbrales SET valor = :v, version = version + 1, actualizado_en = now(), "
            "actualizado_por = CAST(:a AS uuid) WHERE clave = :c AND version = :ver "
            "RETURNING clave, valor, unidad, descripcion, version, actualizado_en"),
            {"v": valor, "a": actor_id, "c": clave, "ver": version})).mappings().first()
        return _row(r)


class PgCatalogo:
    async def rutas(self, conn):
        rows = (await conn.execute(text("SELECT id, geometria FROM rutas"))).mappings().all()
        return {r["id"]: _j(r["geometria"]) for r in rows}

    async def bus_ruta(self, conn):
        rows = (await conn.execute(text("SELECT id, ruta_id FROM buses"))).mappings().all()
        return {r["id"]: r["ruta_id"] for r in rows}


class PgReportes:
    async def cumplimiento(self, conn, desde, hasta, vmax):
        rows = (await conn.execute(text("""
            WITH muestras AS (
              SELECT b.concesionaria_id,
                     count(*) AS muestras,
                     count(*) FILTER (WHERE t.speed_kmh > :vmax) AS sobre_limite,
                     avg(t.speed_kmh) AS vel_prom, max(t.speed_kmh) AS vel_max,
                     count(DISTINCT t.bus_id) AS buses
              FROM telemetry t JOIN buses b ON b.id = t.bus_id
              WHERE t.ts >= :desde AND t.ts < :hasta
              GROUP BY b.concesionaria_id),
            inf AS (
              SELECT b.concesionaria_id, count(*) AS infracciones,
                     count(*) FILTER (WHERE i.tipo = 'EXCESO_VELOCIDAD') AS exceso_velocidad,
                     count(*) FILTER (WHERE i.tipo = 'DESVIO_RUTA') AS desvio_ruta,
                     count(*) FILTER (WHERE i.tipo = 'PERDIDA_SENAL') AS perdida_senal,
                     count(*) FILTER (WHERE i.estado = 'CURSADA') AS cursadas
              FROM infracciones i JOIN buses b ON b.id = i.bus_id
              WHERE i.detectada_en >= :desde AND i.detectada_en < :hasta
              GROUP BY b.concesionaria_id)
            SELECT c.id AS concesionaria_id, c.nombre,
                   coalesce(m.buses, 0) AS buses, coalesce(m.muestras, 0) AS muestras,
                   coalesce(m.sobre_limite, 0) AS sobre_limite,
                   coalesce(m.vel_prom, 0) AS vel_prom, coalesce(m.vel_max, 0) AS vel_max,
                   coalesce(i.infracciones, 0) AS infracciones, coalesce(i.exceso_velocidad, 0) AS exceso_velocidad,
                   coalesce(i.desvio_ruta, 0) AS desvio_ruta, coalesce(i.perdida_senal, 0) AS perdida_senal,
                   coalesce(i.cursadas, 0) AS cursadas
            FROM concesionarias c
            LEFT JOIN muestras m ON m.concesionaria_id = c.id
            LEFT JOIN inf i ON i.concesionaria_id = c.id
            ORDER BY c.nombre"""), {"desde": desde, "hasta": hasta, "vmax": vmax})).mappings().all()
        return [dict(r) for r in rows]

    async def serie_horaria(self, conn, concesionaria_id, desde, hasta):
        # time_bucket: función de TimescaleDB para agregar la serie por intervalos
        rows = (await conn.execute(text("""
            SELECT time_bucket('1 hour', t.ts) AS hora, count(*) AS muestras,
                   avg(t.speed_kmh) AS vel_prom, max(t.speed_kmh) AS vel_max
            FROM telemetry t JOIN buses b ON b.id = t.bus_id
            WHERE b.concesionaria_id = :c AND t.ts >= :desde AND t.ts < :hasta
            GROUP BY hora ORDER BY hora"""), {"c": concesionaria_id, "desde": desde, "hasta": hasta})).mappings().all()
        return [dict(r) for r in rows]
