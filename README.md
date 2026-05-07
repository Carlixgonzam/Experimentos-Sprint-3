# Experimentos Sprint 3 — Disponibilidad y Seguridad

Monolito Django que evidencia tres ASRs.

> **Si llegas a este repo por primera vez, ve a [GUIA.md](GUIA.md)** —
> tiene el setup paso a paso, troubleshooting, y mapa del repo.
> Este README es la referencia rápida.

## ASRs evidenciados

| ID | Tipo | Requisito | Métrica medida (2026-05-07) |
|---|---|---|---|
| ASR1 | Disponibilidad / Detección | Detectar caída < 1 s (Heartbeat) | **779.9 ms** ✅ |
| ASR2 | Disponibilidad / Recuperación | Decisión de routing < 100 ms (Active Redundancy) | **2.66 ms** ✅ |
| ASR-Seg | Seguridad / Rate Limiting | Bloquear IPs que excedan 100 req / 60 s | bloqueo en req **#101** ✅ |

## Componentes

| App | Prefijo API | Responsabilidad |
|---|---|---|
| [api_gateway/](api_gateway/) | `/api/gateway/` | Punto de entrada + endpoints de chaos-engineering del experimento. |
| [monitor_trafico/](monitor_trafico/) | `/api/monitor-trafico/` | Middleware de rate limiting + endpoints de stats / unblock. |
| [monitor_servicios/](monitor_servicios/) | `/api/monitor-servicios/` | Recibe heartbeats, detecta caídas. |
| [generador_reportes/](generador_reportes/) | `/api/generador-reportes/` | Combina datos Postgres + Mongo. Emite heartbeats simulando 2 instancias. |
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

Usa SQLite local + Mongo "fail-fast". Útil para correr la suite cuando
AWS no es alcanzable.

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

## Correr los tests

Con el server arriba, en otra terminal:

```bash
# Tests de integración del Recolector (Felipe — 71 checks)
PYTHONIOENCODING=utf-8 uv run python tests/test_recolector.py

# ASR1 — detección de caída
PYTHONIOENCODING=utf-8 uv run python experiments/measure_asr1_detection.py

# ASR2 — failover (necesita un business_id válido del seed)
PYTHONIOENCODING=utf-8 \
EXPERIMENT_BUSINESS_ID=11111111-1111-1111-1111-111111111111 \
uv run python experiments/measure_asr2_failover.py

# ASR-Seg — rate limiting
PYTHONIOENCODING=utf-8 uv run python experiments/measure_security_ratelimit.py
```

Cada script imprime eventos JSON line y exit code 0/1.

## Endpoints clave

```
# Gateway (entrada principal con Active Redundancy)
GET  /api/gateway/reportes/?business_id=<UUID>&month=YYYY-MM
GET  /api/gateway/status/

# Endpoints del experimento de disponibilidad
POST /api/gateway/experimento/matar/<instance>/
POST /api/gateway/experimento/revivir/<instance>/
GET  /api/gateway/experimento/medir/

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
| `HEARTBEAT_INTERVAL_SECONDS` | 0.2 s | [settings.py](settings.py) |
| `expected_interval_seconds` | 0.8 s | [generador_reportes/heartbeat.py](generador_reportes/heartbeat.py) (intervalo × 4) |
| `REQUEST_THRESHOLD` | 100 reqs | [monitor_trafico/services.py](monitor_trafico/services.py) |
| `TIME_WINDOW_SECONDS` | 60 s | [monitor_trafico/services.py](monitor_trafico/services.py) |
| Mongo `serverSelectionTimeoutMS` | 500 ms | [recolector_inventarios/connectors.py](recolector_inventarios/connectors.py) |

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
├── api_gateway/                 # Active Redundancy / failover
├── monitor_servicios/           # Heartbeats / Ping-Echo
├── monitor_trafico/             # Rate Limiting / DoS
├── generador_reportes/          # Combina datos PG + Mongo
├── recolector_inventarios/      # Acceso a datos
│
├── data-faker/seed_data.py      # Seed completo PG + Mongo (vía ORM + pymongo)
├── experiments/                 # Scripts de medición de ASRs
│   ├── _common.py
│   ├── _seed_postgres_only.py
│   ├── measure_asr1_detection.py
│   ├── measure_asr2_failover.py
│   └── measure_security_ratelimit.py
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
| Reporte tarda 30 s con Mongo caído | `git pull` (timeout fix está en commit `3f2f81c`) |

Más casos en [GUIA.md §7](GUIA.md#7-troubleshooting).
