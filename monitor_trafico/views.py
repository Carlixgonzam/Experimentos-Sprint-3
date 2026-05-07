"""
Views del Monitor de Tráfico.

Endpoints:
  GET  /api/monitor-trafico/stats/             → estadísticas de tráfico reciente
  GET  /api/monitor-trafico/blocked/           → lista de IPs bloqueadas activas
  POST /api/monitor-trafico/unblock/<ip>/      → desbloquea una IP manualmente
"""
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from datetime import timedelta

from .models import BlockedIP, RequestLog
from .services import TrafficMonitorService

_svc = TrafficMonitorService()


@method_decorator(csrf_exempt, name='dispatch')
class TrafficStatsView(View):
    """GET /stats/ — resumen de tráfico en la última ventana de tiempo."""
    def get(self, request):
        window_seconds = int(request.GET.get('window', 60))
        window_start = timezone.now() - timedelta(seconds=window_seconds)
        recent = RequestLog.objects.filter(timestamp__gte=window_start)

        top_ips = list(
            recent.values('ip_address')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        return JsonResponse({
            'window_seconds': window_seconds,
            'total_requests': recent.count(),
            'top_ips': top_ips,
            'blocked_count': BlockedIP.objects.filter(is_active=True).count(),
        })


@method_decorator(csrf_exempt, name='dispatch')
class BlockedIPListView(View):
    """GET /blocked/ — IPs actualmente bloqueadas."""
    def get(self, request):
        blocked = list(
            BlockedIP.objects.filter(is_active=True)
            .values('ip_address', 'blocked_at', 'reason')
        )
        return JsonResponse({'blocked_ips': blocked, 'count': len(blocked)})


@method_decorator(csrf_exempt, name='dispatch')
class UnblockIPView(View):
    """POST /unblock/<ip>/ — levanta el bloqueo de una IP manualmente."""
    def post(self, request, ip_address: str):
        _svc.unblock_ip(ip_address)
        return JsonResponse({'message': f"IP {ip_address} desbloqueada.", 'ip': ip_address})
