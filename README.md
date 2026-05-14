# Experimentos Sprint 3 — Disponibilidad y Seguridad

Monolito Django que evidencia dos ASRs.

> **Si llegas a este repo por primera vez, ve a [GUIA.md](GUIA.md)** —
> tiene el setup paso a paso, troubleshooting, y mapa del repo.
> Este README es la referencia rápida.

## ASRs evidenciados

### Disponibilidad — dos categorías de tácticas

| Categoría | Táctica | Implementación | Métrica medida |
|---|---|---|---|
| **01 Detectar fallos** | Monitoreo (Ping/Echo) | `GET /api/monitor-servicios/health/` | ping **23.8 ms** ✅ |
| **01 Detectar fallos** | Heartbeats | `HeartbeatSender` thread daemon (200 ms) → `monitor_servicios.Heartbeat` | `last_seen` avanzando entre dos consultas con ventana de 600 ms ✅ |
| **02 Reaccionar al fallo** | Fallar con gracia (graceful degradation) | `LookupError` por sección → `null` en lugar de 5xx | HTTP 200, Postgres preservado, **545 ms** con Mongo caído ✅ |

### Seguridad

| Táctica | Implementación | Métrica medida (smoke) | Métrica medida (carga) |
|---|---|---|---|
| Rate Limiting | `TrafficMonitorMiddleware` con umbral 100 reqs / 60 s | Bloqueo en req **#101** (serie) ✅ | **2,797 reqs / 10 s** (308 RPS, 30 users concurrentes), 2,669 → 403, 128 colados antes del bloqueo ✅ |

## Componentes

| App | Prefijo API | Responsabilidad |
|---|---|---|
| [api_gateway/](api_gateway/) | `/api/gateway/` | Punto de entrada — combina datos PG + Mongo y degrada si Mongo cae. |
| [monitor_trafico/](monitor_trafico/) | `/api/monitor-trafico/` | Middleware de rate limiting + endpoints de stats / unblock. |
| [monitor_servicios/](monitor_servicios/) | `/api/monitor-servicios/` | Recibe heartbeats, expone health-check. |
| [generador_reportes/](generador_reportes/) | `/api/generador-reportes/` | Combina datos Postgres + Mongo. |
| [recolector_inventarios/](recolector_inventarios/) | `/api/recolector/` | Capa de datos sobre PostgreSQL + MongoDB. |

## Setup rápido

### Modo PROD (servidor AWS del equipo)

Usa la base de datos compartida en `100.31.110.6` (Postgres + Mongo).

```bash
uv sync
uv run python manage.py migrate
uv run python data-faker/seed_data.py
uv run python manage.py runserver
```

### Modo TEST (local, sin AWS)

Usa SQLite local + Mongo "fail-fast" — la pre-condición para evidenciar
degradación controlada (Mongo no accesible).

```bash
uv sync
rm -f db_test.sqlite3
DJANGO_SETTINGS_MODULE=settings_test uv run python manage.py migrate
uv run python experiments/_seed_postgres_only.py
DJANGO_SETTINGS_MODULE=settings_test \
    uv run python manage.py runserver 127.0.0.1:8000 --noreload
```

> En PowerShell usa `$env:DJANGO_SETTINGS_MODULE="settings_test"` antes
> del comando, no la sintaxis `VAR=valor cmd`.

