"""Reglas de fiscalización — patrón STRATEGY (+ registro/fábrica).

Cada regla encapsula UN criterio de fiscalización detrás de la misma interfaz.
El motor itera las reglas sin conocer ninguna en particular: para fiscalizar un
nuevo criterio basta escribir una clase y registrarla (principio abierto/cerrado).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol, Sequence

from .geo import distancia_a_polilinea_m
from .models import EstadoBus, InfraccionCandidata, Telemetria


@dataclass(frozen=True)
class ContextoRegla:
    umbrales: Mapping[str, float]
    ruta: Sequence[Sequence[float]] | None   # geometría del trazado autorizado
    ahora: datetime


class ReglaTelemetria(Protocol):
    """Se evalúa por cada muestra de telemetría recibida."""
    tipo: str

    def evaluar(self, t: Telemetria, ctx: ContextoRegla) -> InfraccionCandidata | None: ...


class ReglaPeriodica(Protocol):
    """Se evalúa periódicamente sobre el estado de cada bus (ausencia de datos)."""
    tipo: str

    def evaluar(self, e: EstadoBus, ctx: ContextoRegla) -> InfraccionCandidata | None: ...


class ExcesoVelocidad:
    tipo = "EXCESO_VELOCIDAD"

    def evaluar(self, t, ctx):
        limite = ctx.umbrales["velocidad_max_kmh"]
        exceso = t.speed_kmh - limite
        if exceso <= 0:
            return None
        sev = "CRITICA" if exceso >= 30 else "GRAVE" if exceso >= 15 else "LEVE"
        return InfraccionCandidata(
            bus_id=t.bus_id, tipo=self.tipo, severidad=sev, detectada_en=t.ts,
            valor_medido=round(t.speed_kmh, 1), umbral=limite, lat=t.lat, lon=t.lon,
            detalle={"exceso_kmh": round(exceso, 1), "sequence_number": t.sequence_number,
                     "es_backfill": t.is_backfill})


class DesvioRuta:
    tipo = "DESVIO_RUTA"

    def evaluar(self, t, ctx):
        if not ctx.ruta:
            return None
        limite = ctx.umbrales["desvio_max_m"]
        dist = distancia_a_polilinea_m(t.lat, t.lon, ctx.ruta)
        if dist <= limite:
            return None
        sev = "GRAVE" if dist >= 2 * limite else "LEVE"
        return InfraccionCandidata(
            bus_id=t.bus_id, tipo=self.tipo, severidad=sev, detectada_en=t.ts,
            valor_medido=round(dist, 1), umbral=limite, lat=t.lat, lon=t.lon,
            detalle={"distancia_m": round(dist, 1), "sequence_number": t.sequence_number,
                     "es_backfill": t.is_backfill})


class PerdidaSenalProlongada:
    """Los túneles son normales; una ausencia más larga que el umbral sugiere
    falla o manipulación del equipo y se fiscaliza."""
    tipo = "PERDIDA_SENAL"

    def evaluar(self, e, ctx):
        limite = ctx.umbrales["senal_perdida_s"]
        if e.edad_s < limite:
            return None
        sev = "GRAVE" if e.edad_s >= 3 * limite else "LEVE"
        return InfraccionCandidata(
            bus_id=e.bus_id, tipo=self.tipo, severidad=sev, detectada_en=ctx.ahora,
            valor_medido=round(e.edad_s, 0), umbral=limite, lat=e.lat, lon=e.lon,
            detalle={"ultimo_reporte": e.ts.isoformat()})


class FabricaReglas:
    """Registro de reglas disponibles; el motor las instancia desde aquí."""
    _telemetria: dict[str, type] = {}
    _periodicas: dict[str, type] = {}

    @classmethod
    def registrar_telemetria(cls, regla: type) -> type:
        cls._telemetria[regla.tipo] = regla
        return regla

    @classmethod
    def registrar_periodica(cls, regla: type) -> type:
        cls._periodicas[regla.tipo] = regla
        return regla

    @classmethod
    def telemetria(cls, habilitadas: set[str] | None = None) -> list[ReglaTelemetria]:
        return [r() for k, r in cls._telemetria.items() if habilitadas is None or k in habilitadas]

    @classmethod
    def periodicas(cls, habilitadas: set[str] | None = None) -> list[ReglaPeriodica]:
        return [r() for k, r in cls._periodicas.items() if habilitadas is None or k in habilitadas]


FabricaReglas.registrar_telemetria(ExcesoVelocidad)
FabricaReglas.registrar_telemetria(DesvioRuta)
FabricaReglas.registrar_periodica(PerdidaSenalProlongada)
