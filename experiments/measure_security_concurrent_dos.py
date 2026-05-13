"""
Experimento: Rate Limiting bajo concurrencia real (Locust)
============================================================

Mejora sobre `measure_security_ratelimit.py`:

    - El smoke test viejo hace 105 GETs en serie con `requests.get()` en
      un for. Eso prueba la *correctitud* pero NO la *concurrencia*.
    - Este wrapper levanta N usuarios virtuales de Locust en paralelo,
      todos con el mismo X-Forwarded-For. El middleware debe manejar
      contención simultánea sobre `RequestLog` y `BlockedIP`.

Diseño:
    1. Limpiar bloqueo previo de la IP atacante (idempotencia).
    2. Ejecutar `python -m locust --headless ...` como subproceso, con
       output CSV.
    3. Parsear `<prefix>_stats.csv`:
        - `Request Count` = total de requests servidos.
        - `Failure Count` = cuántos devolvieron 403 (Locust trata no-2xx
                            como failure).
    4. Verificar:
        - total > THRESHOLD            → atacante alcanzó a martillar.
        - failures > 0                 → middleware bloqueó al menos uno.
        - failures >= total - THRESHOLD - SLACK → casi todos los reqs
                                                  posteriores al umbral
                                                  fueron 403.
        - max_response_time_ms < 5000  → el sistema NO se cayó bajo carga.
    5. `GET /api/monitor-trafico/blocked/` debe listar la IP atacante.
    6. `POST /api/monitor-trafico/unblock/<ip>/` y verificar reapertura.

Uso:
    PYTHONIOENCODING=utf-8 \
    uv run python experiments/measure_security_concurrent_dos.py

Variables de entorno:
    BASE_URL           default http://127.0.0.1:8000
    ATTACKER_IP        default 10.0.0.99
    USERS              default 50    (usuarios concurrentes)
    SPAWN_RATE         default 25    (usuarios/segundo a crear)
    RUN_TIME           default 15s   (duración del ataque)
    THRESHOLD          default 100   (debe coincidir con TrafficMonitorService)
    SLACK              default 30    (margen para concurrencia — varios
                                       requests pueden colarse antes del
                                       primer 403 por race conditions
                                       entre el evaluate_ip y el log)
"""
import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments._common import BASE_URL, url, emit, fail, ok  # noqa: E402

ATTACKER_IP = os.environ.get('ATTACKER_IP', '10.0.0.99')
USERS       = os.environ.get('USERS', '50')
SPAWN_RATE  = os.environ.get('SPAWN_RATE', '25')
RUN_TIME    = os.environ.get('RUN_TIME', '15s')
THRESHOLD   = int(os.environ.get('THRESHOLD', '100'))
SLACK       = int(os.environ.get('SLACK', '30'))


def _unblock_attacker() -> None:
    """Best-effort unblock para limpiar estado entre corridas."""
    try:
        requests.post(url(f'/api/monitor-trafico/unblock/{ATTACKER_IP}/'),
                      headers={'X-Forwarded-For': '127.0.0.1'}, timeout=2)
    except requests.RequestException:
        pass


def _run_locust(csv_prefix: Path) -> int:
    """Ejecuta locust headless. Devuelve exit code del subproceso."""
    locustfile = Path(__file__).parent / 'locustfile_attacker.py'
    cmd = [
        sys.executable, '-m', 'locust',
        '-f', str(locustfile),
        '--host', BASE_URL,
        '--headless',
        '--users', USERS,
        '--spawn-rate', SPAWN_RATE,
        '--run-time', RUN_TIME,
        '--csv', str(csv_prefix),
        '--only-summary',
        '--exit-code-on-error', '0',  # 403s causan exit-on-error por default
    ]
    env = {**os.environ, 'ATTACKER_IP': ATTACKER_IP}
    emit('LOCUST_START', {'cmd': ' '.join(cmd)})
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    # Locust imprime su summary en stderr en modo --only-summary
    if proc.stderr:
        for line in proc.stderr.splitlines()[-10:]:
            emit('LOCUST_LOG', {'line': line})
    return proc.returncode


