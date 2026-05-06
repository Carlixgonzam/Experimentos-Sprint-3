"""
Lógica de negocio del Monitor de Servicios.
Evalúa la salud de cada servicio registrado según sus heartbeats.

Táctica arquitectónica: Ping/Echo
  - Los servicios monitoreados envían heartbeats periódicos (el "echo").
  - Este módulo verifica si el echo llegó a tiempo (el "detector").
  - Si no hay echo en expected_interval_seconds → servicio DOWN.
  - Cumple el ASR: detección de fallo < 1 segundo (la detección es local,
    no requiere llamada de red — solo consulta la DB).
"""
from datetime import timedelta

from django.utils import timezone

from .models import Heartbeat, ServiceRegistration


class ServiceMonitorService:
    """
    Responsable de:
    - Registrar heartbeats entrantes.
    - Detectar servicios caídos (ausencia de heartbeat en el intervalo esperado).
    - Calcular el estado global del sistema.
    """

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _is_alive(self, registration: ServiceRegistration) -> tuple[bool, object | None]:
        """
        Decide si un servicio sigue vivo comparando el timestamp del último
        heartbeat con su expected_interval_seconds.

        Returns:
            (is_alive: bool, last_heartbeat: Heartbeat | None)
        """
        try:
            last = registration.heartbeats.latest()
        except Heartbeat.DoesNotExist:
            return False, None

        deadline = timezone.now() - timedelta(seconds=registration.expected_interval_seconds)
        return last.received_at >= deadline, last

    # ── Métodos públicos ──────────────────────────────────────────────────────

    def register_heartbeat(self, service_name: str, status: str, metadata: dict) -> Heartbeat:
        """
        Persiste un Heartbeat para el servicio indicado.
        Lanza ValueError si el servicio no está registrado o está inactivo.

        Args:
            service_name: nombre único del servicio (debe existir en ServiceRegistration).
            status:       uno de 'ok', 'degraded', 'error'.
            metadata:     dict libre con info adicional del servicio.

        Returns:
            El objeto Heartbeat creado.
        """
        try:
            registration = ServiceRegistration.objects.get(name=service_name, is_active=True)
        except ServiceRegistration.DoesNotExist:
            raise ValueError(
                f"Servicio '{service_name}' no está registrado o no está activo."
            )

        # Normalizar status — si viene un valor inválido usamos 'ok' por defecto
        valid_statuses = {choice[0] for choice in Heartbeat.Status.choices}
        if status not in valid_statuses:
            status = Heartbeat.Status.OK

        heartbeat = Heartbeat.objects.create(
            service=registration,
            status=status,
            metadata=metadata or {},
        )
        return heartbeat

    def get_service_health(self, service_name: str) -> dict:
        """
        Retorna el estado actual de un servicio.

        Returns:
            {
              'name':      str,
              'status':    'ok' | 'degraded' | 'error' | 'unknown',
              'last_seen': ISO8601 str | None,
              'is_alive':  bool,
            }

        Lanza ValueError si el servicio no existe.
        """
        try:
            registration = ServiceRegistration.objects.get(name=service_name)
        except ServiceRegistration.DoesNotExist:
            raise ValueError(f"Servicio '{service_name}' no encontrado.")

        is_alive, last_hb = self._is_alive(registration)

        return {
            'name':      registration.name,
            'status':    last_hb.status if last_hb else 'unknown',
            'last_seen': last_hb.received_at.isoformat() if last_hb else None,
            'is_alive':  is_alive,
        }

    def get_system_health(self) -> list[dict]:
        """
        Retorna el estado de todos los servicios activos registrados.

        Returns:
            Lista de dicts con el mismo esquema que get_service_health().
        """
        active_services = ServiceRegistration.objects.filter(is_active=True)
        return [
            self.get_service_health(registration.name)
            for registration in active_services
        ]

    def get_stale_services(self) -> list[str]:
        """
        Retorna los nombres de servicios que NO han enviado heartbeat a tiempo.

        Un servicio está "stale" (caído/tardío) si:
          - Nunca ha enviado heartbeat, O
          - El último heartbeat es más viejo que expected_interval_seconds.

        Returns:
            Lista de nombres de servicios caídos.
        """
        active_services = ServiceRegistration.objects.filter(is_active=True)
        stale = []

        for registration in active_services:
            is_alive, _ = self._is_alive(registration)
            if not is_alive:
                stale.append(registration.name)

        return stale