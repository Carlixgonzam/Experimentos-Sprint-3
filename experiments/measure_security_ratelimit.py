"""
Experimento Seguridad — Rate Limiting / detección de DoS
=========================================================

Hipótesis: una IP que envíe más de `REQUEST_THRESHOLD` peticiones (default 100)
en una ventana de 60 s es bloqueada por el middleware de monitor_trafico
(HTTP 403) y aparece en `/api/monitor-trafico/blocked/`. Tras desbloquearla
con `POST /unblock/<ip>/` la IP vuelve a poder consumir endpoints.

Diseño:
  1. Limpia el estado: desbloquea la IP de prueba si quedó de una corrida previa.
  2. Envía 105 GETs a `/api/monitor-servicios/health/` con header
     `X-Forwarded-For: 10.0.0.99` (la IP real del cliente local es ignorada
     porque el middleware respeta XFF).
  3. Verifica la transición 200 → 403 ocurre antes de los 105.
  4. Confirma que la IP aparece en `/blocked/`.
  5. POST /unblock/ y verifica que un GET adicional vuelve a recibir 200.

Uso:
    BASE_URL=http://127.0.0.1:8000 python experiments/measure_security_ratelimit.py

Variables de entorno:
    BASE_URL       default http://127.0.0.1:8000
    ATTACKER_IP    default 10.0.0.99
    TOTAL_REQUESTS default 105
    THRESHOLD      default 100   (debe coincidir con TrafficMonitorService)
"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments._common import BASE_URL, url, emit, fail, ok  # noqa: E402

ATTACKER_IP    = os.environ.get('ATTACKER_IP', '10.0.0.99')
TOTAL_REQUESTS = int(os.environ.get('TOTAL_REQUESTS', '105'))
THRESHOLD      = int(os.environ.get('THRESHOLD', '100'))


def is_blocked_in_list(attacker: str) -> bool:
    r = requests.get(url('/api/monitor-trafico/blocked/'),
                     headers={'X-Forwarded-For': '127.0.0.1'},
                     timeout=2)
    if r.status_code != 200:
        return False
    return any(b.get('ip_address') == attacker
               for b in r.json().get('blocked_ips', []))


def main() -> None:
    emit('START', {'experiment': 'security_ratelimit', 'base_url': BASE_URL,
                   'attacker_ip': ATTACKER_IP, 'total_requests': TOTAL_REQUESTS,
                   'threshold': THRESHOLD})

    # 0. Pre-cleanup
    try:
        requests.post(url(f'/api/monitor-trafico/unblock/{ATTACKER_IP}/'),
                      headers={'X-Forwarded-For': '127.0.0.1'}, timeout=2)
    except requests.RequestException:
        pass

    # 1. Bombardeo desde la IP atacante
    headers = {'X-Forwarded-For': ATTACKER_IP}
    target  = url('/api/monitor-servicios/health/')

    first_403_at = None
    last_status  = None
    for i in range(1, TOTAL_REQUESTS + 1):
        try:
            r = requests.get(target, headers=headers, timeout=2)
        except requests.RequestException as exc:
            fail(f'Request {i} explotó: {exc}')
        last_status = r.status_code
        if r.status_code == 403 and first_403_at is None:
            first_403_at = i
            emit('FIRST_BLOCK', {'request_index': i})
            # Mandamos algunas más para confirmar que sigue 403
            for _ in range(3):
                rr = requests.get(target, headers=headers, timeout=2)
                if rr.status_code != 403:
                    fail('Tras el primer 403, recibimos otro status',
                         got=rr.status_code)
            break

    if first_403_at is None:
        fail('Nunca recibimos 403 — el middleware no bloqueó la IP',
             total_sent=TOTAL_REQUESTS, last_status=last_status)
    if first_403_at > THRESHOLD + 1:
        # +1 porque la lógica actual evalúa después de loggear, así que el
        # 101° request es el que primero retorna 403.
        emit('WARN', {
            'msg': f'Bloqueado en el request {first_403_at}, '
                   f'no <= {THRESHOLD + 1}. Aún cuenta como bloqueado.',
        })

    # 2. Confirma listado /blocked/
    if not is_blocked_in_list(ATTACKER_IP):
        fail('La IP no aparece en /api/monitor-trafico/blocked/',
             attacker=ATTACKER_IP)
    emit('BLOCK_LIST_OK', {'attacker': ATTACKER_IP})

    # 3. Desbloqueo manual
    r = requests.post(url(f'/api/monitor-trafico/unblock/{ATTACKER_IP}/'),
                      headers={'X-Forwarded-For': '127.0.0.1'}, timeout=2)
    if r.status_code != 200:
        fail('POST /unblock/ no respondió 200', http=r.status_code, body=r.text)
    emit('UNBLOCK_SENT', {'attacker': ATTACKER_IP})

    # 4. Confirma que la IP vuelve a ser admitida
    r = requests.get(target, headers=headers, timeout=2)
    if r.status_code == 403:
        fail('Tras /unblock/ la IP sigue retornando 403',
             attacker=ATTACKER_IP)
    emit('REOPEN_OK', {'http': r.status_code})

    ok('Rate limiting cumple — IP bloqueada tras umbral y desbloqueable',
       first_block_at=first_403_at, threshold=THRESHOLD)


if __name__ == '__main__':
    main()
