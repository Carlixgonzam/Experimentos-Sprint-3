# Monolito Django — Arquitectura de Componentes

## Componentes

| App | Prefijo API | Responsabilidad |
|---|---|---|
| `monitor_trafico` | `/api/monitor-trafico/` | Registro de requests, detección de DoS, bloqueo de IPs |
| `monitor_servicios` | `/api/monitor-servicios/` | Heartbeats de servicios internos, detección de caídas |
| `generador_reportes` | `/api/generador-reportes/` | Combina datos de Postgres + Mongo en JSON para el frontend |
| `recolector_inventarios` | `/api/recolector/` | API abstracta sobre PostgreSQL y MongoDB |

## Estructura de cada app

```
<app>/
  models.py       # Modelos de Django (solo Postgres)
  services.py     # Lógica de negocio (NotImplementedError → implementar)
  views.py        # Vistas DRF (APIView)
  urls.py         # Rutas del componente
  connectors.py   # Solo en recolector_inventarios (bajo nivel DB)
  middleware.py   # Solo en monitor_trafico
```

## Dependencias entre componentes

```
generador_reportes
    └─> recolector_inventarios.services.PostgresCollector
    └─> recolector_inventarios.services.MongoCollector

monitor_trafico (middleware)
    └─> se ejecuta en CADA request antes de llegar a cualquier vista

monitor_servicios
    └─> los demás componentes llaman POST /api/monitor-servicios/heartbeat/
```

## Setup

```bash
pip install django djangorestframework pymongo psycopg2-binary
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

## Variables de entorno recomendadas

| Variable | Descripción |
|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django |
| `POSTGRES_DB / USER / PASSWORD / HOST / PORT` | Conexión Postgres |
| `MONGO_URI` | URI de MongoDB |
