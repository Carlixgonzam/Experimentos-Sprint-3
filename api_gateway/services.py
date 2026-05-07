"""
Táctica de disponibilidad: Active Redundancy (recuperación)

El GatewayService consulta el estado de las instancias del Generador de Reportes
al Monitor de Servicios (que usa la información de Heartbeats) y enruta cada
request sólo a instancias vivas.

Flujo de failover (ASR2 — < 1 s desde detección):
  1. Monitor detecta instancia DOWN (heartbeat ausente > expected_interval).
  2. Próximo request llega al Gateway.
  3. Gateway consulta monitor en tiempo real → descarta instancias DOWN.
  4. Gateway enruta al primer candidato saludable.
  Tiempo total de esta decisión: < 10 ms (consulta DB local).
"""
import logging
import uuid

from django.conf import settings

from monitor_servicios.services import ServiceMonitorService
from generador_reportes.services import ReportGeneratorService

logger = logging.getLogger(__name__)


class GatewayService:
    def __init__(self) -> None:
        self._monitor   = ServiceMonitorService()
        self._generator = ReportGeneratorService()

    @property
    def _instances(self) -> list[str]:
        return getattr(
            settings, 'REPORT_GENERATOR_INSTANCES',
            ['generador_reportes_1', 'generador_reportes_2'],
        )

    def get_all_status(self) -> list[dict]:
        """Retorna el estado (vivo/caído) de todas las instancias registradas."""
        result = []
        for name in self._instances:
            try:
                health = self._monitor.get_service_health(name)
            except ValueError:
                health = {
                    'name': name,
                    'status': 'unknown',
                    'last_seen': None,
                    'is_alive': False,
                }
            result.append(health)
        return result

    def get_healthy_instances(self) -> list[dict]:
        return [s for s in self.get_all_status() if s['is_alive']]

    def route_report_request(
        self,
        business_id: uuid.UUID,
        month_year: str | None = None,
    ) -> dict:
        """
        Enruta la solicitud de reporte a la primera instancia saludable.
        Estrategia: first-healthy (se puede extender a round-robin).

        Args:
            business_id: UUID del negocio sobre el que se quiere el reporte.
            month_year:  filtro opcional 'YYYY-MM' para consumo USD.

        Raises:
            RuntimeError: si no hay ninguna instancia disponible.
            ValueError:   si el business_id no existe (404 a nivel HTTP).
        """
        healthy = self.get_healthy_instances()
        if not healthy:
            logger.error("[GATEWAY] Sin instancias saludables — retornando 503.")
            raise RuntimeError(
                "Todas las instancias del Generador de Reportes están caídas."
            )

        target = healthy[0]
        logger.info("[GATEWAY] Enrutando a '%s'.", target['name'])

        # En producción multi-instancia (AWS) haríamos un HTTP proxy al target['url'].
        # En el experimento mono-proceso llamamos la capa de servicio directamente.
        report = self._generate_report_on(
            target['name'], business_id, month_year=month_year,
        )
        return {'routed_to': target['name'], 'report': report}

    def _generate_report_on(
        self,
        instance_name: str,
        business_id: uuid.UUID,
        month_year: str | None = None,
    ) -> dict:
        """
        Genera el reporte real delegando a `ReportGeneratorService`.
        El `instance_name` se anota en `meta.routed_to` para que el cliente
        pueda evidenciar a qué instancia fue enrutado durante el experimento.
        """
        report = self._generator.generate_full_inventory_report(
            business_id, month_year=month_year,
        )
        # Anotación de trazabilidad para el experimento ASR2
        report.setdefault('meta', {})
        report['meta']['routed_to'] = instance_name
        return report
