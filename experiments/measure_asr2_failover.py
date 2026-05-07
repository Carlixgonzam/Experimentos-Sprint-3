"""
Experimento ASR2 — Active Redundancy / Failover
================================================

Hipótesis: tras la detección de una instancia caída, el API Gateway sigue
sirviendo `GET /api/gateway/reportes/` enrutando al nodo sano restante,
con latencia de routing < 100 ms y latencia total de la solicitud < 1.5 s.

Diseño:
  1. Verificar pre-condición: ambas instancias vivas.
  2. Matar `generador_reportes_1` (mismo flujo que ASR1).
  3. Esperar a que el monitor reporte `is_alive=false` (ASR1).
  4. Cronometrar `GET /reportes/?business_id=<UUID>` y verificar:
     - HTTP 200
     - `routed_to == generador_reportes_2`
     - `routing_latency_ms < 100`
     - latencia total medida desde el cliente < 1500 ms
  5. Limpieza: revivir la instancia.

Uso:
    BASE_URL=http://127.0.0.1:8000 \
    EXPERIMENT_BUSINESS_ID=11111111-1111-1111-1111-111111111111 \
    python experiments/measure_asr2_failover.py

Variables de entorno adicionales:
    KILLED_INSTANCE     default generador_reportes_1
    EXPECTED_FAILOVER   default generador_reportes_2
    DETECTION_TIMEOUT_S default 5
"""
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments._common import (  # noqa: E402
    BASE_URL, DEFAULT_BID, url, emit, fail, ok,
)

KILLED              = os.environ.get('KILLED_INSTANCE',     'generador_reportes_1')
EXPECTED            = os.environ.get('EXPECTED_FAILOVER',   'generador_reportes_2')
DETECTION_TIMEOUT_S = float(os.environ.get('DETECTION_TIMEOUT_S', '5'))


def get_status() -> dict:
    r = requests.get(url('/api/gateway/status/'), timeout=2)
    r.raise_for_status()
    return r.json()


def wait_until_dead(instance: str, timeout_s: float) -> float:
    """Polling /medir/ hasta que la instancia aparezca caída. Retorna t_detección."""
    t0 = time.perf_counter()
    while (time.perf_counter() - t0) < timeout_s:
        try:
            r = requests.get(url('/api/gateway/experimento/medir/'), timeout=2)
            r.raise_for_status()
            for m in r.json().get('measurements', []):
                if m.get('instance') == instance and not m.get('is_alive'):
                    return time.perf_counter()
        except requests.RequestException:
            pass
        time.sleep(0.05)
    raise TimeoutError(f'No se detectó caída de {instance} en {timeout_s}s')


def main() -> None:
    emit('START', {'experiment': 'ASR2_failover', 'base_url': BASE_URL,
                   'killed': KILLED, 'expected_failover': EXPECTED,
                   'business_id': DEFAULT_BID})

    pre = get_status()
    if pre['healthy_count'] < 2:
        fail('Pre-condición falló: se requieren al menos 2 instancias sanas',
             status=pre)
    emit('PRECONDITION_OK', {'healthy_count': pre['healthy_count']})

    # 1. Mata la instancia
    t_kill = time.perf_counter()
    r = requests.post(url(f'/api/gateway/experimento/matar/{KILLED}/'), timeout=2)
    r.raise_for_status()
    emit('KILL_SENT', {'instance': KILLED})

    # 2. Espera detección
    try:
        t_detect = wait_until_dead(KILLED, DETECTION_TIMEOUT_S)
    except TimeoutError as exc:
        # limpieza antes de salir
        requests.post(url(f'/api/gateway/experimento/revivir/{KILLED}/'), timeout=2)
        fail(str(exc))
    detection_s = t_detect - t_kill
    emit('DETECTED', {'seconds_since_kill': round(detection_s, 4)})

    # 3. Solicita el reporte vía Gateway — debe enrutar al sano
    report_target = url('/api/gateway/reportes/') + f'?business_id={DEFAULT_BID}'
    t_req = time.perf_counter()
    try:
        rr = requests.get(report_target, timeout=5)
    except requests.RequestException as exc:
        requests.post(url(f'/api/gateway/experimento/revivir/{KILLED}/'), timeout=2)
        fail(f'Error en GET /reportes/: {exc}')
    total_latency_ms = (time.perf_counter() - t_req) * 1000
    body = rr.json() if rr.headers.get('content-type', '').startswith('application/json') else {}

    emit('REPORT_RESPONSE', {
        'http': rr.status_code,
        'routed_to': body.get('routed_to'),
        'routing_latency_ms_server': body.get('routing_latency_ms'),
        'total_latency_ms_client':   round(total_latency_ms, 3),
    })

    # 4. Limpieza
    try:
        requests.post(url(f'/api/gateway/experimento/revivir/{KILLED}/'), timeout=2)
        emit('CLEANUP', {'revived': KILLED})
    except requests.RequestException as exc:
        emit('CLEANUP_FAIL', {'error': str(exc)})

    # 5. Veredicto
    if rr.status_code != 200:
        fail('GET /reportes/ no respondió 200', http=rr.status_code, body=body)
    if body.get('routed_to') != EXPECTED:
        fail(f'Routed_to inesperado',
             expected=EXPECTED, got=body.get('routed_to'))
    routing_ms = body.get('routing_latency_ms', float('inf'))
    if routing_ms >= 100:
        fail('routing_latency_ms >= 100 ms', routing_latency_ms=routing_ms)
    if total_latency_ms >= 1500:
        fail('total_latency_ms_client >= 1500 ms',
             total_latency_ms=round(total_latency_ms, 3))

    ok('ASR2 cumplido — failover < 1.5 s, enrutamiento < 100 ms',
       seconds_since_kill=round(detection_s, 4),
       routing_latency_ms=routing_ms,
       total_latency_ms_client=round(total_latency_ms, 3),
       routed_to=body.get('routed_to'))


if __name__ == '__main__':
    main()
