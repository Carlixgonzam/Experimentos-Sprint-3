# Guía del proyecto — Experimentos Sprint 3

> Documento de onboarding para miembros del equipo. Cubre el estado actual,
> cómo correr todo localmente, cómo verificar que cumple los ASRs, y dónde
> tocar para extender el trabajo.

Última actualización: **2026-05-07**

---

## 1. Qué es este proyecto

Es un monolito Django que **evidencia tres ASRs** (Architecturally Significant
Requirements) del Sprint 3:

| ID | Tipo | Requisito | Táctica usada |
|---|---|---|---|
| ASR1 | Disponibilidad | Detectar caída de instancia en **< 1 s** | Heartbeat (Ping/Echo) |
| ASR2 | Disponibilidad | Hacer failover a nodo sano con decisión de routing **< 100 ms** | Active Redundancy / first-healthy |
| ASR-Seg | Seguridad | Bloquear con HTTP 403 IPs que excedan **100 reqs / 60 s** | Rate Limiting / detección DoS |

Para evidenciarlo el repo incluye:
- 5 apps Django (Recolector, Generador de Reportes, API Gateway, Monitor de
  Servicios, Monitor de Tráfico).
- 3 scripts en [`experiments/`](experiments/) que miden cada ASR.
- 1 suite de tests de integración del Recolector en [`tests/test_recolector.py`](tests/test_recolector.py).

---

## 2. Estado actual

### Lo que funciona

✅ Django arranca limpio (`manage.py check` → 0 issues).
✅ Migraciones consistentes con los modelos (`makemigrations --dry-run` → "No changes detected").
✅ Heartbeats corriendo en thread daemon (200 ms intervalo, umbral 800 ms).
✅ Routing con first-healthy — el Gateway descarta instancias caídas.
✅ Rate limiting con bloqueo automático y endpoint de unblock manual.
✅ Reporte combinado **degrada limpio** si Mongo está caído (timeout 500 ms,
   cortocircuito tras primer fallo de Mongo, secciones `s3`/`ec2` quedan en `null`).
✅ Suite de tests del Recolector con 71 checks.

### Métricas medidas (2026-05-07, runserver local con SQLite + Mongo inalcanzable)

| Test | Resultado | Métrica |
|---|---|---|
| ASR1 — detección | PASS | 779.9 ms (< 1000 ms) |
| ASR2 — decisión de routing | PASS | 2.66 ms (< 100 ms) |
| ASR2 — total cliente | PASS | 570 ms (< 1500 ms) |
| ASR-Seg — bloqueo | PASS | request #101 con umbral 100 |
| ASR-Seg — unblock | PASS | siguiente GET vuelve a 200 |
| `tests/test_recolector.py` | 63/71 | 8 fails por Mongo inalcanzable (esperado) |

> Nota: con el servidor AWS de Felipe (`100.31.110.6`) accesible y datos completos,
> los 71 tests del Recolector deberían pasar todos.

### Lo que falta o se puede extender

- **Estrategia de routing**: hoy es first-healthy. Se podría extender a round-robin
  ponderado o least-connections en [api_gateway/services.py](api_gateway/services.py).
- **Rate limiting más fino**: hoy es por IP global. Podría ser por IP+endpoint,
  o usar token bucket en lugar de ventana fija.
- **Reporte combinado**: la lógica de `_combine` en
  [generador_reportes/services.py](generador_reportes/services.py) hoy genera
  3 highlights básicos. Se puede enriquecer con joins más sofisticados.
- **Tests para los demás componentes**: hoy solo tenemos tests del Recolector.
  Faltan tests de los endpoints del Gateway, Monitor de Tráfico, Monitor de Servicios.
- **Validación de contratos**: no hay validación formal de schemas (e.g. con
  `pydantic` o DRF serializers). Los views devuelven dicts arbitrarios.

---

## 3. Setup paso a paso

Tienes **dos opciones de setup** según el escenario:

- **Opción A:** apuntar al servidor AWS de Felipe (datos reales, Mongo, Postgres).
- **Opción B:** correr todo en local con SQLite y sin Mongo (modo testing).

Las dos comparten el bootstrap de Python.

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
caído o no se tiene VPN. Usa SQLite en archivo y Mongo "fail-fast" (el
reporte combinado degrada y devuelve `mongo: null`).

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

### Tests de integración del Recolector (Felipe)

```bash
PYTHONIOENCODING=utf-8 uv run python tests/test_recolector.py
PYTHONIOENCODING=utf-8 uv run python tests/test_recolector.py -v   # verbose
```

Imprime un resumen `N/71 tests pasaron`. Si estás en modo testing
(Opción B), espera ~63/71: los 8 fails de S3/EC2 son por Mongo inalcanzable
(comportamiento correcto del sistema, no un bug).

### ASR1 — Detección de caída

```bash
PYTHONIOENCODING=utf-8 uv run python experiments/measure_asr1_detection.py
```

