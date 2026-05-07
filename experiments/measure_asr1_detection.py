"""
Experimento ASR1 — Tiempo de detección de fallo
================================================

Hipótesis: una instancia del Generador de Reportes que deja de enviar
heartbeats es marcada como `is_alive=false` por el Monitor de Servicios
en menos de 1 segundo.

Diseño:
  1. Sondear `GET /api/gateway/experimento/medir/` para confirmar que la
     instancia objetivo está viva al inicio.
  2. `POST /api/gateway/experimento/matar/<instance>/` y registrar t0.
  3. Hacer polling cada 50 ms al endpoint `medir/` hasta que la instancia
     reporte `is_alive == false`.
  4. Reportar `seconds_since_kill = t_detection - t0`.
  5. PASS si `seconds_since_kill < 1.0` (objetivo del ASR1).
  6. Limpieza: `POST /experimento/revivir/<instance>/`.

Uso:
    BASE_URL=http://127.0.0.1:8000 python experiments/measure_asr1_detection.py

Variables de entorno:
    BASE_URL   default http://127.0.0.1:8000
    INSTANCE   default generador_reportes_1
    POLL_MS    default 50  (intervalo de polling en milisegundos)
    TIMEOUT_S  default 5   (techo absoluto antes de declarar timeout)
"""
import os
import sys
import time

import requests

# Permite ejecutar el script directamente: `python experiments/measure_*.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments._common import BASE_URL, url, emit, fail, ok  # noqa: E402

INSTANCE  = os.environ.get('INSTANCE', 'generador_reportes_1')
POLL_S    = float(os.environ.get('POLL_MS', '50')) / 1000
TIMEOUT_S = float(os.environ.get('TIMEOUT_S', '5'))


def get_instance_state(instance: str) -> dict:
    r = requests.get(url('/api/gateway/experimento/medir/'), timeout=2)
    r.raise_for_status()
    body = r.json()
    for m in body.get('measurements', []):
        if m.get('instance') == instance:
            return m
    raise RuntimeError(f'Instancia {instance} no aparece en /medir/')


def main() -> None:
    emit('START', {'experiment': 'ASR1_detection', 'base_url': BASE_URL,
                   'instance': INSTANCE, 'poll_ms': POLL_S * 1000,
                   'timeout_s': TIMEOUT_S})

    # 0. Pre-condición: instancia viva
    pre = get_instance_state(INSTANCE)
    if not pre.get('is_alive'):
        fail('Pre-condición falló: la instancia ya estaba caída antes del experimento',
             pre_state=pre)
    emit('PRECONDITION_OK', {'instance': INSTANCE, 'is_alive': True})

    # 1. Mata la instancia
    t0 = time.perf_counter()
    r = requests.post(url(f'/api/gateway/experimento/matar/{INSTANCE}/'), timeout=2)
    r.raise_for_status()
    emit('KILL_SENT', {'instance': INSTANCE, 'http': r.status_code})

    # 2. Polling hasta detección
    detected_at = None
    seconds_since = None
    while (time.perf_counter() - t0) < TIMEOUT_S:
        try:
            state = get_instance_state(INSTANCE)
        except requests.RequestException as exc:
            emit('POLL_ERROR', {'error': str(exc)})
            time.sleep(POLL_S)
            continue

        if not state.get('is_alive'):
            detected_at  = time.perf_counter()
            seconds_since = detected_at - t0
            emit('DETECTED', {'instance': INSTANCE,
                              'seconds_since_kill': round(seconds_since, 4),
                              'state': state})
            break
        time.sleep(POLL_S)

    # 3. Limpieza (siempre)
    try:
        requests.post(url(f'/api/gateway/experimento/revivir/{INSTANCE}/'),
                      timeout=2)
        emit('CLEANUP', {'revived': INSTANCE})
    except requests.RequestException as exc:
        emit('CLEANUP_FAIL', {'error': str(exc)})

    # 4. Veredicto
    if detected_at is None:
        fail('No se detectó la caída dentro del timeout',
             timeout_s=TIMEOUT_S)
    if seconds_since >= 1.0:
        fail('Detección fuera de objetivo ASR1 (>= 1 s)',
             seconds_since_kill=round(seconds_since, 4))

    ok('ASR1 cumplido — detección < 1 s',
       seconds_since_kill=round(seconds_since, 4))


if __name__ == '__main__':
    main()
