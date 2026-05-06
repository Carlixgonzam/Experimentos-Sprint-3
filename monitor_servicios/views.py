"""
Views del Monitor de Servicios.

Endpoints:
  GET  /health/                          → self health-check (para que Kong/otros te pingueen)
  POST /monitor/heartbeat/               → recibir heartbeat de un servicio
  GET  /monitor/status/                  → estado de todos los servicios
  GET  /monitor/status/<service_name>/   → estado de un servicio específico
  GET  /monitor/stale/                   → servicios caídos/tardíos
"""
import json
import logging

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .services import ServiceMonitorService

logger = logging.getLogger(__name__)
_svc = ServiceMonitorService()


def _json_body(request) -> dict:
    """Parsea el body JSON del request. Retorna {} si está vacío o es inválido."""
    try:
        return json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        return {}


# ── Self health-check ─────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class SelfHealthView(View):
    """
    GET /health/

    Responde que este componente está vivo.
    Kong y otros servicios usan este endpoint para verificar que el
    Monitor de Servicios está operativo (Ping/Echo inverso).
    """
    def get(self, request):
        return JsonResponse({'status': 'UP', 'service': 'monitor-servicios'}, status=200)


# ── Heartbeat ─────────────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class HeartbeatView(View):
    """
    POST /monitor/heartbeat/

    Body esperado:
    {
      "service_name": "generador_reportes",
      "status": "ok",          ← opcional, default "ok"
      "metadata": {}            ← opcional
    }

    Los servicios monitoreados llaman a este endpoint periódicamente.
    El Monitor registra el heartbeat y actualiza el estado.
    """
    def post(self, request):
        data = _json_body(request)
        service_name = data.get('service_name', '').strip()

        if not service_name:
            return JsonResponse({'error': 'service_name es requerido.'}, status=400)

        try:
            hb = _svc.register_heartbeat(
                service_name=service_name,
                status=data.get('status', 'ok'),
                metadata=data.get('metadata', {}),
            )
            return JsonResponse({
                'message': 'Heartbeat registrado.',
                'service': service_name,
                'received_at': hb.received_at.isoformat(),
                'status': hb.status,
            }, status=201)

        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=404)

        except Exception as e:
            logger.exception("Error registrando heartbeat para %s", service_name)
            return JsonResponse({'error': 'Error interno.'}, status=500)


# ── Estado del sistema ────────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class SystemHealthView(View):
    """
    GET /monitor/status/

    Retorna el estado de todos los servicios activos.
    HTTP 200 si todos vivos, 207 si alguno está caído.
    """
    def get(self, request):
        health = _svc.get_system_health()
        all_alive = all(s['is_alive'] for s in health)

        return JsonResponse({
            'overall': 'OK' if all_alive else 'DEGRADED',
            'services': health,
        }, status=200 if all_alive else 207)


@method_decorator(csrf_exempt, name='dispatch')
class ServiceHealthView(View):
    """
    GET /monitor/status/<service_name>/

    Retorna el estado de un servicio específico.
    HTTP 200 (vivo) o 503 (caído) o 404 (no encontrado).
    """
    def get(self, request, service_name: str):
        try:
            health = _svc.get_service_health(service_name)
            status_code = 200 if health['is_alive'] else 503
            return JsonResponse(health, status=status_code)

        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=404)


@method_decorator(csrf_exempt, name='dispatch')
class StaleServicesView(View):
    """
    GET /monitor/stale/

    Lista los servicios que no han enviado heartbeat a tiempo.
    Útil para alertas y dashboards de operaciones.
    """
    def get(self, request):
        stale = _svc.get_stale_services()
        return JsonResponse({
            'stale_count': len(stale),
            'stale_services': stale,
        }, status=200)