def _parse_stats(csv_prefix: Path) -> dict:
    """Lee `<prefix>_stats.csv` y extrae la fila Aggregated."""
    stats_file = Path(str(csv_prefix) + '_stats.csv')
    if not stats_file.exists():
        fail(f'Locust no produjo el CSV esperado: {stats_file}')
    with stats_file.open('r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    agg = next((r for r in rows if r.get('Name') == 'Aggregated'), None)
    if agg is None:
        fail('No se encontró fila "Aggregated" en el CSV de Locust',
             rows=[r.get('Name') for r in rows])
    return {
        'total':       int(agg['Request Count']),
        'failures':    int(agg['Failure Count']),
        'rps':         float(agg['Requests/s']),
        'avg_ms':      float(agg['Average Response Time']),
        'max_ms':      float(agg['Max Response Time']),
        'p95_ms':      float(agg.get('95%') or 0),
    }


def main() -> None:
    emit('START', {
        'experiment':  'security_concurrent_dos',
        'base_url':    BASE_URL,
        'attacker_ip': ATTACKER_IP,
        'users':       USERS, 'spawn_rate': SPAWN_RATE,
        'run_time':    RUN_TIME,
        'threshold':   THRESHOLD, 'slack': SLACK,
    })

    _unblock_attacker()

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_prefix = Path(tmpdir) / 'locust_run'
        rc = _run_locust(csv_prefix)
        if rc != 0:
            fail(f'Locust salió con código {rc}')

        stats = _parse_stats(csv_prefix)

    emit('LOCUST_STATS', stats)

    # ── Verificaciones ───────────────────────────────────────────────────
    if stats['total'] <= THRESHOLD:
        fail(f'El atacante no superó el umbral — solo {stats["total"]} reqs '
             f'(esperaba > {THRESHOLD}). Sube USERS o RUN_TIME.')

    if stats['failures'] == 0:
        fail('Ningún request fue bloqueado (Failure Count = 0). '
             'El middleware NO está rate-limiteando bajo concurrencia.',
             stats=stats)

    expected_min_failures = max(0, stats['total'] - THRESHOLD - SLACK)
    if stats['failures'] < expected_min_failures:
        fail(f'Failures ({stats["failures"]}) < esperado mínimo '
             f'({expected_min_failures} = total - threshold - slack). '
             f'El middleware bloqueó pero MUY tarde — posible race condition.',
             stats=stats)

    if stats['max_ms'] >= 5000:
        fail(f'Max response time {stats["max_ms"]} ms ≥ 5000 — '
             f'el sistema se degradó bajo carga (5xx o cuelgues).',
             stats=stats)

    emit('STATS_OK', {
        'total':                stats['total'],
        'failures_403':         stats['failures'],
        'success_under_threshold': stats['total'] - stats['failures'],
        'rps':                  round(stats['rps'], 1),
        'p95_ms':               round(stats['p95_ms'], 1),
        'max_ms':               round(stats['max_ms'], 1),
    })

    # ── /blocked/ debe listar al atacante ────────────────────────────────
    r = requests.get(url('/api/monitor-trafico/blocked/'),
                     headers={'X-Forwarded-For': '127.0.0.1'}, timeout=3)
    if r.status_code != 200:
        fail('GET /blocked/ no respondió 200', http=r.status_code)
    blocked = [b['ip_address'] for b in r.json().get('blocked_ips', [])]
    if ATTACKER_IP not in blocked:
        fail(f'IP {ATTACKER_IP} no aparece en /blocked/', blocked=blocked)
    emit('BLOCKED_LIST_OK', {'attacker': ATTACKER_IP})

    # ── Unblock y verificar reapertura ───────────────────────────────────
    r = requests.post(url(f'/api/monitor-trafico/unblock/{ATTACKER_IP}/'),
                      headers={'X-Forwarded-For': '127.0.0.1'}, timeout=3)
    if r.status_code != 200:
        fail('POST /unblock/ no respondió 200', http=r.status_code, body=r.text)
    r = requests.get(url('/api/monitor-servicios/health/'),
                     headers={'X-Forwarded-For': ATTACKER_IP}, timeout=3)
    if r.status_code == 403:
        fail('Tras /unblock/ la IP sigue retornando 403')
    emit('REOPEN_OK', {'http': r.status_code})

    ok('Rate limiting cumple bajo concurrencia — atacante bloqueado y '
       'reapertura manual funciona',
       total=stats['total'], failures_403=stats['failures'],
       rps=round(stats['rps'], 1), max_ms=round(stats['max_ms'], 1))


if __name__ == '__main__':
    main()
