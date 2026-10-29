"""Acceso a PostgreSQL/TimescaleDB: escritura al primario, lectura pesada a la réplica."""
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine


class Database:
    def __init__(self, primary_url: str, replica_url: str | None = None) -> None:
        self.primary = create_async_engine(primary_url, pool_size=10, max_overflow=10, pool_pre_ping=True)
        same = not replica_url or replica_url == primary_url
        self.replica = self.primary if same else create_async_engine(
            replica_url, pool_size=5, max_overflow=5, pool_pre_ping=True)

    @asynccontextmanager
    async def tx(self):
        """Transacción de escritura sobre el nodo primario (commit/rollback automático)."""
        async with self.primary.begin() as conn:
            yield conn

    @asynccontextmanager
    async def lectura(self):
        """Consultas de auditoría/reportes: van a la réplica para no competir con la ingesta."""
        async with self.replica.connect() as conn:
            yield conn

    async def dispose(self) -> None:
        await self.primary.dispose()
        if self.replica is not self.primary:
            await self.replica.dispose()


AsyncConn = AsyncConnection
