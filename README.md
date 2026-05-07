# Experimentos Sprint 3 — Disponibilidad y Seguridad

Monolito Django (proyecto `core`) que evidencia dos ASRs:

- **ASR1 — Disponibilidad / Detección:** una instancia caída del Generador de
  Reportes es marcada como `is_alive=false` en **< 1 s** (táctica *Heartbeat*).
- **ASR2 — Disponibilidad / Recuperación:** tras la detección, el API Gateway
  enruta automáticamente al nodo sano restante en **< 1 s** (táctica
  *Active Redundancy*, estrategia *first-healthy*).
- **ASR-Seg — Seguridad / Rate Limiting:** el middleware de Monitor de Tráfico
  bloquea con HTTP 403 cualquier IP que exceda el umbral configurado en
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
├── manage.py
├── core/                      # proyecto Django (settings, urls, wsgi, asgi)
├── api_gateway/
├── generador_reportes/
├── monitor_servicios/
├── monitor_trafico/
├── recolector_inventarios/
├── data-faker/seed_data.py    # popular Postgres + Mongo con datos plausibles
├── experiments/
│   ├── measure_asr1_detection.py
│   ├── measure_asr2_failover.py
│   └── measure_security_ratelimit.py
├── setups/
│   ├── setup-dbs.sh           # instala Postgres 16 + Mongo 8 (Ubuntu 24.04)
│   └── setup-credentials.sh   # crea bite_db / bite_telemetry y usuarios
└── requirements.txt
```

## Setup (orden recomendado)

### 1. Bases de datos

En el servidor (o local Linux) ejecuta los scripts:

```bash
sudo ./setups/setup-dbs.sh
sudo ./setups/setup-credentials.sh
```

Eso crea:
- Postgres `bite_db` con usuario `bite_user`/`Bite_KISS_2026!`
- Mongo `bite_telemetry` con usuario `bite_mongo_user`/`Mongo_KISS_2026!`

Si trabajas local sin tocar `setup-credentials.sh`, exporta las variables que
[core/settings.py](core/settings.py) lee:

```bash
export POSTGRES_DB=bite_db
export POSTGRES_USER=bite_user
export POSTGRES_PASSWORD='Bite_KISS_2026!'
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432
export MONGO_URI='mongodb://127.0.0.1:27017/'
export MONGO_DB_NAME=bite_telemetry
```

### 2. Dependencias Python

```bash
pip install -r requirements.txt
```

### 3. Migraciones

```bash
python manage.py migrate
```

Esto crea las tablas de `recolector_inventarios`, `monitor_trafico`,
`monitor_servicios`, además de las propias de Django.

### 4. Datos de prueba

```bash
python data-faker/seed_data.py
```

Crea 4 empresas con UUIDs predecibles (ver lista al final del seed) más
50 aleatorias, con histórico financiero, gobernanza, y telemetría S3/EC2.

### 5. Servidor

```bash
python manage.py runserver
```

El hilo `HeartbeatSender` arranca automáticamente y comienza a emitir
heartbeats cada 200 ms por cada instancia lógica
(`generador_reportes_1`, `generador_reportes_2`).

## Ejecutar los experimentos

Con el servidor arriba y `seed_data.py` ejecutado, en otra terminal:

### ASR1 — Detección de fallo en < 1 s

```bash
python experiments/measure_asr1_detection.py
```

Sale con código 0 si la detección fue < 1 s e imprime cada evento como
JSON line. Variables de entorno útiles: `INSTANCE`, `POLL_MS`, `TIMEOUT_S`.

### ASR2 — Failover < 1.5 s, routing < 100 ms

```bash
python experiments/measure_asr2_failover.py
```

Mata `generador_reportes_1`, espera detección, y cronometra la respuesta del
Gateway al pedir un reporte real. Verifica que `routed_to ==
generador_reportes_2`.

### Seguridad — Rate Limiting

```bash
python experiments/measure_security_ratelimit.py
```

Bombardea `/api/monitor-servicios/health/` con la IP atacante (default
`10.0.0.99` vía `X-Forwarded-For`), confirma que se bloquea con 403, y
verifica que `POST /api/monitor-trafico/unblock/<ip>/` la libera.

> Cada script imprime `{"event": "PASS", ...}` en éxito o `{"event": "FAIL", ...}`
> con el motivo del fallo. Idempotente: revive instancias y desbloquea IPs al
> terminar.

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

Definidos en [core/settings.py](core/settings.py):

| Parámetro | Valor | Significado |
|---|---|---|
| `HEARTBEAT_INTERVAL_SECONDS` | `0.2` | Frecuencia de emisión de heartbeats. |
| `expected_interval_seconds` | `0.8` | Calculado como intervalo × 4 al registrar la instancia. Umbral de detección. |
| `REPORT_GENERATOR_INSTANCES` | `['generador_reportes_1', 'generador_reportes_2']` | Instancias lógicas que participan en el experimento. |

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
  pocas requests (<10) por lo que no disparan el rate limiting (umbral 100/60s).
  Si fueras a ejecutar muchas iteraciones consecutivas usa
  `POST /api/monitor-trafico/unblock/127.0.0.1/` entre corridas.
- **Conexión Mongo lazy:** `MongoConnector` no abre socket hasta la primera
  consulta. Esto permite que el monolito arranque (y los endpoints de
  heartbeat funcionen) aunque Mongo no esté disponible.
