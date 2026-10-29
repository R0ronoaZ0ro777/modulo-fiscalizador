"""Ensamblado de dependencias (composición manual, sin framework de DI)."""
from dataclasses import dataclass

from .config import Settings
from .events import EventBus
from .repositories import postgres as pg
from .repositories.redis_flota import CooldownRedis, FlotaRedis
from .security import LoginGuard
from .services.auditoria import AuditoriaService
from .services.auth import AuthService
from .services.difusion import HubWS
from .services.infracciones import InfraccionService
from .services.motor import MotorFiscalizacion
from .services.umbrales import UmbralProvider, UmbralService


@dataclass
class Repos:
    usuarios: object
    infracciones: object
    actas: object
    auditoria: object
    telemetria: object
    umbrales: object
    catalogo: object
    reportes: object
    flota: object
    cooldown: object


@dataclass
class Container:
    settings: Settings
    db: object
    redis: object
    bus: EventBus
    repos: Repos
    auditoria: AuditoriaService
    auth: AuthService
    infracciones: InfraccionService
    umbrales: UmbralService
    umbral_provider: UmbralProvider
    motor: MotorFiscalizacion
    hub: HubWS


def repos_reales(redis, settings: Settings) -> Repos:
    return Repos(usuarios=pg.PgUsuarios(), infracciones=pg.PgInfracciones(), actas=pg.PgActas(),
                 auditoria=pg.PgAuditoria(), telemetria=pg.PgTelemetria(), umbrales=pg.PgUmbrales(),
                 catalogo=pg.PgCatalogo(), reportes=pg.PgReportes(),
                 flota=FlotaRedis(redis, settings.offline_after_s), cooldown=CooldownRedis(redis))


def ensamblar(settings: Settings, db, redis, repos: Repos) -> Container:
    bus = EventBus()
    auditoria = AuditoriaService(repos.auditoria)
    guard = LoginGuard(redis, settings.login_max_intentos, settings.login_bloqueo_min)
    infracciones = InfraccionService(db, repos.infracciones, repos.actas, repos.telemetria, auditoria, bus)
    provider = UmbralProvider(db, repos.umbrales, bus)
    motor = MotorFiscalizacion(db=db, catalogo=repos.catalogo, umbrales=provider, infracciones=infracciones,
                               flota=repos.flota, cooldown=repos.cooldown, cooldown_s=settings.cooldown_s)
    return Container(settings=settings, db=db, redis=redis, bus=bus, repos=repos, auditoria=auditoria,
                     auth=AuthService(settings, db, repos.usuarios, guard, auditoria),
                     infracciones=infracciones, umbrales=UmbralService(db, repos.umbrales, auditoria, bus),
                     umbral_provider=provider, motor=motor, hub=HubWS(bus))
