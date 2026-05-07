"""
Views del Generador de Reportes (acceso directo, sin pasar por el API Gateway).

Endpoints:
  GET /api/generador-reportes/health/                   → self health-check
  GET /api/generador-reportes/generar/?business_id=...  → reporte combinado real
"""
import logging
import uuid

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .services import ReportGeneratorService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class ReportHealthView(View):
    """GET /health/ — el API Gateway y el Monitor de Servicios usan este endpoint."""
    def get(self, request):
        return JsonResponse(
            {'status': 'UP', 'service': 'generador_reportes'},
            status=200,
        )


@method_decorator(csrf_exempt, name='dispatch')
class GenerateReportView(View):
    """
    GET /generar/?business_id=<uuid>&month=YYYY-MM

    Genera un reporte de inventario combinado (Postgres + Mongo) usando
    `ReportGeneratorService`. `month` es opcional.
    """
    def get(self, request):
        raw_id = request.GET.get('business_id', '').strip()
        if not raw_id:
            return JsonResponse(
                {'error': 'Query param `business_id` (UUID) es obligatorio.'},
                status=400,
            )

        try:
            bid = uuid.UUID(raw_id)
        except ValueError:
            return JsonResponse(
                {'error': f'`business_id` no es un UUID válido: {raw_id}'},
                status=400,
            )

        month_year = request.GET.get('month') or None

        try:
            report = ReportGeneratorService().generate_full_inventory_report(
                bid, month_year=month_year,
            )
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=404)
        except Exception:
            logger.exception("Error generando reporte para %s", bid)
            return JsonResponse(
                {'error': 'Error interno generando el reporte.'},
                status=500,
            )

        return JsonResponse(report, status=200)
