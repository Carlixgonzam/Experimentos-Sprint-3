"""
Experimento: Monitoreo (Ping/Echo) + Heartbeats
================================================

Evidencia las dos tácticas de detección de la categoría 01 del cuadro de
disponibilidad:

    1. Monitoreo (Ping/Echo)
        - El servicio expone GET /api/monitor-servicios/health/ que
          responde 200 con `{status: UP}` — un endpoint pasivo al que
          cualquier supervisor puede pingear.

    2. Heartbeats
        - Las instancias del Generador de Reportes envían heartbeats
          periódicos (cada 200 ms) al Monitor de Servicios mediante un
          thread daemon que arranca con el server (HeartbeatSender).
        - El Monitor mantiene el último timestamp por servicio y expone
          GET /api/monitor-servicios/monitor/status/ que reporta
          `is_alive: true` mientras el último heartbeat sea reciente.

Diseño de la medición:

    PASO 1 — Ping/Echo:
        GET /api/monitor-servicios/health/
        Verificar HTTP 200 y que responde rápido (< 100 ms).

    PASO 2 — Heartbeats están vivos:
        GET /api/monitor-servicios/monitor/status/
        Verificar que las dos instancias del Generador de Reportes
        aparecen con `is_alive: true` y `last_seen` no nulo.

    PASO 3 — Heartbeats AVANZAN en tiempo real:
        Tomar `last_seen_T1`, dormir HEARTBEAT_INTERVAL_SECONDS * 3,
        tomar `last_seen_T2`, verificar que T2 > T1 para AMBAS instancias.
        Esto demuestra que el thread emisor está vivo y emitiendo, no
        que estamos viendo heartbeats fósiles de una corrida anterior.

PASS si los tres pasos pasan.

Uso:
    PYTHONIOENCODING=utf-8 \
    uv run python experiments/measure_heartbeat_monitoring.py

Variables de entorno:
    BASE_URL                       default http://127.0.0.1:8000
    PING_BUDGET_MS                 default 200   (latencia max del /health/)
    HEARTBEAT_OBSERVATION_S        default 0.6   (tiempo entre T1 y T2)
"""
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments._common import BASE_URL, url, emit, fail, ok  # noqa: E402

PING_BUDGET_MS          = int(os.environ.get('PING_BUDGET_MS', '200'))
HEARTBEAT_OBSERVATION_S = float(os.environ.get('HEARTBEAT_OBSERVATION_S', '0.6'))


def main() -> None:
    emit('START', {
        'experiment':              'heartbeat_monitoring',
        'base_url':                BASE_URL,
        'ping_budget_ms':          PING_BUDGET_MS,
        'heartbeat_observation_s': HEARTBEAT_OBSERVATION_S,
    })

    # ── PASO 1 — Ping/Echo ───────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        r = requests.get(url('/api/monitor-servicios/health/'), timeout=2)
    except requests.RequestException as exc:
        fail(f'Error de transporte en /health/: {exc}')
    ping_ms = (time.perf_counter() - t0) * 1000

    if r.status_code != 200:
        fail('Ping /health/ no respondió 200',
             http=r.status_code, body=r.text[:200])
    body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
    if body.get('status') != 'UP':
        fail("Ping /health/ no respondió status='UP'", body=body)
    if ping_ms >= PING_BUDGET_MS:
        fail(f'Ping > {PING_BUDGET_MS} ms', ping_ms=round(ping_ms, 3))

    emit('PING_ECHO_OK', {'http': 200, 'status': 'UP',
                          'ping_ms': round(ping_ms, 3)})

    # ── PASO 2 — Heartbeats están vivos ───────────────────────────────────
    try:
        r = requests.get(url('/api/monitor-servicios/monitor/status/'), timeout=2)
    except requests.RequestException as exc:
        fail(f'Error de transporte en /monitor/status/: {exc}')
    if r.status_code not in (200, 207):
        fail('GET /monitor/status/ respondió código inesperado',
             http=r.status_code, body=r.text[:200])

    services = r.json().get('services', [])
    by_name  = {s['name']: s for s in services}
    expected_names = ('generador_reportes_1', 'generador_reportes_2')
    for name in expected_names:
        if name not in by_name:
            fail(f'Instancia {name} no aparece en /monitor/status/',
                 services=list(by_name.keys()))
        s = by_name[name]
        if not s.get('is_alive'):
            fail(f'Instancia {name} no está viva',
                 last_seen=s.get('last_seen'))
        if not s.get('last_seen'):
            fail(f'Instancia {name} sin last_seen',
                 service=s)

    last_seen_T1 = {n: by_name[n]['last_seen'] for n in expected_names}
    emit('HEARTBEATS_ALIVE_T1', {'last_seen_T1': last_seen_T1})

    # ── PASO 3 — Heartbeats AVANZAN en tiempo real ────────────────────────
    time.sleep(HEARTBEAT_OBSERVATION_S)

    try:
        r = requests.get(url('/api/monitor-servicios/monitor/status/'), timeout=2)
    except requests.RequestException as exc:
        fail(f'Error de transporte (T2) en /monitor/status/: {exc}')
    services_T2 = {s['name']: s for s in r.json().get('services', [])}

    last_seen_T2 = {n: services_T2[n]['last_seen'] for n in expected_names
                    if n in services_T2}
    emit('HEARTBEATS_ALIVE_T2', {'last_seen_T2': last_seen_T2})

    for name in expected_names:
        t1 = last_seen_T1.get(name)
        t2 = last_seen_T2.get(name)
        if not t2 or t2 <= t1:
            fail(f'Instancia {name}: heartbeat NO avanzó entre T1 y T2 — '
                 f'el thread emisor está bloqueado o muerto',
                 t1=t1, t2=t2)

    emit('HEARTBEATS_PROGRESSING', {
        n: f'{last_seen_T1[n]} -> {last_seen_T2[n]}' for n in expected_names
    })

    ok('Monitoreo (Ping/Echo) + Heartbeats cumplen — endpoint /health/ '
       'responde rápido y los heartbeats avanzan en tiempo real',
       ping_ms=round(ping_ms, 3),
       observation_window_s=HEARTBEAT_OBSERVATION_S,
       instances_observed=list(expected_names))


if __name__ == '__main__':
    main()
