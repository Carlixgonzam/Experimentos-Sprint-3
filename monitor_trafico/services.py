"""
Lógica de negocio del Monitor de Tráfico.
Táctica: Rate Limiting — detección y bloqueo de IPs con tráfico abusivo (DoS).
"""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import BlockedIP, RequestLog


class TrafficMonitorService:
    REQUEST_THRESHOLD = 100
    TIME_WINDOW_SECONDS = 60

    def is_blocked(self, ip_address: str) -> bool:
        return BlockedIP.objects.filter(ip_address=ip_address, is_active=True).exists()

    def log_request(self, ip_address: str, path: str, method: str,
                    status_code: int, user_agent: str) -> None:
        RequestLog.objects.create(
            ip_address=ip_address,
            path=path,
            method=method,
            status_code=status_code,
            user_agent=user_agent,
        )

    def evaluate_ip(self, ip_address: str) -> bool:
        window_start = timezone.now() - timedelta(seconds=self.TIME_WINDOW_SECONDS)
        count = RequestLog.objects.filter(
            ip_address=ip_address,
            timestamp__gte=window_start,
        ).count()

        if count >= self.REQUEST_THRESHOLD:
            BlockedIP.objects.update_or_create(
                ip_address=ip_address,
                defaults={
                    'is_active': True,
                    'reason': (
                        f"Excedió {self.REQUEST_THRESHOLD} peticiones "
                        f"en {self.TIME_WINDOW_SECONDS}s"
                    ),
                },
            )
            return True
        return False

    def unblock_ip(self, ip_address: str) -> None:
        BlockedIP.objects.filter(ip_address=ip_address).update(is_active=False)

    def get_top_ips(self, window_seconds: int = 60) -> list[dict]:
        window_start = timezone.now() - timedelta(seconds=window_seconds)
        return list(
            RequestLog.objects.filter(timestamp__gte=window_start)
            .values('ip_address')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
