"""
Táctica de disponibilidad: Heartbeat (emisor)

Cada instancia lógica del Generador de Reportes envía un heartbeat periódico
al Monitor de Servicios. Si el hilo deja de hacerlo (instancia "muerta"),
el monitor lo detectará en ≤ expected_interval_seconds.

Parámetros del experimento:
  HEARTBEAT_INTERVAL_SECONDS = 0.2  → un heartbeat cada 200 ms
  expected_interval_seconds  = 0.8  → umbral de detección: 800 ms

Peor caso de detección: failure justo tras enviar heartbeat → detectado en 800 ms < 1 s ✓
"""
import logging
import threading
import time

from django.db import close_old_connections

logger = logging.getLogger(__name__)

# Estado en memoria — controla qué instancias tienen los heartbeats pausados
_killed: set[str] = set()
_lock = threading.Lock()


def kill_instance(name: str) -> None:
    """Pausa los heartbeats de la instancia (simula fallo)."""
    with _lock:
        _killed.add(name)
    logger.warning("[EXPERIMENTO] Instancia '%s' marcada como caída.", name)


def revive_instance(name: str) -> None:
    """Reanuda los heartbeats de la instancia (simula recuperación)."""
    with _lock:
        _killed.discard(name)
    logger.info("[EXPERIMENTO] Instancia '%s' reactivada.", name)


def is_killed(name: str) -> bool:
    with _lock:
        return name in _killed


def _register_instances(instances: list[str], interval: float) -> None:
    """Auto-registra las instancias en ServiceRegistration si no existen."""
    from monitor_servicios.models import ServiceRegistration
    for name in instances:
        ServiceRegistration.objects.get_or_create(
            name=name,
            defaults={
                'description': f'Instancia simulada del Generador de Reportes ({name})',
                # Umbral = intervalo * 4 garantiza < 1 s de detección con intervalo 0.2 s
                'expected_interval_seconds': interval * 4,
                'is_active': True,
            },
        )


def _heartbeat_loop(instances: list[str], interval: float) -> None:
    from monitor_servicios.services import ServiceMonitorService
    svc = ServiceMonitorService()

    # Espera breve para que Django termine de arrancar completamente
    time.sleep(1.5)
    _register_instances(instances, interval)

    while True:
        close_old_connections()
        for name in instances:
            if not is_killed(name):
                try:
                    svc.register_heartbeat(service_name=name, status='ok', metadata={})
                except Exception as exc:
                    logger.debug("Heartbeat fallido para '%s': %s", name, exc)
        time.sleep(interval)


class HeartbeatSender:
    _thread: threading.Thread | None = None

    @classmethod
    def start(cls) -> None:
        if cls._thread and cls._thread.is_alive():
            return

        from django.conf import settings
        instances: list[str] = getattr(
            settings, 'REPORT_GENERATOR_INSTANCES',
            ['generador_reportes_1', 'generador_reportes_2'],
        )
        interval: float = getattr(settings, 'HEARTBEAT_INTERVAL_SECONDS', 0.2)

        t = threading.Thread(
            target=_heartbeat_loop,
            args=(instances, interval),
            daemon=True,
            name='HeartbeatSender',
        )
        t.start()
        cls._thread = t
        logger.info(
            "HeartbeatSender arrancado — instancias: %s, intervalo: %.1fs",
            instances, interval,
        )
