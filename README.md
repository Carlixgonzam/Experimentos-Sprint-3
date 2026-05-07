# Experimentos Sprint 3 — Disponibilidad y Seguridad

Monolito Django que evidencia tres ASRs:

- **ASR1 — Disponibilidad / Detección:** una instancia caída del Generador de
  Reportes es marcada como `is_alive=false` en **< 1 s** (táctica *Heartbeat*).
- **ASR2 — Disponibilidad / Recuperación:** tras la detección, el API Gateway
  enruta automáticamente al nodo sano restante en **< 1 s** (táctica
  *Active Redundancy*, estrategia *first-healthy*).
- **ASR-Seg — Seguridad / Rate Limiting:** el middleware de Monitor de Tráfico
  bloquea con HTTP 403 cualquier IP que exceda
  `TrafficMonitorService.REQUEST_THRESHOLD` (default 100 req / 60 s).

## Componentes

| App | Prefijo API | Responsabilidad |
|---|---|---|
| [api_gateway/](api_gateway/) | `/api/gateway/` | Punto de entrada + endpoints de chaos-engineering del experimento. |
| [monitor_trafico/](monitor_trafico/) | `/api/monitor-trafico/` | Middleware de rate limiting + endpoints de stats / unblock. |
| [monitor_servicios/](monitor_servicios/) | `/api/monitor-servicios/` | Recibe heartbeats, detecta caídas. |
| [generador_reportes/](generador_reportes/) | `/api/generador-reportes/` | Combina datos Postgres + Mongo. Emite heartbeats simulando 2 instancias. |
| [recolector_inventarios/](recolector_inventarios/) | `/api/recolector/` | Capa de datos sobre PostgreSQL + MongoDB. |

## Estructura

```
.
├── manage.py            # apunta a 'settings'
├── settings.py          # DATABASES / MONGO_URI / INSTALLED_APPS / etc.
├── urls.py              # ROOT_URLCONF
├── wsgi.py              # WSGI_APPLICATION
├── api_gateway/
├── generador_reportes/
├── monitor_servicios/
├── monitor_trafico/
├── recolector_inventarios/
├── data-faker/seed_data.py    # popular Postgres + Mongo (Django ORM + pymongo)
├── experiments/               # scripts de medición ASR1 / ASR2 / Rate-Limit
│   ├── measure_asr1_detection.py
│   ├── measure_asr2_failover.py
│   └── measure_security_ratelimit.py
├── tests/test_recolector.py   # tests de integración del Recolector
├── setups/
│   ├── setup-dbs.sh           # instala Postgres 16 + Mongo 8 (Ubuntu 24.04)
│   └── setup-credentials.sh   # crea bite_db / bite_telemetry y usuarios
├── pyproject.toml             # gestionado por uv
└── requirements.txt           # alternativa con pip
```

## Setup

### Opción A — `uv` (recomendada)

