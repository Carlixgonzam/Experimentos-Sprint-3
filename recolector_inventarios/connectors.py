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

    La conexión a Mongo se abre de forma perezosa (lazy) en la primera
    consulta — así el monolito puede arrancar y servir endpoints que NO
    dependen de Mongo aunque Mongo esté caído.
    """

    COLLECTION = 'cloud_telemetry'

    def __init__(self):
        self._client = None
        self._col    = None

    # Timeout corto para que un Mongo caído no bloquee al cliente
    # — crítico para el ASR2 (latencia objetivo < 1.5 s, y el reporte hace
    # potencialmente 2 llamadas a Mongo S3+EC2). Con 500ms peor caso son
    # 1000ms si las dos fuentes están caídas, y el cortocircuito en
    # `ReportGeneratorService` lo baja a ~500ms.
    _SERVER_SELECTION_TIMEOUT_MS = 500
    _CONNECT_TIMEOUT_MS          = 500
    _SOCKET_TIMEOUT_MS           = 1000

    @property
    def col(self):
        if self._col is None:
            import pymongo
            self._client = pymongo.MongoClient(
                settings.MONGO_URI,
                serverSelectionTimeoutMS=self._SERVER_SELECTION_TIMEOUT_MS,
                connectTimeoutMS=self._CONNECT_TIMEOUT_MS,
                socketTimeoutMS=self._SOCKET_TIMEOUT_MS,
            )
            db = self._client[settings.MONGO_DB_NAME]
            self._col = db[self.COLLECTION]
        return self._col

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
        if self._client is not None:
            self._client.close()
            self._client = None
            self._col    = None