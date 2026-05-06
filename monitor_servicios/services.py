"""
Lógica de negocio del Monitor de Servicios.
Evalúa la salud de cada servicio registrado según sus heartbeats.
"""
from datetime import timedelta
from django.utils import timezone


class ServiceMonitorService:
    """
    Responsable de:
    - Registrar heartbeats entrantes.
    - Detectar servicios caídos (ausencia de heartbeat en el intervalo esperado).
    - Calcular el estado global del sistema.
    """

    def register_heartbeat(self, service_name: str, status: str, metadata: dict) -> None:
        """
        Persiste un Heartbeat para el servicio indicado.
        Lanza ValueError si el servicio no está registrado.
        """
        # TODO: buscar ServiceRegistration, crear Heartbeat
        raise NotImplementedError

    def get_service_health(self, service_name: str) -> dict:
        """
        Retorna el estado actual de un servicio:
        {'name': ..., 'status': ..., 'last_seen': ..., 'is_alive': bool}
        """
        # TODO: comparar last heartbeat timestamp con expected_interval_seconds
        raise NotImplementedError

    def get_system_health(self) -> list[dict]:
        """
        Retorna el estado de todos los servicios activos registrados.
        """
        # TODO: iterar ServiceRegistration.objects.filter(is_active=True)
        raise NotImplementedError

    def get_stale_services(self) -> list[str]:
        """
        Retorna los nombres de servicios que no han enviado heartbeat a tiempo.
        """
        # TODO: implementar detección de servicios caídos
        raise NotImplementedError