Detalles en [GUIA.md §3](GUIA.md#3-setup-paso-a-paso).

## Correr los experimentos

Con el server arriba, en otra terminal:

```bash
# Disponibilidad 01 — Ping/Echo + Heartbeats están vivos y avanzando
PYTHONIOENCODING=utf-8 uv run python experiments/measure_heartbeat_monitoring.py

# Disponibilidad 02 — Degradación controlada con Mongo caído
PYTHONIOENCODING=utf-8 \
EXPERIMENT_BUSINESS_ID=11111111-1111-1111-1111-111111111111 \
uv run python experiments/measure_graceful_degradation.py

# Seguridad (smoke) — rate limiting en serie (105 GETs)
PYTHONIOENCODING=utf-8 uv run python experiments/measure_security_ratelimit.py

# Seguridad (carga) — DoS concurrente con Locust (30 users en paralelo, 10s)
PYTHONIOENCODING=utf-8 \
USERS=30 SPAWN_RATE=15 RUN_TIME=10s \
uv run python experiments/measure_security_concurrent_dos.py

# Tests de integración del Recolector (Felipe — 71 checks)
PYTHONIOENCODING=utf-8 uv run python tests/test_recolector.py
```

Cada script imprime eventos JSON line y exit code 0/1.

## Endpoints clave

```
# Gateway (entrada principal)
GET  /api/gateway/reportes/?business_id=<UUID>&month=YYYY-MM
GET  /api/gateway/status/

# Recolector (CRUD sobre PG + Mongo)
GET  /api/recolector/businesses/<UUID>/USDConsumption[?month=YYYY-MM]
GET  /api/recolector/businesses/<UUID>/CloudGovernance
GET  /api/recolector/businesses/<UUID>/S3Usage
GET  /api/recolector/businesses/<UUID>/EC2Usage

# Generador de reportes (acceso directo, sin Gateway)
GET  /api/generador-reportes/health/
GET  /api/generador-reportes/generar/?business_id=<UUID>&month=YYYY-MM

# Monitor de tráfico (experimento de seguridad)
GET  /api/monitor-trafico/stats/?window=60
GET  /api/monitor-trafico/blocked/
POST /api/monitor-trafico/unblock/<ip>/

# Monitor de servicios
GET  /api/monitor-servicios/health/
POST /api/monitor-servicios/monitor/heartbeat/
GET  /api/monitor-servicios/monitor/status/[<service_name>/]
GET  /api/monitor-servicios/monitor/stale/
```

## Parámetros del experimento

| Parámetro | Valor | Archivo |
|---|---|---|
| Mongo `serverSelectionTimeoutMS` | 500 ms | [recolector_inventarios/connectors.py](recolector_inventarios/connectors.py) |
| Mongo `connectTimeoutMS` | 500 ms | [recolector_inventarios/connectors.py](recolector_inventarios/connectors.py) |
| Mongo `socketTimeoutMS` | 1000 ms | [recolector_inventarios/connectors.py](recolector_inventarios/connectors.py) |
| `REQUEST_THRESHOLD` (rate-limit) | 100 reqs | [monitor_trafico/services.py](monitor_trafico/services.py) |
| `TIME_WINDOW_SECONDS` (rate-limit) | 60 s | [monitor_trafico/services.py](monitor_trafico/services.py) |
| `TIMEOUT_MS` (presupuesto del experimento) | 1500 ms | [experiments/measure_graceful_degradation.py](experiments/measure_graceful_degradation.py) |

## Estructura

```
.
├── manage.py            # apunta a 'settings'
├── settings.py          # DATABASES / MONGO_URI (PROD: AWS)
├── settings_test.py     # SQLite local + Mongo fail-fast (TEST)
├── urls.py              # ROOT_URLCONF
├── wsgi.py
├── pyproject.toml + uv.lock     # dependencias gestionadas con uv
├── requirements.txt             # alternativa pip
├── GUIA.md                      # guía de equipo (lee este primero)
├── README.md
│
├── api_gateway/                 # Entrada principal
├── monitor_servicios/           # Heartbeats / health-check
├── monitor_trafico/             # Rate Limiting / DoS
├── generador_reportes/          # Combina datos PG + Mongo (degrada limpio)
├── recolector_inventarios/      # Acceso a datos
│
├── data-faker/seed_data.py      # Seed completo PG + Mongo
├── experiments/                 # Scripts de medición de ASRs
│   ├── _common.py
│   ├── _seed_postgres_only.py
│   ├── measure_heartbeat_monitoring.py     # Disp 01 (Ping/Echo + Heartbeats)
│   ├── measure_graceful_degradation.py     # Disp 02 (Fallar con gracia)
│   ├── measure_security_ratelimit.py       # Seg smoke (serie, 105 GETs)
│   ├── measure_security_concurrent_dos.py  # Seg carga (Locust, concurrente)
│   └── locustfile_attacker.py              # Definición del usuario Locust
├── tests/test_recolector.py     # 71 tests de integración HTTP
└── setups/
    ├── setup-dbs.sh             # instala Postgres 16 + Mongo 8 (Ubuntu 24.04)
    └── setup-credentials.sh     # crea bite_db / bite_telemetry + usuarios
```

## Solución de problemas (rápido)

| Error | Solución |
|-------|----------|
| `ModuleNotFoundError: No module named 'psycopg2'` | Prefijo `uv run python ...` |
| `relation "..." does not exist` | `uv run python manage.py migrate` |
| `Connection refused` (Postgres/Mongo) | IP de AWS cambió; pídela al equipo o usa modo TEST |
| `UnicodeEncodeError: 'charmap' codec` | `PYTHONIOENCODING=utf-8` antes del comando |
| El experimento de degradación falla con `Mongo respondió` | Pre-condición no se cumple — Mongo está accesible. Apaga Mongo o usa `settings_test` apuntando a un puerto vacío. |

Más casos en [GUIA.md §7](GUIA.md#7-troubleshooting).
