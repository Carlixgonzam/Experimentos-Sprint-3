# Guía del proyecto — Experimentos Sprint 3

> Documento de onboarding para miembros del equipo. Cubre el estado actual,
> cómo correr todo localmente, cómo verificar que cumple los ASRs, y dónde
> tocar para extender el trabajo.

Última actualización: **2026-05-07**

---

## 1. Qué es este proyecto

Es un monolito Django que **evidencia dos ASRs** (Architecturally Significant
Requirements) del Sprint 3, con tácticas implementadas y experimentos que
las verifican.

### ASR de Disponibilidad — dos categorías

**Categoría 01 — Detectar fallos:**

| Táctica | Implementación |
|---|---|
| Monitoreo (Ping/Echo) | `GET /api/monitor-servicios/health/` responde `{status: UP}` para que cualquier supervisor pueda pingear. |
| Heartbeats | `HeartbeatSender` (thread daemon en [generador_reportes/heartbeat.py](generador_reportes/heartbeat.py)) emite cada 200 ms a `monitor_servicios.Heartbeat`. |

**Categoría 02 — Reaccionar al fallo:**

| Táctica | Implementación |
|---|---|
| Fallar con gracia (graceful degradation) | Cuando una fuente cae, los `LookupError` de [`generador_reportes/services.py`](generador_reportes/services.py) se traducen a secciones `null` en el reporte combinado en lugar de propagar 5xx al cliente. |

### ASR de Seguridad

| Táctica | Implementación |
|---|---|
| Rate Limiting / detección DoS | Middleware [`monitor_trafico/middleware.py`](monitor_trafico/middleware.py) bloquea con HTTP 403 IPs que excedan 100 reqs / 60 s. |

> **Nota arquitectónica:** un experimento previo planteaba *Active Redundancy*
> con dos "instancias" del Generador de Reportes en el mismo proceso y un
> mecanismo de `kill` simulado. Esto fue rechazado por el equipo: en un
> monolito mono-proceso ambas instancias comparten dominio de fallo, así
> que NO es redundancia real. Migramos a las tácticas listadas arriba, que
> sí se pueden demostrar con rigor en este setup.

Para evidenciarlas el repo incluye:
- 5 apps Django (Recolector, Generador de Reportes, API Gateway, Monitor de
  Servicios, Monitor de Tráfico).
- 3 scripts en [`experiments/`](experiments/) que miden cada táctica.
- 1 suite de tests de integración del Recolector en
  [`tests/test_recolector.py`](tests/test_recolector.py).

---

## 2. Estado actual

### Lo que funciona

- Django arranca limpio (`manage.py check` → 0 issues).
- Migraciones consistentes con los modelos
  (`makemigrations --dry-run` → "No changes detected").
- Reporte combinado **degrada limpio** si Mongo está caído (timeout 500 ms,
  cortocircuito tras primer fallo de Mongo, secciones `s3`/`ec2` quedan en
  `null`, HTTP 200).
- Rate limiting con bloqueo automático y endpoint de unblock manual.
- Suite de tests del Recolector con 71 checks.

### Métricas medidas (2026-05-07, runserver local con SQLite + Mongo inalcanzable)

| Test | Resultado | Métrica |
|---|---|---|
| Disp 01 — Ping/Echo `/health/` | PASS | 23.8 ms (< 200 ms presupuesto) |
| Disp 01 — Heartbeats avanzan en tiempo real | PASS | `last_seen` avanza > 600 ms en ventana de 600 ms |
| Disp 02 — Degradación: HTTP 200 con Mongo caído | PASS | 545 ms (< 1500 ms) |
| Disp 02 — Degradación: Postgres preservado | PASS | 3 records de consumption + governance |
| Disp 02 — Degradación: Mongo en `null` | PASS | s3=null, ec2=null |
| Seg — bloqueo de IP | PASS | request #101 con umbral 100 |
| Seg — unblock | PASS | siguiente GET vuelve a 200 |
| `tests/test_recolector.py` | 63/71 | 8 fails por Mongo inalcanzable (esperado) |

