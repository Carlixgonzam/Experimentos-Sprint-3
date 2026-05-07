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

# Guía de Inicio Rápido

## Descripción General

Las bases de datos PostgreSQL y MongoDB se encuentran desplegadas en AWS con datos de prueba. El proyecto utiliza `uv` como gestor de paquetes para simplificar la configuración del entorno.

## Gestor de Paquetes: uv

El proyecto utiliza `uv`, un gestor de paquetes de alto rendimiento escrito en Rust, en lugar del flujo tradicional de `pip` y entornos virtuales.

### Instalación de uv

Si `uv` no está instalado, ejecutar:

- **Mac/Linux**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Windows**: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

### Uso de uv

Todos los comandos de Python deben ejecutarse con el prefijo `uv run`:

```bash
# Incorrecto
python manage.py runserver

# Correcto
uv run python manage.py runserver
```

## Configuración de Bases de Datos

Las instancias de PostgreSQL y MongoDB están alojadas en AWS. Las credenciales de conexión deben configurarse en `settings.py` o en el archivo `.env`.

**Nota**: La dirección IP del servidor AWS (ej. `100.31.110.6`) puede cambiar. Si se produce un error de timeout o conexión rechazada, se debe solicitar la dirección IP actualizada.

## Procedimiento de Inicio

Ejecutar los siguientes pasos después de clonar el repositorio:

### 1. Instalar dependencias

```bash
uv sync
```

### 2. Ejecutar migraciones

```bash
uv run python manage.py migrate
```

Si aparece el mensaje `relation already exists`, utilizar la opción `--fake` en la migración correspondiente.

### 3. Iniciar el servidor

```bash
uv run python manage.py runserver
```

## Solución de Problemas

| Error | Causa | Solución |
|-------|-------|----------|
| `ModuleNotFoundError: No module named 'psycopg2'` | Python global en lugar del entorno de `uv` | Usar `uv run python ...` |
| `relation "monitor_servicios_serviceregistration" does not exist` | Las migraciones no se ejecutaron antes de iniciar el servidor | Detener el servidor, ejecutar `uv run python manage.py migrate` y reiniciar |
| `Connection refused` | Dirección IP de AWS ha cambiado o el firewall local bloquea los puertos 5432/27017 | Solicitar la dirección IP actualizada; verificar configuración del firewall |
| `ModuleNotFoundError: No module named 'wsgi'` | Ruta incorrecta en `WSGI_APPLICATION` en `settings.py` | Verificar que `WSGI_APPLICATION = 'core.wsgi.application'` coincida con la estructura del proyecto |