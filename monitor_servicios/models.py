from django.db import models


class ServiceRegistration(models.Model):
    """
    Registro de un servicio interno que debe enviar heartbeats periódicos.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    expected_interval_seconds = models.FloatField(default=30.0)
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    # Timestamp del último heartbeat recibido (OK o no).
    # Se actualiza con UPDATE en lugar de INSERT por cada heartbeat normal,
    # evitando acumulación infinita de filas en la tabla Heartbeat.
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class Heartbeat(models.Model):
    """
    Evento notable — solo se persiste cuando algo va mal o se recupera.

    Se guarda:
      - 'degraded'  : el servicio reportó estado degradado
      - 'error'     : el servicio reportó error
      - 'recovered' : el servicio volvió a OK tras haber estado en fallo
      - 'timeout'   : el monitor detectó que el servicio dejó de responder

    NO se guarda:
      - 'ok' normal → solo actualiza last_heartbeat_at en ServiceRegistration
    """

    class Status(models.TextChoices):
        OK        = 'ok',        'OK'
        DEGRADED  = 'degraded',  'Degraded'
        ERROR     = 'error',     'Error'
        RECOVERED = 'recovered', 'Recovered'
        TIMEOUT   = 'timeout',   'Timeout'

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