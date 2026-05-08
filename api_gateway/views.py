"""
Views del API Gateway.

Endpoints:
  GET  /api/gateway/reportes/   → genera un reporte enrutado al primer
                                  generador de reportes saludable
  GET  /api/gateway/status/     → estado actual de todas las instancias
"""
import time
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .services import GatewayService

logger = logging.getLogger(__name__)
_gateway = GatewayService()


@method_decorator(csrf_exempt, name='dispatch')
class GatewayReportView(View):
    """
    GET /api/gateway/reportes/?business_id=<uuid>&month=YYYY-MM

    Punto de entrada principal. Enruta al primer generador de reportes
    saludable (first-healthy).
    """
    def get(self, request):
        import uuid as _uuid

        raw_id = request.GET.get('business_id', '').strip()
        if not raw_id:
            return JsonResponse(
                {'status': 'error',
                 'message': 'Query param `business_id` (UUID) es obligatorio.'},
                status=400,
            )
        try:
            bid = _uuid.UUID(raw_id)
        except ValueError:
            return JsonResponse(
                {'status': 'error',
                 'message': f'`business_id` no es un UUID válido: {raw_id}'},
                status=400,
            )
        month_year = request.GET.get('month') or None

        t0 = time.perf_counter()
        try:
            result = _gateway.route_report_request(bid, month_year=month_year)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return JsonResponse({
                'status': 'ok',
                'routed_to': result['routed_to'],
                # `routing_decision_ms` es la métrica del Gateway (decidir destino).
                # `report_generation_ms` puede incluir timeouts de DB externas
                # — degradación controlada cuando una fuente cae.
                'routing_decision_ms':  result['routing_decision_ms'],
                'report_generation_ms': result['report_generation_ms'],
                'total_ms':             round(elapsed_ms, 3),
                # Mantengo `routing_latency_ms` para no romper integraciones
                # existentes; es alias de `total_ms`.
                'routing_latency_ms':   round(elapsed_ms, 3),
                'report': result['report'],
            }, status=200)
        except RuntimeError as exc:
            return JsonResponse(
                {'status': 'error', 'message': str(exc)}, status=503,
            )
        except ValueError as exc:
            return JsonResponse(
                {'status': 'error', 'message': str(exc)}, status=404,
            )


@method_decorator(csrf_exempt, name='dispatch')
class GatewayStatusView(View):
    """
    GET /api/gateway/status/

    Muestra el estado en tiempo real de todas las instancias.
    Útil para dashboards de operaciones.
    """
    def get(self, request):
        all_status = _gateway.get_all_status()
        healthy = [s for s in all_status if s['is_alive']]

        return JsonResponse({
            'timestamp': timezone.now().isoformat(),
            'overall': 'OK' if healthy else 'DOWN',
            'healthy_count': len(healthy),
            'total_count': len(all_status),
            'instances': all_status,
        })
