"""
Lógica de negocio del Monitor de Servicios.
Evalúa la salud de cada servicio registrado según sus heartbeats.

Táctica arquitectónica: Ping/Echo
  - Los servicios monitoreados envían heartbeats periódicos (el "echo").
  - Este módulo verifica si el echo llegó a tiempo (el "detector").
  - Si no hay echo en expected_interval_seconds → servicio DOWN.
  - Cumple el ASR: detección de fallo < 1 segundo (la detección es local,
    no requiere llamada de red — solo consulta last_heartbeat_at en DB).

Estrategia de persistencia:
  - Heartbeat OK     → solo UPDATE de last_heartbeat_at (sin INSERT)
  - Heartbeat no-OK  → INSERT en tabla Heartbeat (evento notable)
  - Recuperación     → INSERT con status='recovered' (evento notable)
"""
import logging
from datetime import timedelta

from django.utils import timezone

from .models import Heartbeat, ServiceRegistration

logger = logging.getLogger(__name__)

# Estados que ameritan persistir un registro en la tabla Heartbeat
_NOTABLE_STATUSES = {
    Heartbeat.Status.DEGRADED,
    Heartbeat.Status.ERROR,
    Heartbeat.Status.TIMEOUT,
}


class ServiceMonitorService:

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _is_alive(self, registration: ServiceRegistration) -> bool:
        """
        Decide si un servicio sigue vivo comparando last_heartbeat_at
        con expected_interval_seconds.

        Usa el campo desnormalizado last_heartbeat_at en lugar de consultar
        la tabla Heartbeat — más rápido y sin generar filas innecesarias.
        """
        if registration.last_heartbeat_at is None:
            return False
        deadline = timezone.now() - timedelta(
            seconds=registration.expected_interval_seconds
        )
        return registration.last_heartbeat_at >= deadline

    def _was_previously_failed(self, registration: ServiceRegistration) -> bool:
        """
        Comprueba si el último evento notable registrado era un fallo.
        Sirve para detectar recuperaciones y loguearlas.
        """
        last_event = registration.heartbeats.first()  # ordering = ['-received_at']
        if last_event is None:
            return False
        return last_event.status in (
            Heartbeat.Status.DEGRADED,
            Heartbeat.Status.ERROR,
            Heartbeat.Status.TIMEOUT,
        )

    # ── Métodos públicos ──────────────────────────────────────────────────────

    def register_heartbeat(
        self, service_name: str, status: str, metadata: dict
    ) -> None:
        """
        Procesa un heartbeat entrante.

        - Siempre actualiza last_heartbeat_at (UPDATE, no INSERT).
        - Solo inserta en la tabla Heartbeat si el estado es notable
          (degraded / error) o si el servicio se está recuperando.

        Lanza ValueError si el servicio no está registrado o está inactivo.
        """
        try:
            registration = ServiceRegistration.objects.get(
                name=service_name, is_active=True
            )
        except ServiceRegistration.DoesNotExist:
            raise ValueError(
                f"Servicio '{service_name}' no está registrado o no está activo."
            )

        now = timezone.now()

        # Normalizar status
        valid_statuses = {choice[0] for choice in Heartbeat.Status.choices}
        if status not in valid_statuses:
            status = Heartbeat.Status.OK

        # ── Siempre actualizar timestamp (sin INSERT) ──────────────────────
        ServiceRegistration.objects.filter(pk=registration.pk).update(
            last_heartbeat_at=now
        )

        # ── Persistir solo eventos notables ───────────────────────────────
        if status in _NOTABLE_STATUSES:
            Heartbeat.objects.create(
                service=registration,
                status=status,
                metadata=metadata or {},
            )
            logger.warning(
                "Heartbeat notable — servicio '%s' reportó estado '%s'.",
                service_name, status,
            )

        elif status == Heartbeat.Status.OK and self._was_previously_failed(registration):
            # El servicio vuelve a OK después de un fallo → registrar recuperación
            Heartbeat.objects.create(
                service=registration,
                status=Heartbeat.Status.RECOVERED,
                metadata=metadata or {},
            )
            logger.info(
                "Recuperación — servicio '%s' volvió a OK.",
                service_name,
            )

    def get_service_health(self, service_name: str) -> dict:
        """
        Retorna el estado actual de un servicio.

        Returns:
            {
              'name':      str,
              'last_seen': ISO8601 str | None,
              'is_alive':  bool,
              'last_event': {'status': str, 'at': ISO8601} | None
            }

        Lanza ValueError si el servicio no existe.
        """
        try:
            registration = ServiceRegistration.objects.get(name=service_name)
        except ServiceRegistration.DoesNotExist:
            raise ValueError(f"Servicio '{service_name}' no encontrado.")

        is_alive = self._is_alive(registration)

        # Último evento notable (puede ser None si nunca falló)
        last_event = registration.heartbeats.first()

        return {
            'name':      registration.name,
            'last_seen': (
                registration.last_heartbeat_at.isoformat()
                if registration.last_heartbeat_at else None
            ),
            'is_alive':  is_alive,
            'last_event': {
                'status': last_event.status,
                'at':     last_event.received_at.isoformat(),
            } if last_event else None,
        }

    def get_system_health(self) -> list[dict]:
        """Retorna el estado de todos los servicios activos."""
        active = ServiceRegistration.objects.filter(is_active=True)
        return [self.get_service_health(r.name) for r in active]

    def get_stale_services(self) -> list[str]:
        """Retorna los nombres de servicios que no han enviado heartbeat a tiempo."""
        active = ServiceRegistration.objects.filter(is_active=True)
        return [r.name for r in active if not self._is_alive(r)]