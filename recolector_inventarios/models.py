"""
Modelos Django (PostgreSQL) del Recolector de Inventarios.

Esquema:
  businesses            → empresa / cliente
  consumption_summary   → gasto mensual en USD  (endpoint /USDConsumption)
  cloud_governance      → etiquetas y límites    (endpoint /CloudGovernance)

MongoDB almacena cloud_telemetry (S3Usage, EC2Usage) — sin modelos Django.
La join key entre ambas DBs es businesses.id_business (UUID).
"""
import uuid
from django.db import models


class Business(models.Model):
    """
    Empresa cliente. Llave de unión con MongoDB (business_id).
    """
    id_business = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=255)
    nit         = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = 'businesses'

    def __str__(self):
        return f"{self.name} ({self.nit})"


class ConsumptionSummary(models.Model):
    """
    Gasto mensual total en USD por empresa.
    Fuente: PostgreSQL — endpoint /businesses/{id}/USDConsumption
    """

    class PaymentStatus(models.TextChoices):
        PENDING  = 'pending',  'Pendiente'
        PAID     = 'paid',     'Pagado'
        OVERDUE  = 'overdue',  'Vencido'

    id_business       = models.ForeignKey(Business, on_delete=models.CASCADE,
                                          db_column='id_business',
                                          related_name='consumption_summaries')
    month_year        = models.CharField(max_length=7)          # '2026-05'
    total_usd_spent   = models.DecimalField(max_digits=12, decimal_places=2)
    currency          = models.CharField(max_length=3, default='USD')
    assigned_budget   = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment_status    = models.CharField(max_length=20, choices=PaymentStatus.choices,
                                         default=PaymentStatus.PENDING)

    class Meta:
        db_table = 'consumption_summary'
        unique_together = [('id_business', 'month_year')]

    def __str__(self):
        return f"{self.id_business_id} | {self.month_year} | ${self.total_usd_spent}"


class CloudGovernance(models.Model):
    """
    Reglas de gobernanza cloud por empresa.
    Fuente: PostgreSQL — endpoint /businesses/{id}/CloudGovernance
    """
    id_business          = models.OneToOneField(Business, on_delete=models.CASCADE,
                                                db_column='id_business',
                                                related_name='governance',
                                                primary_key=True,
                                                )
    # Tags obligatorios almacenados como JSON: {"env": "prod", "owner": "..."}
    mandatory_tags       = models.JSONField(default=dict)
    responsible_area     = models.CharField(max_length=255)
    # Límites por proyecto: {"proyecto-a": 5000.00, "proyecto-b": 12000.00}
    spend_limits_by_project = models.JSONField(default=dict)

    class Meta:
        db_table = 'cloud_governance'

    def __str__(self):
        return f"Governance for {self.id_business_id}"
