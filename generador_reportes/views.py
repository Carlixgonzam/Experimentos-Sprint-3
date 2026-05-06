"""
Views del Generador de Reportes.

Endpoints directos (sin pasar por el API Gateway):
  GET /api/generador-reportes/health/   → self health-check
  GET /api/generador-reportes/generar/  → genera reporte combinado (stub)
"""
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator


@method_decorator(csrf_exempt, name='dispatch')
class ReportHealthView(View):
    """GET /health/ — el API Gateway y el Monitor de Servicios usan este endpoint."""
    def get(self, request):
        return JsonResponse({'status': 'UP', 'service': 'generador_reportes'}, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class GenerateReportView(View):
    """
    GET /generar/

    Retorna un reporte de inventario combinado (Postgres + Mongo).
    Por ahora devuelve datos de ejemplo; la integración real con
    recolector_inventarios se completa en el Sprint 4.
    """
    def get(self, request):
        return JsonResponse({
            'meta': {
                'generated_at': timezone.now().isoformat(),
                'sources': ['postgres', 'mongo'],
            },
            'postgres': [],
            'mongo': [],
            'combined': [],
        }, status=200)
