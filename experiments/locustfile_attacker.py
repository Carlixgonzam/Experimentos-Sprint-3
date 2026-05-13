"""
Locustfile para simular un atacante DoS contra el monitor de tráfico.

Cada usuario virtual de Locust = una conexión TCP independiente del
atacante, pero TODOS comparten el mismo header `X-Forwarded-For` →
el middleware los ve como una **única IP** que está spammeando.

Esto es más realista que el `for i in range(105)` del smoke test
(`measure_security_ratelimit.py`) porque:
  - Las peticiones salen en paralelo desde múltiples conexiones.
  - El middleware tiene que manejar contención concurrente sobre
    `RequestLog` y `BlockedIP` (transacciones simultáneas a la DB).
  - Mide bien la latencia bajo carga, no solo en serie.

Cómo correrlo
=============

A. Modo headless (scripteado, ideal para CI o entrega):

    PYTHONIOENCODING=utf-8 \
    python -m locust \
        -f experiments/locustfile_attacker.py \
        --host http://127.0.0.1:8000 \
        --headless \
        --users 50 --spawn-rate 25 \
        --run-time 15s \
        --only-summary

   Esto lanza 50 usuarios concurrentes (la misma IP simulada), 25 por
   segundo, durante 15 segundos. Al final imprime un resumen con
   total de requests, RPS, fails, percentiles de latencia.

B. Modo Web UI (interactivo, ideal para demo):

    python -m locust -f experiments/locustfile_attacker.py --host http://127.0.0.1:8000

   Luego abre http://127.0.0.1:8089 en el navegador, configura users
   y spawn-rate, y observa las gráficas en tiempo real.

Resultado esperado
==================

Con umbral de 100 reqs/60s en `monitor_trafico.services`:

  - Los primeros ~100 requests reciben HTTP 200 (`{status: UP}`).
  - A partir del request #101 el middleware devuelve HTTP 403.
  - Locust marca 403 como failure por default (no es 2xx) — el
    "Failures" en el reporte ≈ total_requests - 100.
  - Después del run, `GET /api/monitor-trafico/blocked/` lista la IP
    del atacante.
  - Para reanudar, `POST /api/monitor-trafico/unblock/<ip>/`.

Variables de entorno (opcionales):

    ATTACKER_IP    IP a poner en X-Forwarded-For (default 10.0.0.99)
    TARGET_PATH    endpoint a martillar (default /api/monitor-servicios/health/)
"""
import os

from locust import HttpUser, task, constant


ATTACKER_IP = os.environ.get('ATTACKER_IP', '10.0.0.99')
TARGET_PATH = os.environ.get('TARGET_PATH', '/api/monitor-servicios/health/')


class Attacker(HttpUser):
    """
    Un solo "atacante" lógico — cientos de conexiones TCP, mismo X-Forwarded-For.

    `wait_time = constant(0)` significa "tan rápido como el cliente pueda",
    que es el comportamiento adversarial que queremos simular.
    """
    wait_time = constant(0)

    def on_start(self):
        # Header que el middleware lee como IP del cliente.
        self.client.headers['X-Forwarded-For'] = ATTACKER_IP

    @task
    def flood(self):
        # `name=` agrupa las stats por endpoint logico. Dejamos que Locust
        # cuente naturalmente 403 como failure: asi el "Failures" del CSV
        # nos da directamente cuantos requests cayeron en rate-limit.
        self.client.get(TARGET_PATH, name=TARGET_PATH)