> Nota: con el servidor AWS de Felipe (`100.31.110.6`) accesible y Mongo arriba,
> los 8 fails del Recolector pasarían a 71/71. El experimento de degradación
> controlada por su naturaleza requiere Mongo CAÍDO para evidenciarse.

### Lo que falta o se puede extender

- **Rate limiting más fino**: hoy es por IP global. Podría ser por IP+endpoint,
  o usar token bucket en lugar de ventana fija.
- **Reporte combinado**: la lógica de `_combine` en
  [generador_reportes/services.py](generador_reportes/services.py) hoy genera
  3 highlights básicos. Se puede enriquecer con joins más sofisticados.
- **Tests para los demás componentes**: hoy solo tenemos tests del Recolector.
  Faltan tests de los endpoints del Gateway, Monitor de Tráfico, Monitor de
  Servicios.
- **Validación de contratos**: no hay validación formal de schemas (e.g. con
  `pydantic` o DRF serializers). Los views devuelven dicts arbitrarios.

---

## 3. Setup paso a paso

Tienes **dos opciones de setup** según el escenario:

- **Opción A:** apuntar al servidor AWS de Felipe (datos reales, Mongo, Postgres).
- **Opción B:** correr todo en local con SQLite y sin Mongo (modo testing).

> **Para evidenciar la degradación controlada localmente, usa la Opción B.**
> Si Mongo está accesible, no hay degradación que mostrar.

### 3.0. Bootstrap común (una sola vez)

```bash
# Clonar
git clone <repo-url>
cd Experimentos-Sprint-3

# Instalar uv (gestor de paquetes rápido)
# Mac/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Instalar dependencias
uv sync
```

Si prefieres `pip` clásico: `pip install -r requirements.txt`.

---

### 3.A. Opción A — Apuntar al servidor AWS

Esta opción usa la base de datos compartida del equipo en `100.31.110.6`.

#### Pre-requisitos

- Estar en una red que pueda alcanzar `100.31.110.6:5432` (Postgres) y `:27017` (Mongo).
- Si la IP cambió, pedir la nueva en el chat del equipo y editarla en
  [settings.py](settings.py) (`DATABASES['default']['HOST']` y `MONGO_URI`).

#### Pasos

```bash
# Migraciones (solo necesario la primera vez por equipo)
uv run python manage.py migrate

# Seed completo (Postgres + Mongo)
uv run python data-faker/seed_data.py

# Server
uv run python manage.py runserver
```

Si `migrate` reporta `relation already exists`:

```bash
uv run python manage.py migrate --fake
```

#### Probar que funcionó

```bash
# Healthcheck
curl http://127.0.0.1:8000/api/monitor-servicios/health/

# Reporte real
curl "http://127.0.0.1:8000/api/gateway/reportes/?business_id=11111111-1111-1111-1111-111111111111"
```

---

### 3.B. Opción B — Local sin AWS (modo testing)

Esta opción es la que se usa para correr la suite de tests cuando AWS está
caído o no se tiene VPN. Usa SQLite en archivo y Mongo "fail-fast" — el
Mongo configurado apunta a `127.0.0.1:27017` que normalmente está vacío,
así que el sistema **degrada genuinamente** (no se simula nada).

Los archivos clave que la habilitan:
- [`settings_test.py`](settings_test.py) — hereda de `settings.py` y
  sobrescribe DBs.
- [`experiments/_seed_postgres_only.py`](experiments/_seed_postgres_only.py)
  — seed minimalista sin Mongo.

#### Pasos

```bash
# 1. Limpia DB de corridas anteriores
rm -f db_test.sqlite3

# 2. Migraciones contra SQLite
DJANGO_SETTINGS_MODULE=settings_test uv run python manage.py migrate

# 3. Seed de Postgres (4 empresas con UUIDs predecibles)
uv run python experiments/_seed_postgres_only.py

# 4. Server (en una terminal aparte, mantenerlo abierto)
DJANGO_SETTINGS_MODULE=settings_test \
    uv run python manage.py runserver 127.0.0.1:8000 --noreload
```

