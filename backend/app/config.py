"""Configuración centralizada (12-factor): todo viene de variables de entorno."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Persistencia
    database_url: str = "postgresql+asyncpg://fiscal:fiscal_dev_pw@localhost:5432/fiscalizacion"
    database_replica_url: str | None = None      # réplica de solo lectura (auditoría/reportes)
    redis_url: str = "redis://localhost:6379/0"

    # Mensajería
    kafka_bootstrap: str = "localhost:9094"
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    topic_raw: str = "raw-telemetry"
    topic_validated: str = "telemetry-validated"
    topic_dlq: str = "telemetry-dlq"
    topic_partitions: int = 6
    ##topic_partitions define la cantidad de particionies s

    # Seguridad
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"
    jwt_alg: str = "HS256"
    access_ttl_min: int = 15          # JWT de vida corta
    refresh_ttl_h: int = 8
    mfa_ttl_min: int = 5
    login_max_intentos: int = 5
    login_bloqueo_min: int = 15
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # Fiscalización
    offline_after_s: int = 45         # un bus sin reportar más de esto se muestra "sin señal"
    cooldown_s: int = 300             # no repetir la misma infracción (bus+tipo) antes de esto
    motor_activo: bool = True
    seed_demo: bool = True

    # Simulador
    sim_buses: int = 40
    sim_interval_s: float = 2.0
    sim_fault_rate: float = 1.0

    @property
    def replica_url(self) -> str:
        return self.database_replica_url or self.database_url

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
