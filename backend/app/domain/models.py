"""Modelos de dominio compartidos por pipeline, motor y API."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Rol = Literal["ADMIN", "FISCALIZADOR", "OPERADOR"]
TipoInfraccion = Literal["EXCESO_VELOCIDAD", "DESVIO_RUTA", "PERDIDA_SENAL"]
Severidad = Literal["LEVE", "GRAVE", "CRITICA"]


class Telemetria(BaseModel):
    """Evento que emite la OBU de cada bus. Se valida en el procesador (hot path)."""
    event_id: UUID
    bus_id: str = Field(pattern=r"^BUS-\d{3,5}$")
    sequence_number: int = Field(ge=0)
    ts: datetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    speed_kmh: float = Field(ge=0, le=160)
    heading: float = Field(default=0, ge=0, le=360)
    is_backfill: bool = False

    @field_validator("ts")
    @classmethod
    def _ts_valido(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("ts debe incluir zona horaria")
        if v > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("ts en el futuro (reloj de la OBU desfasado)")
        return v.astimezone(timezone.utc)


@dataclass(frozen=True)
class Actor:
    id: str
    email: str
    rol: Rol


@dataclass(frozen=True)
class InfraccionCandidata:
    bus_id: str
    tipo: TipoInfraccion
    severidad: Severidad
    detectada_en: datetime
    valor_medido: float
    umbral: float
    lat: float | None = None
    lon: float | None = None
    detalle: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EstadoBus:
    bus_id: str
    lat: float
    lon: float
    speed_kmh: float
    heading: float
    ts: datetime
    edad_s: float
    estado: Literal["EN_RUTA", "SIN_SENAL"]

    def a_dict(self) -> dict:
        return {"bus_id": self.bus_id, "lat": self.lat, "lon": self.lon,
                "speed_kmh": round(self.speed_kmh, 1), "heading": self.heading,
                "ts": self.ts.isoformat(), "edad_s": round(self.edad_s, 1), "estado": self.estado}
