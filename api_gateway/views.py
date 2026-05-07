"""
Views del API Gateway.

Endpoints de servicio:
  GET  /api/gateway/reportes/   → genera un reporte, enrutando a instancia sana
  GET  /api/gateway/status/     → estado actual de todas las instancias

Endpoints del experimento (simulación de fallos):
  POST /api/gateway/experimento/matar/<instance>/    → pausa heartbeats (simula fallo)
  POST /api/gateway/experimento/revivir/<instance>/  → reanuda heartbeats
  GET  /api/gateway/experimento/medir/               → mide tiempo de detección
"""
import time
import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .services import GatewayService
from generador_reportes.heartbeat import kill_instance, revive_instance, is_killed

logger = logging.getLogger(__name__)
_gateway = GatewayService()


# ── Endpoints de producción ───────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class GatewayReportView(View):
    """
    GET /api/gateway/reportes/?business_id=<uuid>&month=YYYY-MM

    Punto de entrada principal. Implementa Active Redundancy:
    enruta al primer generador de reportes saludable.
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
                'routing_latency_ms': round(elapsed_ms, 3),
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
        for s in all_status:
            s['heartbeat_paused'] = is_killed(s['name'])

        return JsonResponse({
            'timestamp': timezone.now().isoformat(),
            'overall': 'OK' if healthy else 'DOWN',
            'healthy_count': len(healthy),
            'total_count': len(all_status),
            'instances': all_status,
        })


# ── Endpoints del experimento (ASR de disponibilidad) ────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class ExperimentKillView(View):
    """
    POST /api/gateway/experimento/matar/<instance_name>/

    Simula el fallo de una instancia deteniendo sus heartbeats.
    La detección por el Monitor de Servicios debe ocurrir en < 1 s (ASR1).
    """
    def post(self, request, instance_name: str):
        valid = getattr(settings, 'REPORT_GENERATOR_INSTANCES', [])
        if instance_name not in valid:
            return JsonResponse(
                {'error': f"Instancia '{instance_name}' no existe. Válidas: {valid}"},
                status=404,
            )

        kill_instance(instance_name)
        return JsonResponse({
            'accion': 'instancia_detenida',
            'instance': instance_name,
            'killed_at': timezone.now().isoformat(),
            'instrucciones': (
                f"Espera ~1 s y luego llama GET /api/gateway/status/ "
                f"para verificar que '{instance_name}' aparece como is_alive=false (ASR1). "
                f"Luego llama GET /api/gateway/reportes/ para verificar que el sistema "
                f"sigue operando usando la instancia restante (ASR2)."
            ),
        })


@method_decorator(csrf_exempt, name='dispatch')
class ExperimentReviveView(View):
    """
    POST /api/gateway/experimento/revivir/<instance_name>/

    Reanuda los heartbeats de una instancia previamente detenida.
    """
    def post(self, request, instance_name: str):
        valid = getattr(settings, 'REPORT_GENERATOR_INSTANCES', [])
        if instance_name not in valid:
            return JsonResponse(
                {'error': f"Instancia '{instance_name}' no existe."},
                status=404,
            )

        revive_instance(instance_name)
        return JsonResponse({
            'accion': 'instancia_reactivada',
            'instance': instance_name,
            'revived_at': timezone.now().isoformat(),
        })


@method_decorator(csrf_exempt, name='dispatch')
class ExperimentMeasureView(View):
    """
    GET /api/gateway/experimento/medir/

    Mide en tiempo real cuánto tiempo lleva detectar el fallo:
    - Indica cuándo fue el último heartbeat de cada instancia.
    - Indica si ya se detectó como caída.
    - Calcula el tiempo transcurrido desde el último heartbeat.
    Útil para evidenciar el cumplimiento de ASR1 (< 1 s de detección).
    """
    def get(self, request):
        from monitor_servicios.models import ServiceRegistration, Heartbeat
        now = timezone.now()
        instances = getattr(settings, 'REPORT_GENERATOR_INSTANCES', [])
        measurements = []

        for name in instances:
            try:
                reg = ServiceRegistration.objects.get(name=name)
                try:
                    last_hb = reg.heartbeats.latest()
                    seconds_since = (now - last_hb.received_at).total_seconds()
                    is_alive = seconds_since < reg.expected_interval_seconds
                    measurements.append({
                        'instance': name,
                        'last_heartbeat': last_hb.received_at.isoformat(),
                        'seconds_since_last_hb': round(seconds_since, 3),
                        'detection_threshold_s': reg.expected_interval_seconds,
                        'is_alive': is_alive,
                        'heartbeat_paused': is_killed(name),
                        'detection_note': (
                            f"Fallo detectado en {round(seconds_since, 3)} s"
                            if not is_alive else
                            f"Viva — quedan {round(reg.expected_interval_seconds - seconds_since, 3)} s antes de timeout"
                        ),
                    })
                except Heartbeat.DoesNotExist:
                    measurements.append({
                        'instance': name,
                        'last_heartbeat': None,
                        'seconds_since_last_hb': None,
                        'detection_threshold_s': reg.expected_interval_seconds,
                        'is_alive': False,
                        'heartbeat_paused': is_killed(name),
                        'detection_note': 'Sin heartbeats registrados aún.',
                    })
            except ServiceRegistration.DoesNotExist:
                measurements.append({
                    'instance': name,
                    'error': 'No registrada en ServiceRegistration aún.',
                })

        return JsonResponse({
            'timestamp': now.isoformat(),
            'measurements': measurements,
            'asr1_target': '< 1 segundo desde el fallo hasta is_alive=false',
            'asr2_target': '< 1 segundo desde detección hasta gateway enruta correctamente',
        })
