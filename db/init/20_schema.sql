-- =============================================================================
-- Esquema del módulo de Fiscalización  (PostgreSQL + TimescaleDB)
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ── Datos maestros (consistencia fuerte, ACID) ───────────────────────────────
CREATE TABLE concesionarias (
    id      SERIAL PRIMARY KEY,
    nombre  TEXT NOT NULL UNIQUE
);

CREATE TABLE rutas (
    id                TEXT PRIMARY KEY,
    nombre            TEXT NOT NULL,
    concesionaria_id  INT  NOT NULL REFERENCES concesionarias(id),
    geometria         JSONB NOT NULL            -- [[lat, lon], ...]
);

CREATE TABLE buses (
    id                TEXT PRIMARY KEY,         -- BUS-001
    patente           TEXT NOT NULL UNIQUE,
    ruta_id           TEXT NOT NULL REFERENCES rutas(id),
    concesionaria_id  INT  NOT NULL REFERENCES concesionarias(id)
);
CREATE INDEX ON buses (concesionaria_id);

CREATE TABLE usuarios (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email          TEXT NOT NULL UNIQUE,
    nombre         TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    rol            TEXT NOT NULL CHECK (rol IN ('ADMIN','FISCALIZADOR','OPERADOR')),
    mfa_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    totp_secret    TEXT,
    activo         BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Umbrales de fiscalización: dato maestro crítico con versionado optimista.
CREATE TABLE umbrales (
    clave           TEXT PRIMARY KEY,
    valor           DOUBLE PRECISION NOT NULL,
    unidad          TEXT NOT NULL,
    descripcion     TEXT NOT NULL,
    version         INT  NOT NULL DEFAULT 1,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_por UUID REFERENCES usuarios(id)
);

-- ── Telemetría: serie de tiempo (hypertable) ─────────────────────────────────
CREATE TABLE telemetry (
    ts               TIMESTAMPTZ NOT NULL,
    bus_id           TEXT        NOT NULL,
    sequence_number  BIGINT      NOT NULL,
    event_id         UUID        NOT NULL,
    lat              DOUBLE PRECISION NOT NULL,
    lon              DOUBLE PRECISION NOT NULL,
    speed_kmh        REAL        NOT NULL,
    heading          REAL        NOT NULL DEFAULT 0,
    is_backfill      BOOLEAN     NOT NULL DEFAULT FALSE,
    received_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Idempotencia: un reintento del OBU (mismo bus + secuencia + instante) no duplica.
    PRIMARY KEY (bus_id, ts, sequence_number)
);
SELECT create_hypertable('telemetry', 'ts', chunk_time_interval => INTERVAL '1 day');
ALTER TABLE telemetry SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'bus_id',
    timescaledb.compress_orderby   = 'ts DESC'
);
SELECT add_compression_policy('telemetry', INTERVAL '7 days');
SELECT add_retention_policy('telemetry', INTERVAL '180 days');

-- ── Fiscalización ────────────────────────────────────────────────────────────
CREATE TABLE infracciones (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bus_id         TEXT NOT NULL REFERENCES buses(id),
    tipo           TEXT NOT NULL CHECK (tipo IN ('EXCESO_VELOCIDAD','DESVIO_RUTA','PERDIDA_SENAL')),
    severidad      TEXT NOT NULL CHECK (severidad IN ('LEVE','GRAVE','CRITICA')),
    estado         TEXT NOT NULL DEFAULT 'DETECTADA'
                   CHECK (estado IN ('DETECTADA','EN_REVISION','CURSADA','DESCARTADA')),
    detectada_en   TIMESTAMPTZ NOT NULL,
    valor_medido   DOUBLE PRECISION NOT NULL,
    umbral         DOUBLE PRECISION NOT NULL,
    lat            DOUBLE PRECISION,
    lon            DOUBLE PRECISION,
    detalle        JSONB NOT NULL DEFAULT '{}'::jsonb,
    creada_en      TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizada_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON infracciones (estado, detectada_en DESC);
CREATE INDEX ON infracciones (bus_id, detectada_en DESC);

-- Un acta por infracción: la restricción UNIQUE impide resolver dos veces la misma.
CREATE TABLE actas (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    infraccion_id    UUID NOT NULL UNIQUE REFERENCES infracciones(id),
    fiscalizador_id  UUID NOT NULL REFERENCES usuarios(id),
    resolucion       TEXT NOT NULL CHECK (resolucion IN ('CURSAR','DESCARTAR')),
    observaciones    TEXT NOT NULL,
    sancion          JSONB,
    evidencia        JSONB NOT NULL,      -- snapshot de la infracción + muestras de telemetría
    creada_en        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Auditoría forense: append-only con hash encadenado ───────────────────────
CREATE TABLE audit_log (
    id                BIGSERIAL PRIMARY KEY,
    ts                TIMESTAMPTZ NOT NULL,
    actor_id          UUID,
    actor_rol         TEXT,
    accion            TEXT NOT NULL,
    entidad           TEXT,
    entidad_id        TEXT,
    payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_canonico  TEXT  NOT NULL,     -- texto exacto que se hasheó
    prev_hash         CHAR(64) NOT NULL,
    hash              CHAR(64) NOT NULL UNIQUE
);

CREATE FUNCTION audit_log_inmutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log es append-only: % no permitido', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_no_mutar
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_inmutable();
CREATE TRIGGER audit_log_no_truncar
    BEFORE TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION audit_log_inmutable();