Mata `generador_reportes_1`, hace polling cada 50 ms a `/medir/` hasta
detectar `is_alive=false`. PASS si `seconds_since_kill < 1.0`.

Variables de entorno (opcionales):
- `BASE_URL`        (default `http://127.0.0.1:8000`)
- `INSTANCE`        (default `generador_reportes_1`)
- `POLL_MS`         (default `50`)
- `TIMEOUT_S`       (default `5`)

### ASR2 — Failover

```bash
PYTHONIOENCODING=utf-8 \
EXPERIMENT_BUSINESS_ID=11111111-1111-1111-1111-111111111111 \
uv run python experiments/measure_asr2_failover.py
```

Mata el nodo 1, espera detección, y cronometra
`GET /api/gateway/reportes/?business_id=<UUID>`. Verifica que:
- `routed_to == generador_reportes_2`
- `routing_decision_ms < 100` (decisión del Gateway)
- `total_latency_ms_client < 1500` (extremo a extremo)

> **Por qué se separan `routing_decision_ms` y `report_generation_ms`:**
> el SLA del Gateway es sobre la **decisión** de a qué nodo enrutar; el
> tiempo de generar el reporte depende de Postgres y Mongo y NO es parte
> del SLA. Si Mongo se cae, `report_generation_ms` ≈ 500 ms (timeout
> + cortocircuito) pero `routing_decision_ms` se mantiene < 5 ms.

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
{"event": "PRECONDITION_OK", ...}
{"event": "DETECTED", "seconds_since_kill": 0.78, ...}
{"event": "PASS", "reason": "ASR1 cumplido — detección < 1 s", ...}
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
├── api_gateway/                    # Active Redundancy / failover
│   ├── services.py                 # GatewayService.route_report_request
│   └── views.py                    # Endpoints del experimento ASR
│
├── monitor_servicios/              # Heartbeat / Ping-Echo
│   ├── services.py                 # ServiceMonitorService
│   ├── models.py                   # ServiceRegistration, Heartbeat
│   └── views.py                    # POST /heartbeat/, GET /status/
│
├── monitor_trafico/                # Rate Limiting / DoS
│   ├── middleware.py               # TrafficMonitorMiddleware (en cada request)
│   ├── services.py                 # log_request, evaluate_ip, unblock_ip
│   └── views.py                    # /stats/, /blocked/, /unblock/<ip>/
│
├── generador_reportes/             # Combina datos PG + Mongo
│   ├── services.py                 # ReportGeneratorService.generate_full_inventory_report
│   ├── heartbeat.py                # HeartbeatSender (thread daemon)
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
│   ├── measure_asr1_detection.py
│   ├── measure_asr2_failover.py
│   └── measure_security_ratelimit.py
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

### Heartbeat con intervalo 0.2 s, umbral 0.8 s

Definidos en [settings.py](settings.py) y aplicados en
[generador_reportes/heartbeat.py](generador_reportes/heartbeat.py).
Razón: peor caso de detección = `expected_interval` (justo después de un
heartbeat OK, esperar el siguiente que nunca llega). 0.8 s < 1 s →
ASR1 cumplido por construcción. No bajes esto sin medir CPU; cada
heartbeat es un INSERT en Postgres.

### First-healthy (no round-robin)

Implementado en
[`GatewayService.route_report_request`](api_gateway/services.py).
Razón: simplifica la verificación determinista del experimento ASR2.
El siguiente request tras el `kill` siempre va al mismo nodo sano. Si
quisieras round-robin, agrégalo como una `RoutingStrategy` separada.

### Mongo lazy + timeouts cortos (500 ms)

[recolector_inventarios/connectors.py](recolector_inventarios/connectors.py).
Razón: el default de `pymongo.MongoClient` es 30 s — eso rompía el ASR2
cuando Mongo no respondía. Con 500 ms de `serverSelectionTimeoutMS`
y cortocircuito en
[`ReportGeneratorService._fetch_from_mongo`](generador_reportes/services.py)
(si la primera llamada falla, no intentamos la segunda) bajamos de
~2266 ms a ~648 ms con Mongo caído.

### `routing_decision_ms` separado de `report_generation_ms`

[api_gateway/services.py](api_gateway/services.py) y
[api_gateway/views.py](api_gateway/views.py).
Razón: el SLA del Gateway es la **decisión de routing** (hace dos queries
locales). El tiempo de generar el reporte depende de DBs externas — eso
NO debe contar contra el ASR2.

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

### El experimento ASR1 falla con "No se detectó la caída"

El thread `HeartbeatSender` no está corriendo. Causas comunes:
1. Iniciaste el server con `--noreload` o `manage.py shell` (que están
   en la lista de comandos donde el thread NO arranca, mira
   [generador_reportes/apps.py](generador_reportes/apps.py)).
2. Usas Windows + PowerShell donde el SIGINT entre procesos es flaky.
   Reinicia el server limpio.

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
