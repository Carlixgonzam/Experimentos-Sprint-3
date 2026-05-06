# Documentación: recolector_inventarios

## 1. Descripción General

El módulo **recolector_inventarios** actúa como la capa de servicios de datos para la plataforma de gestión de nube. Su objetivo principal es exponer métricas de consumo y uso de recursos de infraestructura mediante una arquitectura de persistencia políglota, combinando la consistencia de PostgreSQL para datos financieros y la flexibilidad de MongoDB para telemetría técnica.

---

## 2. Arquitectura de Datos

Se implementa una separación de responsabilidades:

### A. Capa Relacional (PostgreSQL)

Gestiona la **“Verdad Operativa”** y la gobernanza.

* **Tablas**: `businesses`, `consumption_summary`, `cloud_governance`
* **Propósito**: Auditoría financiera, control de acceso y gestión de metadatos de clientes de BITE.co.

### B. Capa Documental (MongoDB)

Gestiona la **“Telemetría Cruda”** de proveedores como AWS.

* **Colección**: `cloud_telemetry`
* **Propósito**: Almacenar esquemas variables de recursos como S3 y EC2, permitiendo identificar patrones de desperdicio sin modificar el código base.

---

## 3. Endpoints y Flujo de Datos

| Endpoint                  | Fuente de Datos | Lógica de Enriquecimiento                                       |
| ------------------------- | --------------- | --------------------------------------------------------------- |
| `GET .../USDConsumption`  | PostgreSQL      | Filtrado por `month` vía query param para reportes mensuales    |
| `GET .../CloudGovernance` | PostgreSQL      | Validación de tags obligatorios y políticas de cumplimiento     |
| `GET .../S3Usage`         | MongoDB         | Cálculo de `waste_percentage` por cada bucket identificado      |
| `GET .../EC2Usage`        | MongoDB         | Evaluación de `is_underutilized` basado en umbral de CPU (<20%) |

---

## 4. Decisiones de Diseño (KISS & Clean Architecture)

### Validación de Integridad (Join Key)

Todo servicio inicia validando el `business_id` contra PostgreSQL. Esto garantiza que no se procesen datos de telemetría de empresas no registradas o accesos no autorizados.

### Procesamiento en Capa de Servicio

La lógica pesada (como el cálculo de sugerencias de optimización) reside en los *Services*. Si el volumen de datos de telemetría excede el umbral de rendimiento, el sistema puede delegar la tarea a procesos en segundo plano.

### Optimización de Respuesta

Se utiliza la proyección `{"_id": 0}` en consultas de MongoDB para:

* Reducir el payload
* Evitar errores de serialización de `ObjectId`
* Optimizar el tiempo de respuesta hacia el generador de reportes

### Independencia de Nube

El uso de documentos JSON en la telemetría permite extraer información de cualquier nube (AWS/GCP) sin requerir migraciones de esquema en la base de datos relacional.

---

## 5. Guía de Despliegue Rápido

### Migraciones SQL

Ejecutar:

```bash
python manage.py migrate
```

Esto aplicará el archivo `0001_initial.py` en la base de datos relacional.

### Conexión NoSQL

Asegurar que la URI de MongoDB apunte a la base de datos de telemetría con la colección `cloud_telemetry` pre-poblada.

### Configuración

Los umbrales de subutilización (por ejemplo, 20% de CPU) se encuentran definidos como constantes en `EC2UsageService`, facilitando ajustes según la madurez tecnológica del cliente.

---

## Nota

Este módulo cumple con el requisito de detección de recursos infrautilizados y patrones de desperdicio económico definidos en el reto de arquitectura de software.
