"""
Middleware principal del Monitor de Tráfico.
Se engancha en cada request para registrar y evaluar el volumen de peticiones por IP.
"""
from django.http import HttpResponseForbidden

from .services import TrafficMonitorService


class TrafficMonitorMiddleware:
    """
    Middleware que:
    1. Registra cada petición entrante.
    2. Evalúa si la IP supera el umbral de peticiones (DoS detection).
    3. Rechaza la petición si la IP está bloqueada.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.service = TrafficMonitorService()

    def __call__(self, request):
        ip = self._get_client_ip(request)

        # TODO: verificar si la IP está bloqueada antes de procesar
        if self.service.is_blocked(ip):
            return HttpResponseForbidden("Tu IP ha sido bloqueada por exceso de peticiones.")

        response = self.get_response(request)

        # TODO: registrar la petición de forma asíncrona para no bloquear el hilo
        self.service.log_request(
            ip_address=ip,
            path=request.path,
            method=request.method,
            status_code=response.status_code,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

        # TODO: evaluar si se debe bloquear la IP tras esta petición
        self.service.evaluate_ip(ip)

        return response

    @staticmethod
    def _get_client_ip(request) -> str:
        """Extrae la IP real del cliente (considera proxies)."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')
