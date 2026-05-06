from django.db import models


class RequestLog(models.Model):
    """
    Registro individual de una petición HTTP entrante.
    Usado por el Monitor de Tráfico para detectar patrones de DoS.
    """
    ip_address = models.GenericIPAddressField()
    path = models.CharField(max_length=512)
    method = models.CharField(max_length=10)
    timestamp = models.DateTimeField(auto_now_add=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['ip_address', 'timestamp']),
        ]

    def __str__(self):
        return f"[{self.timestamp}] {self.ip_address} -> {self.method} {self.path}"


class BlockedIP(models.Model):
    """
    IPs bloqueadas por exceder el umbral de peticiones (posible DoS).
    """
    ip_address = models.GenericIPAddressField(unique=True)
    blocked_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Blocked: {self.ip_address} ({'active' if self.is_active else 'lifted'})"