`uv` (https://astral.sh/uv) es un gestor de paquetes mucho más rápido que pip
y maneja entornos virtuales sin pasos extra. Instalación:

- **Mac / Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Windows:** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Todos los comandos Python se prefijan con `uv run`:

```bash
uv sync                                       # instala deps de pyproject.toml
uv run python manage.py migrate
uv run python data-faker/seed_data.py
uv run python manage.py runserver
```

### Opción B — `pip` clásico

```bash
pip install -r requirements.txt
python manage.py migrate
python data-faker/seed_data.py
python manage.py runserver
```

### Bases de datos

El [settings.py](settings.py) hardcodea las credenciales hacia un servidor
AWS (`100.31.110.6`) que ya tiene PostgreSQL y MongoDB con los usuarios
creados por [setups/setup-credentials.sh](setups/setup-credentials.sh).

Si la IP cambia o trabajas local, edita `DATABASES['default']['HOST']` y
`MONGO_URI` en [settings.py](settings.py).

Para levantar las DBs desde cero (Ubuntu 24.04):

```bash
sudo ./setups/setup-dbs.sh
sudo ./setups/setup-credentials.sh
```

## Ejecutar los experimentos

Con el servidor arriba (`runserver`) y `seed_data.py` ejecutado, en otra terminal:

### ASR1 — Detección de fallo en < 1 s

```bash
uv run python experiments/measure_asr1_detection.py
```

Mata `generador_reportes_1` y hace polling cada 50 ms a `/medir/` hasta
detectar `is_alive=false`. PASS si `seconds_since_kill < 1.0`.

Variables: `BASE_URL`, `INSTANCE`, `POLL_MS`, `TIMEOUT_S`.

### ASR2 — Failover < 1.5 s, routing < 100 ms

```bash
uv run python experiments/measure_asr2_failover.py
```

Mata `generador_reportes_1`, espera detección, y cronometra
`GET /api/gateway/reportes/?business_id=<UUID>`. Verifica que
`routed_to == generador_reportes_2` y que el reporte combinado se generó.

Variables: `BASE_URL`, `EXPERIMENT_BUSINESS_ID`, `KILLED_INSTANCE`,
`EXPECTED_FAILOVER`, `DETECTION_TIMEOUT_S`.

### Seguridad — Rate Limiting

```bash
uv run python experiments/measure_security_ratelimit.py
```

Bombardea `/api/monitor-servicios/health/` con `X-Forwarded-For: 10.0.0.99`,
confirma transición 200 → 403, presencia en `/blocked/`, y que
`POST /api/monitor-trafico/unblock/<ip>/` la libera.

Variables: `BASE_URL`, `ATTACKER_IP`, `TOTAL_REQUESTS`, `THRESHOLD`.

> Cada script imprime un evento por línea como JSON
> (`{"event": "PASS", ...}` / `{"event": "FAIL", "reason": "..."}`)
> y exit code 0/1 — listo para CI.

### Tests del Recolector

Tests de integración HTTP escritos por el equipo:

```bash
uv run python tests/test_recolector.py        # silencioso
uv run python tests/test_recolector.py -v     # verbose
```

## Endpoints clave

```
# Generador de reportes (acceso directo)
GET  /api/generador-reportes/health/
GET  /api/generador-reportes/generar/?business_id=<UUID>&month=YYYY-MM

# Gateway con Active Redundancy (entrada principal)
GET  /api/gateway/reportes/?business_id=<UUID>&month=YYYY-MM
GET  /api/gateway/status/

# Endpoints del experimento de disponibilidad
POST /api/gateway/experimento/matar/<instance>/
POST /api/gateway/experimento/revivir/<instance>/
GET  /api/gateway/experimento/medir/

# Recolector
GET  /api/recolector/businesses/<UUID>/USDConsumption[?month=YYYY-MM]
GET  /api/recolector/businesses/<UUID>/CloudGovernance
GET  /api/recolector/businesses/<UUID>/S3Usage
GET  /api/recolector/businesses/<UUID>/EC2Usage

# Monitor de tráfico (experimento de seguridad)
GET  /api/monitor-trafico/stats/?window=60
GET  /api/monitor-trafico/blocked/
POST /api/monitor-trafico/unblock/<ip>/

# Monitor de servicios
GET  /api/monitor-servicios/health/
POST /api/monitor-servicios/monitor/heartbeat/
GET  /api/monitor-servicios/monitor/status/
GET  /api/monitor-servicios/monitor/status/<service_name>/
GET  /api/monitor-servicios/monitor/stale/
```

## Parámetros del experimento

Definidos en [settings.py](settings.py):

| Parámetro | Valor | Significado |
|---|---|---|
| `HEARTBEAT_INTERVAL_SECONDS` | `0.2` | Frecuencia de emisión de heartbeats. |
| `expected_interval_seconds` | `0.8` | Calculado como intervalo × 4 al registrar la instancia. Umbral de detección. |
| `REPORT_GENERATOR_INSTANCES` | `['generador_reportes_1', 'generador_reportes_2']` | Instancias lógicas. |

En [monitor_trafico/services.py](monitor_trafico/services.py):

| Parámetro | Valor | Significado |
|---|---|---|
| `REQUEST_THRESHOLD` | `100` | Reqs por IP que disparan el bloqueo. |
| `TIME_WINDOW_SECONDS` | `60` | Ventana sobre la cual se cuentan las reqs. |

## Notas para el evaluador

- **Por qué 0.2 s + umbral 0.8 s:** peor caso de detección = `expected_interval`
  (justo después de un heartbeat OK, esperar el siguiente que nunca llega).
  0.8 s < 1 s → ASR1 cumplido por construcción.
- **Por qué first-healthy y no round-robin:** simplifica el experimento y
  permite verificar de forma determinista que la siguiente request va al
  segundo nodo sano. La estrategia es intercambiable en
  [api_gateway/services.py](api_gateway/services.py).
- **El middleware de tráfico afecta al experimento ASR2:** los scripts mandan
  pocas requests (<10) por lo que no disparan el rate limiting. Si vas a
  ejecutar muchas iteraciones consecutivas, usa
  `POST /api/monitor-trafico/unblock/127.0.0.1/` entre corridas.
- **Conexión Mongo lazy:** `MongoConnector` no abre socket hasta la primera
  consulta. Esto permite que el monolito arranque y los heartbeats funcionen
  aunque Mongo no esté disponible.

## Solución de Problemas

| Error | Causa | Solución |
|-------|-------|----------|
| `ModuleNotFoundError: No module named 'psycopg2'` | Estás usando Python global en lugar del entorno de `uv` | Prefija los comandos con `uv run python ...` |
| `relation "..." does not exist` | Migraciones no aplicadas | `uv run python manage.py migrate` |
| `Connection refused` (Postgres/Mongo) | IP de AWS cambió o el firewall bloquea 5432/27017 | Pide la IP actualizada; verifica firewall |
| `ModuleNotFoundError: No module named 'wsgi'` | `WSGI_APPLICATION` mal configurado | Debe ser `WSGI_APPLICATION = 'wsgi.application'` (no `core.wsgi`) |
| `NotImplementedError` desde `ReportGeneratorService` | Estás en una versión vieja antes del Sprint 3 | `git pull`; el servicio real está en [generador_reportes/services.py](generador_reportes/services.py) |