#### Variables Windows (PowerShell)

En PowerShell el `VAR=valor cmd` no funciona; tienes que usar:

```powershell
$env:DJANGO_SETTINGS_MODULE="settings_test"
uv run python manage.py migrate
uv run python manage.py runserver 127.0.0.1:8000 --noreload
```

---

## 4. Cómo correr los experimentos / tests

> **Importante en Windows:** la consola por default no soporta los
> caracteres Unicode (─, ✅, etc.) que imprimen los scripts. Prefija
> los comandos con `PYTHONIOENCODING=utf-8` (PowerShell:
> `$env:PYTHONIOENCODING="utf-8"`).

Con el server arriba, en otra terminal:

### Tests de integración del Recolector

```bash
PYTHONIOENCODING=utf-8 uv run python tests/test_recolector.py
PYTHONIOENCODING=utf-8 uv run python tests/test_recolector.py -v   # verbose
```

Imprime un resumen `N/71 tests pasaron`. Si estás en modo testing
(Opción B), espera ~63/71: los 8 fails de S3/EC2 son por Mongo inalcanzable
(comportamiento correcto del sistema, no un bug).

### Disponibilidad 01 — Monitoreo (Ping/Echo) + Heartbeats

```bash
PYTHONIOENCODING=utf-8 uv run python experiments/measure_heartbeat_monitoring.py
```

Verifica las dos tácticas de la categoría 01 sin tocar nada (solo lectura):

1. **Ping/Echo:** `GET /api/monitor-servicios/health/` responde 200 con
   `{status: UP}` en menos de 200 ms.
2. **Heartbeats vivos:** `GET /api/monitor-servicios/monitor/status/` lista
   ambas instancias del Generador de Reportes con `is_alive: true`.
3. **Heartbeats avanzan:** toma `last_seen` en T1, espera 600 ms, toma
   `last_seen` en T2, verifica que avanzó. Esto demuestra que el thread
   emisor `HeartbeatSender` está vivo y emitiendo (no son heartbeats
   fósiles de una corrida anterior).

Variables de entorno (opcionales):
- `BASE_URL`                  (default `http://127.0.0.1:8000`)
- `PING_BUDGET_MS`            (default `200`)
- `HEARTBEAT_OBSERVATION_S`   (default `0.6`)

### Disponibilidad 02 — Fallar con gracia (Degradación Controlada)

```bash
PYTHONIOENCODING=utf-8 \
EXPERIMENT_BUSINESS_ID=11111111-1111-1111-1111-111111111111 \
uv run python experiments/measure_graceful_degradation.py
```

Hace `GET /api/gateway/reportes/?business_id=<UUID>` con Mongo no
accesible (pre-condición), y verifica:

- HTTP **200** (no 5xx) → el sistema NO se cae.
- `report.postgres.consumption` es lista no-vacía → datos críticos preservados.
- `report.postgres.governance` presente → datos críticos preservados.
- `report.mongo.s3 == null` y `report.mongo.ec2 == null` → degradación
  visible y honesta (no se inventa data).
- `total_latency_ms < 1500` → la degradación NO se cuelga 30 s
  (default de pymongo).

Variables de entorno (opcionales):
- `BASE_URL`                (default `http://127.0.0.1:8000`)
- `EXPERIMENT_BUSINESS_ID`  (default `11111111-1111-1111-1111-111111111111`)
- `TIMEOUT_MS`              (default `1500`)

> **Pre-condición crítica:** el experimento exige que Mongo **NO** esté
> accesible. Si Mongo responde, el script **falla a propósito** porque
> entonces no hay degradación que evidenciar. En modo TEST esto se
> garantiza porque `settings_test.py` apunta a `127.0.0.1:27017` que
> normalmente está vacío.

