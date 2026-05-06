"""
Conectores de bajo nivel hacia PostgreSQL (ORM Django) y MongoDB (pymongo).
Cada conector expone métodos de lectura crudos; la lógica de negocio vive en services.py.
"""
import uuid
from django.conf import settings


# ---------------------------------------------------------------------------
# PostgreSQL connector — usa el ORM de Django
# ---------------------------------------------------------------------------

class PostgresConnector:
    """
    Acceso directo a las tablas Postgres definidas en models.py.
    Retorna siempre dicts planos (sin instancias ORM) para mantener
    la interfaz agnóstica al ORM.
    """

    def fetch_usd_consumption(self, business_id: uuid.UUID, month_year: str | None = None) -> list[dict]:
        """
        Retorna los registros de ConsumptionSummary para el negocio indicado.
        Si se pasa month_year ('2026-05') filtra por ese mes.
        """
        from .models import ConsumptionSummary

        qs = ConsumptionSummary.objects.filter(id_business_id=business_id)
        if month_year:
            qs = qs.filter(month_year=month_year)

        return list(qs.values(
            'month_year',
            'total_usd_spent',
            'currency',
            'assigned_budget',
            'payment_status',
        ))

    def fetch_cloud_governance(self, business_id: uuid.UUID) -> dict | None:
        """
        Retorna la configuración de gobernanza de un negocio o None si no existe.
        """
        from .models import CloudGovernance

        try:
            gov = CloudGovernance.objects.get(id_business_id=business_id)
        except CloudGovernance.DoesNotExist:
            return None

        return {
            'mandatory_tags':          gov.mandatory_tags,
            'responsible_area':        gov.responsible_area,
            'spend_limits_by_project': gov.spend_limits_by_project,
        }

    def business_exists(self, business_id: uuid.UUID) -> bool:
        from .models import Business
        return Business.objects.filter(pk=business_id).exists()


# ---------------------------------------------------------------------------
# MongoDB connector — usa pymongo
# ---------------------------------------------------------------------------

class MongoConnector:
    """
    Acceso a la colección cloud_telemetry en MongoDB.
    Cada documento tiene la forma:
    {
        "business_id": "<UUID>",
        "service":     "S3" | "EC2",
        "details":     { ... }
    }
    """

    COLLECTION = 'cloud_telemetry'

    def __init__(self):
        import pymongo
        self.client = pymongo.MongoClient(settings.MONGO_URI)
        self.db     = self.client[settings.MONGO_DB_NAME]
        self.col    = self.db[self.COLLECTION]

    # ------------------------------------------------------------------
    # S3
    # ------------------------------------------------------------------

    def fetch_s3_usage(self, business_id: str) -> dict | None:
        """
        Retorna el documento de telemetría S3 para el negocio indicado.
        Retorna None si no existe.
        """
        doc = self.col.find_one(
            {'business_id': business_id, 'service': 'S3'},
            {'_id': 0},   # excluir _id de Mongo para serialización limpia
        )
        return doc

    # ------------------------------------------------------------------
    # EC2
    # ------------------------------------------------------------------

    def fetch_ec2_usage(self, business_id: str) -> dict | None:
        """
        Retorna el documento de telemetría EC2 para el negocio indicado.
        """
        doc = self.col.find_one(
            {'business_id': business_id, 'service': 'EC2'},
            {'_id': 0},
        )
        return doc

    def close(self):
        """Cierra la conexión a MongoDB explícitamente."""
        self.client.close()