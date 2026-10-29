#!/bin/bash
# Réplica en streaming (hot standby). Clona el primario la primera vez que arranca.
set -e
until pg_isready -h timescaledb -U "$POSTGRES_USER" >/dev/null 2>&1; do sleep 2; done
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  mkdir -p "$PGDATA" && chown -R postgres:postgres "$PGDATA" && chmod 700 "$PGDATA"
  PGPASSWORD="$REPL_PASSWORD" gosu postgres pg_basebackup \
    -h timescaledb -U replicator -D "$PGDATA" -Fp -Xs -R -P
fi
exec docker-entrypoint.sh postgres -c hot_standby=on