### ASR-Seg — Rate Limiting

```bash
PYTHONIOENCODING=utf-8 uv run python experiments/measure_security_ratelimit.py
```

Bombardea `/api/monitor-servicios/health/` con `X-Forwarded-For: 10.0.0.99`,
verifica transición 200 → 403 al sobrepasar el umbral, presencia en
`/blocked/`, y que `POST /unblock/` libera la IP.

Variables (opcionales): `ATTACKER_IP`, `TOTAL_REQUESTS`, `THRESHOLD`.

### Salida de los scripts

Cada script imprime una línea JSON por evento:

```json
{"event": "START", ...}
{"event": "REPORT_RESPONSE", "http": 200, "total_latency_ms": 545.0, ...}
{"event": "CRITICAL_DATA_PRESERVED", "consumption_records": 3, ...}
{"event": "GRACEFUL_NULL_SECTIONS", "mongo.s3": null, "mongo.ec2": null}
{"event": "PASS", "reason": "Degradación controlada cumple — ..."}
```

Exit code 0 = PASS, 1 = FAIL. Listo para CI.

---

## 5. Mapa del repo

```
Experimentos-Sprint-3/
├── manage.py                       # Punto de entrada Django (apunta a 'settings')
├── settings.py                     # Settings PROD (apunta a AWS 100.31.110.6)
├── settings_test.py                # Settings LOCAL (SQLite + Mongo localhost)
├── urls.py                         # ROOT_URLCONF
├── wsgi.py                         # WSGI app
├── pyproject.toml + uv.lock        # Dependencias gestionadas por uv
├── requirements.txt                # Alternativa pip
├── README.md                       # Vista general + endpoints
├── GUIA.md                         # ESTE archivo
│
├── api_gateway/                    # Entrada principal
│   ├── services.py                 # GatewayService.route_report_request
│   └── views.py                    # GatewayReportView, GatewayStatusView
│
├── monitor_servicios/              # Health-check / Heartbeats opcionales
│   ├── services.py                 # ServiceMonitorService
│   ├── models.py                   # ServiceRegistration, Heartbeat
│   └── views.py                    # POST /heartbeat/, GET /status/
│
├── monitor_trafico/                # Rate Limiting / DoS
│   ├── middleware.py               # TrafficMonitorMiddleware (en cada request)
│   ├── services.py                 # log_request, evaluate_ip, unblock_ip
│   └── views.py                    # /stats/, /blocked/, /unblock/<ip>/
│
├── generador_reportes/             # Combina datos PG + Mongo (degrada limpio)
│   ├── services.py                 # ReportGeneratorService.generate_full_inventory_report
│   ├── heartbeat.py                # HeartbeatSender (thread daemon, opcional)
│   ├── apps.py                     # Arranca el thread en ready()
│   └── views.py                    # GET /generar/?business_id=...
│
├── recolector_inventarios/         # Acceso a datos
│   ├── connectors.py               # PostgresConnector, MongoConnector (lazy + timeouts cortos)
│   ├── services.py                 # USDConsumption, CloudGovernance, S3Usage, EC2Usage
│   ├── models.py                   # Business, ConsumptionSummary, CloudGovernance
│   └── views.py                    # 4 endpoints REST
│
├── data-faker/
│   └── seed_data.py                # Seed completo (PG + Mongo) — usa Django ORM
│
├── experiments/                    # Scripts de medición de ASRs
│   ├── _common.py                  # Helpers (BASE_URL, emit, ok, fail)
│   ├── _seed_postgres_only.py      # Seed solo PG para modo testing
│   ├── measure_heartbeat_monitoring.py    # Disp 01: Ping/Echo + Heartbeats
│   ├── measure_graceful_degradation.py    # Disp 02: Fallar con gracia
│   └── measure_security_ratelimit.py      # Seg: Rate Limiting
│
├── tests/
│   └── test_recolector.py          # 71 tests de integración HTTP
│
└── setups/
    ├── setup-dbs.sh                # Instala Postgres 16 + Mongo 8 en Ubuntu 24.04
    └── setup-credentials.sh        # Crea bite_db, bite_telemetry y usuarios
```

