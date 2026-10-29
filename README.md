## Tecnologías (las del informe)
| Capa | Informe | Aquí |
|---|---|---|
| Presentación | MVVM · React + Redux Toolkit + redux-persist | React 18 + TypeScript + Vite; ViewModels como hooks; último estado de la flota persistido |
| Aplicación | Monolito modular (soporte) + microservicios (hot path) | FastAPI (monolito: auth, fiscalización, reportes) · `gateway` y `processor` como procesos independientes |
| Datos | PostgreSQL **con TimescaleDB** + Redis | `timescale/timescaledb:latest-pg16` (hypertable, compresión, retención, `time_bucket`) + Redis (última posición, índice geoespacial, cooldown, bloqueo de login) |
| Mensajería | MQTT QoS 1 → Kafka particionado por bus | Mosquitto → Kafka (KRaft, 6 particiones, clave = `bus_id`) |
| Tiempo real | WebSocket | WebSocket con JWT, reconexión con backoff exponencial |
| Seguridad | OAuth2 + JWT corto, MFA para fiscalización, auditoría forense | JWT 15 min, TOTP, Argon2id, bloqueo por intentos, RBAC, hash encadenado + triggers anti-modificación |
| Réplica | Réplica de solo lectura para auditoría/reportes | Perfil `replica` (streaming replication); auditoría y reportes leen de ella |

# Intrucciones

## Iniciar Docker Desktop
## Ejecutar en Terminal en la ruta raiz del proyecto el siguiente comando:
docker compose up --build

## Abrir en navegador:
http://localhost:8080

### Usuarios de demostración
Copiar y pegar para iniciar sesion
| Rol | Correo | Contraseña | MFA |
|---|---|---|---|
| Fiscalizador | fiscalizador@mtt.cl | `Fiscal#2026` | sí |
| Administrador | admin@mtt.cl | `Admin#2026` | sí |
| Operador | operador@mtt.cl | `Operador#2026` | no |

## Generar el codigo MFA para Fiscalizador y Administrador ejecutar los comandos siguientes en misma ruta raiz del proyecto:
## Para Fiscalizador
docker compose exec backend python -m app.tools.totp fiscalizador@mtt.cl
## Para Administrador
docker compose exec backend python -m app.tools.totp admin@mtt.cl

## Configuración de los parámetros de simulación y del sistema

Los parámetros principales se pueden modificar desde el archivo `.env`, ubicado en la
raíz del proyecto. Estos valores sobrescriben los valores predeterminados definidos
en `backend/app/config.py`.

### Parámetros del simulador

```env
SIM_BUSES=50
SIM_INTERVAL_S=2
SIM_FAULT_RATE=1.0
```

| Parámetro | Descripción |
|---|---|
| `SIM_BUSES` | Cantidad de buses simulados. |
| `SIM_INTERVAL_S` | Intervalo, en segundos, entre las muestras de telemetría de cada bus. |
| `SIM_FAULT_RATE` | Multiplicador de la probabilidad de eventos anómalos. `1.0` utiliza la probabilidad normal; `0.5` la reduce a la mitad y `2.0` la duplica. |

Los eventos que pueden generarse son:

- Exceso de velocidad.
- Desvíos de ruta.
- Fallas prolongadas del equipo.
- Pérdidas breves de señal o paso por túneles.
- Reenvíos de mensajes pendientes (`backfill`).
- Mensajes duplicados por reintentos.

La cantidad aproximada de mensajes generados por segundo se calcula así:

```text
mensajes por segundo ≈ SIM_BUSES / SIM_INTERVAL_S
```

Por ejemplo, `SIM_BUSES=1800` y `SIM_INTERVAL_S=1` generan aproximadamente
1.800 mensajes por segundo.

### Parámetros de fiscalización y Kafka

Estos valores tienen sus valores predeterminados en
`backend/app/config.py`:

```python
offline_after_s: int = 45
topic_partitions: int = 6
```

| Parámetro | Ubicación | Descripción |
|---|---|---|
| `offline_after_s` | `backend/app/config.py` | Segundos desde el último mensaje recibido antes de marcar un bus como `SIN_SENAL`. Puede sobrescribirse desde `.env` con `OFFLINE_AFTER_S`. |
| `topic_partitions` | `backend/app/config.py` | Cantidad de particiones de los tópicos Kafka. Permite distribuir los mensajes entre varios consumidores del mismo grupo. Puede sobrescribirse desde `.env` con `TOPIC_PARTITIONS`. |

Para una prueba de carga con 1.800 buses se puede utilizar:

```env
SIM_BUSES=1800
SIM_INTERVAL_S=1
SIM_FAULT_RATE=0.5
OFFLINE_AFTER_S=180
TOPIC_PARTITIONS=6
```

`OFFLINE_AFTER_S` solo aumenta la tolerancia antes de mostrar un bus como
`SIN_SENAL`; no aumenta la capacidad de procesamiento del sistema.

### Tamaño máximo del lote del procesador

El procesador consume los mensajes desde Kafka en
`backend/app/pipeline/processor.py`:

```python
lotes = await consumidor.getmany(
    timeout_ms=500,
    max_records=500,
)
```

`max_records` limita la cantidad máxima de mensajes que el consumidor intenta
recibir en una sola llamada a `getmany()`. Por ejemplo, con `max_records=500`,
el procesador recibe como máximo 500 mensajes por lote y debe procesar varios
lotes para alcanzar los aproximadamente 1.800 mensajes generados por segundo.

Para una carga de 1.800 buses se puede aumentar el tamaño del lote:

```python
lotes = await consumidor.getmany(
    timeout_ms=250,
    max_records=2000,
)
```

Este parámetro no limita la cantidad total de mensajes que Kafka puede recibir
ni garantiza que el sistema procese 2.000 mensajes por segundo. Solo controla
el tamaño de cada lote; la capacidad real depende del rendimiento de Kafka,
TimescaleDB, Redis y de las instancias del procesador.