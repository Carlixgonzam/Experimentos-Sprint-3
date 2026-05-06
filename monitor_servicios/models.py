from django.db import models


class ServiceRegistration(models.Model):
    """
    Registro de un servicio interno que debe enviar heartbeats periódicos.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    expected_interval_seconds = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Heartbeat(models.Model):
    """
    Evento de heartbeat emitido por un servicio registrado.
    """

    class Status(models.TextChoices):
        OK = 'ok', 'OK'
        DEGRADED = 'degraded', 'Degraded'
        ERROR = 'error', 'Error'

    service = models.ForeignKey(
        ServiceRegistration,
        on_delete=models.CASCADE,
        related_name='heartbeats',
    )
    received_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OK)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-received_at']
        get_latest_by = 'received_at'

    def __str__(self):
        return f"{self.service.name} @ {self.received_at} [{self.status}]"