---

## 6. Decisiones de diseño tomadas

Si te toca extender o modificar, ten en cuenta:

### Por qué estas tácticas y NO Active Redundancy

Un experimento previo planteaba *Active Redundancy* simulando dos
"instancias" del Generador de Reportes en el mismo proceso Python con un
mecanismo de `kill_instance()` que solo agregaba el nombre a un set en
memoria. La crítica del equipo (correcta): en un monolito mono-proceso
ambas "instancias" comparten dominio de fallo (mismo PID, misma GIL,
misma DB connection pool, mismo OS), así que NO son redundantes — si
algo realmente cae, caen juntas.

Migramos a:

- **Detección** vía Ping/Echo + Heartbeats — son tácticas de monitoreo,
  no de redundancia, y se demuestran con rigor con un Mongo realmente
  caído (no simulado) y un thread emisor real.
- **Reacción** vía degradación controlada — el comportamiento ya está
  implementado: cada `LookupError` en [generador_reportes/services.py](generador_reportes/services.py)
  se convierte en una sección `null` en lugar de un 5xx.

Los endpoints `experimento/matar/`, `experimento/revivir/` y
`experimento/medir/` **fueron eliminados** porque solo simulaban el
fallo, no lo causaban.

### Heartbeat con intervalo 0.2 s, umbral 0.8 s

[generador_reportes/heartbeat.py](generador_reportes/heartbeat.py) +
[settings.py](settings.py).
El `HeartbeatSender` arranca con el server (vía
[generador_reportes/apps.py](generador_reportes/apps.py)) como thread
daemon que cada 200 ms inserta un `Heartbeat` por instancia lógica en
`monitor_servicios`. El monitor considera viva una instancia si su
último heartbeat es más reciente que `expected_interval_seconds = 0.8 s`
(intervalo × 4). Esto da una garantía matemática: el peor caso de
detección es 0.8 s, así el `is_alive=true` reportado por el monitor
nunca lleva más de 800 ms de retraso respecto a la realidad.

### Mongo lazy + timeouts cortos (500 ms)

[recolector_inventarios/connectors.py](recolector_inventarios/connectors.py).
Razón: el default de `pymongo.MongoClient` es 30 s. Eso violaría la
garantía de "latencia acotada" del ASR de disponibilidad. Con
`serverSelectionTimeoutMS=500ms` y cortocircuito en
[`ReportGeneratorService._fetch_from_mongo`](generador_reportes/services.py)
(si la primera llamada falla por error de conexión, no intentamos la
segunda) bajamos de ~2266 ms a ~545 ms con Mongo caído.

### `routing_decision_ms` vs `report_generation_ms`

[api_gateway/services.py](api_gateway/services.py) y
[api_gateway/views.py](api_gateway/views.py).
El endpoint expone los dos tiempos por separado en la respuesta:
`routing_decision_ms` mide la lógica del Gateway (escoger el destino,
~2-5 ms); `report_generation_ms` mide la generación del reporte
(incluye llamadas a DB, puede ser 500 ms si Mongo está caído).
Tener los dos separados es útil para diagnosticar dónde está la
latencia cuando algo se desvía del SLA.

### `MongoConnector.col` es lazy

Si `MongoConnector` abriera socket en `__init__`, importar
[api_gateway/views.py](api_gateway/views.py) (que crea
`_gateway = GatewayService()` a nivel de módulo) bloquearía 30 s al
arrancar el server si Mongo está caído. Con la propiedad lazy, no se
intenta conectar hasta que llega un request que necesita datos de Mongo.

### `CloudGovernance.id_business` es el primary key

