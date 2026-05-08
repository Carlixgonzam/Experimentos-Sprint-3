"""
Experimento: Degradación Controlada (Graceful Degradation)
============================================================

Hipótesis:
    Cuando MongoDB no responde, el endpoint /api/gateway/reportes/ sigue
    retornando HTTP 200 con los datos críticos de Postgres preservados,
    las secciones dependientes de Mongo explícitamente en `null`, y dentro
    de un presupuesto de latencia acotado (no se cuelga 30 s con el default
    de pymongo).

Esto evidencia la táctica de **degradación controlada**: ante un fallo
parcial de la capa de datos, el sistema NO cae completamente — entrega
funcionalidad reducida pero útil al cliente.

Pre-condición:
    Mongo NO está accesible. El experimento NO simula un fallo: depende
    de que el Mongo configurado en `settings` realmente no responda.

    En modo TEST (DJANGO_SETTINGS_MODULE=settings_test) `MONGO_URI` apunta
    a `127.0.0.1:27017` que normalmente está vacío, así que el sistema
    degrada genuinamente.

    En PROD/AWS basta con que el host de Mongo esté caído o haya una
    network partition real.

Diseño de la medición:
    1. GET /api/gateway/reportes/?business_id=<UUID>
    2. Cronometrar latencia desde el cliente.
    3. Verificar:
         - HTTP 200 (no 5xx) → el sistema NO se cae.
         - report.postgres.consumption es lista no vacía
                                   → datos críticos preservados.
         - report.postgres.governance presente y dict
                                   → datos críticos preservados.
         - report.mongo.s3  is None
         - report.mongo.ec2 is None
                                   → degradación visible/explícita,
                                     no se inventa data.
         - total_latency_ms < TIMEOUT_MS → latencia acotada.
    4. PASS si todas las verificaciones pasan.

Uso:
    PYTHONIOENCODING=utf-8 python experiments/measure_graceful_degradation.py

Variables de entorno:
    BASE_URL                 default http://127.0.0.1:8000
    EXPERIMENT_BUSINESS_ID   default 11111111-1111-1111-1111-111111111111
    TIMEOUT_MS               default 1500   (latencia máxima aceptada)
"""
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments._common import (  # noqa: E402
    BASE_URL, DEFAULT_BID, url, emit, fail, ok,
)

TIMEOUT_MS = int(os.environ.get('TIMEOUT_MS', '1500'))


def main() -> None:
    target = url('/api/gateway/reportes/') + f'?business_id={DEFAULT_BID}'
    emit('START', {
        'experiment':   'graceful_degradation',
        'base_url':     BASE_URL,
        'business_id':  DEFAULT_BID,
        'timeout_ms':   TIMEOUT_MS,
        'target_url':   target,
    })

    t0 = time.perf_counter()
    try:
        rr = requests.get(target, timeout=10)
    except requests.RequestException as exc:
        fail(f'Error de transporte: {exc}')
    total_latency_ms = (time.perf_counter() - t0) * 1000

    body = {}
    try:
        body = rr.json()
    except ValueError:
        fail('Respuesta no es JSON parseable',
             http=rr.status_code, raw=rr.text[:200])

    emit('REPORT_RESPONSE', {
        'http':                  rr.status_code,
        'total_latency_ms':      round(total_latency_ms, 3),
        'routing_decision_ms':   body.get('routing_decision_ms'),
        'report_generation_ms':  body.get('report_generation_ms'),
        'routed_to':             body.get('routed_to'),
    })

    # Verificación 1 — el sistema no se cayó
    if rr.status_code != 200:
        fail('HTTP != 200: el sistema falló completamente cuando Mongo cayó',
             http=rr.status_code, body=body)

    # Verificación 2 — datos críticos de Postgres preservados
    report = body.get('report') or {}
    pg     = report.get('postgres') or {}
    consumption = pg.get('consumption')
    governance  = pg.get('governance')

    if not isinstance(consumption, list) or len(consumption) == 0:
        fail('postgres.consumption no es lista no-vacía — datos críticos perdidos',
             postgres=pg)
    if not isinstance(governance, dict):
        fail('postgres.governance no es dict — datos críticos perdidos',
             governance=governance)

    emit('CRITICAL_DATA_PRESERVED', {
        'consumption_records': len(consumption),
        'has_governance':      True,
    })

    # Verificación 3 — degradación visible (Mongo en null, no inventado)
    mongo = report.get('mongo') or {}
    s3   = mongo.get('s3')
    ec2  = mongo.get('ec2')

    if s3 is not None or ec2 is not None:
        # Esto significa que Mongo SÍ respondió. El experimento no aplica.
        fail(
            'Mongo respondió — la pre-condición del experimento no se cumple. '
            'Para evidenciar degradación controlada, Mongo debe estar inalcanzable.',
            mongo_s3_present=(s3 is not None),
            mongo_ec2_present=(ec2 is not None),
        )

    emit('GRACEFUL_NULL_SECTIONS', {
        'mongo.s3':  None,
        'mongo.ec2': None,
    })

    # Verificación 4 — latencia acotada (no se colgó 30 s)
    if total_latency_ms >= TIMEOUT_MS:
        fail(f'Latencia >= {TIMEOUT_MS} ms — la degradación no fue controlada',
             total_latency_ms=round(total_latency_ms, 3))

    ok('Degradación controlada cumple — sistema sigue sirviendo Postgres '
       'con secciones de Mongo en null y latencia acotada',
       http=rr.status_code,
       total_latency_ms=round(total_latency_ms, 3),
       consumption_records=len(consumption),
       routing_decision_ms=body.get('routing_decision_ms'),
       report_generation_ms=body.get('report_generation_ms'))


if __name__ == '__main__':
    main()