[recolector_inventarios/models.py](recolector_inventarios/models.py:65).
Razón: relación 1:1 con `Business`. Tener un `id` BigAuto separado era
columna redundante.

### `LookupError` vs `ValueError` en los services del Recolector

Un `ValueError` significa "el business_id no existe — el cliente está
preguntando por algo inválido" → 404 a nivel HTTP, **propaga** desde
el Generador de Reportes.

Un `LookupError` significa "el business existe pero esta sección no
tiene datos (o la DB que la tiene cayó)" → la sección queda como `null`
en el reporte combinado, NO se propaga al cliente como error.

Esta distinción es la base de la degradación controlada.

---

## 7. Troubleshooting

### `ModuleNotFoundError: No module named 'psycopg2'`

Estás corriendo Python global en lugar del entorno de `uv`.
**Fix**: prefijo todos los comandos con `uv run python ...`.

### `relation "..." does not exist`

Migraciones no aplicadas.
**Fix**: `uv run python manage.py migrate`. Si la DB ya tenía las tablas
de antes y solo te faltan algunas, prueba `--fake-initial`.

### `Connection refused` o `timed out` al server AWS

La IP de Felipe (`100.31.110.6`) cambió o tu firewall bloquea el puerto.
**Fix**: pide la IP nueva en el chat del equipo y edita
[settings.py](settings.py). Si estás de viaje y no puedes salir a AWS,
usa la **Opción B** (modo testing).

### El experimento de degradación falla con `Mongo respondió`

Es la pre-condición que NO se cumple — el Mongo configurado en
`settings_test.py` SÍ está accesible. Para evidenciar degradación
controlada Mongo debe estar caído.
**Fix**: edita `settings_test.py` y apunta `MONGO_URI` a un puerto
genuinamente vacío (ej. `mongodb://127.0.0.1:1/`), o detén el Mongo
local.

### `UnicodeEncodeError: 'charmap' codec can't encode...`

Tu consola Windows usa cp1252. Los scripts usan UTF-8.
**Fix**: `PYTHONIOENCODING=utf-8` antes del comando.

### El reporte tarda 30 segundos cuando Mongo está caído

Te quedaste con la versión vieja de
[recolector_inventarios/connectors.py](recolector_inventarios/connectors.py).
**Fix**: `git pull` para traer el commit `3f2f81c` (timeout 500 ms).

### `IntegrityError: UNIQUE constraint failed: businesses.nit`

El seed se corrió dos veces sin limpiar la DB.
**Fix**: `rm db_test.sqlite3` y volver a migrar+seed (Opción B), o
`Business.objects.all().delete()` desde `manage.py shell` (Opción A —
**ojo**: borrarías datos del equipo).

---

## 8. Cómo continuar el trabajo

### Cómo agregar un test nuevo

Para un test del Recolector, edita
[tests/test_recolector.py](tests/test_recolector.py) y añade una nueva
sección con `section()` y `check()`. El runner es minimalista a propósito
(no usa pytest) para no añadir dependencias.

Para un test de un ASR nuevo, copia un `experiments/measure_*.py` como
template. Usa `experiments/_common.py` (`emit`, `ok`, `fail`).

### Convenciones de commit

Los commits siguen `<tipo>: <descripción corta>`:
- `feat:` nueva funcionalidad
- `fix:` bug fix
- `docs:` solo documentación
- `test:` solo tests
- `refactor:` cambio sin cambio funcional

Co-authoring si lo armaste con un asistente:

```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## 9. Contactos / referencias

- **Felipe (fgutep@gmail.com):** dueño del setup AWS y del Recolector.
  Avísale antes de reiniciar Postgres remoto.
- **Alejandro (alejandro.cruz@interkont.co):** estructura Django + ASRs +
  scripts de experimento.

Para cualquier duda, primero revisa los logs del servidor:

```bash
DJANGO_SETTINGS_MODULE=settings_test uv run python manage.py runserver 127.0.0.1:8000 --noreload --verbosity=3
```
