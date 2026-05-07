"""
Capa de servicio del Recolector de Inventarios.
Orquesta los conectores y aplica la lógica de transformación / enriquecimiento
antes de exponer los datos a las vistas o al Generador de Reportes.
"""
import uuid
from .connectors import PostgresConnector, MongoConnector


class USDConsumptionService:
    """
    Lógica para el endpoint /businesses/{id}/USDConsumption (fuente: Postgres).
    """

    def __init__(self):
        self.pg = PostgresConnector()

    def get(self, business_id: uuid.UUID, month_year: str | None = None) -> list[dict]:
        """
        Retorna los registros de consumo en USD para un negocio.
        Lanza ValueError si el negocio no existe.
        Lanza LookupError si no hay registros para el filtro dado.
        """
        if not self.pg.business_exists(business_id):
            raise ValueError(f"Business {business_id} no encontrado.")

        records = self.pg.fetch_usd_consumption(business_id, month_year)

        if not records:
            raise LookupError(
                f"Sin registros de consumo para {business_id}"
                + (f" en {month_year}" if month_year else "")
            )

        # Enriquecimiento: calcular variación presupuestal si hay budget
        for r in records:
            r['total_usd_spent'] = float(r['total_usd_spent'])

        return records


class CloudGovernanceService:
    """
    Lógica para el endpoint /businesses/{id}/CloudGovernance (fuente: Postgres).
    """

    def __init__(self):
        self.pg = PostgresConnector()

    def get(self, business_id: uuid.UUID) -> dict:
        """
        Retorna la configuración de gobernanza.
        Lanza ValueError si el negocio no existe.
        Lanza LookupError si no tiene gobernanza configurada.
        """
        if not self.pg.business_exists(business_id):
            raise ValueError(f"Business {business_id} no encontrado.")

        gov = self.pg.fetch_cloud_governance(business_id)
        if gov is None:
            raise LookupError(f"No hay configuración de gobernanza para {business_id}.")

        return gov


class S3UsageService:
    """
    Lógica para el endpoint /businesses/{id}/S3Usage (fuente: MongoDB).
    """

    def __init__(self):
        self.pg    = PostgresConnector()
        self.mongo = MongoConnector()

    def get(self, business_id: uuid.UUID) -> dict:
        """
        Retorna el detalle de uso S3.
        Lanza ValueError si el negocio no existe en Postgres.
        Lanza LookupError si no hay telemetría S3 en Mongo.
        """
        if not self.pg.business_exists(business_id):
            raise ValueError(f"Business {business_id} no encontrado.")

        doc = self.mongo.fetch_s3_usage(str(business_id))
        if doc is None:
            raise LookupError(f"Sin datos S3 para {business_id}.")

        # Extraer y normalizar campos del documento Mongo
        details = doc.get('details', {})
        buckets = details.get('buckets', [])

        # Calcular waste_percentage por bucket
        for bucket in buckets:
            size = bucket.get('size_gb', 0)
            unused_days = bucket.get('unused_days', 0)
            # Heurística simple: >90 días sin uso → 100% desperdicio; proporcional si menos
            bucket['waste_percentage'] = round(min(unused_days / 90 * 100, 100), 1)
            bucket['policy_violations'] = bucket.get('policy_violations', [])
            bucket['storage_class']     = bucket.get('storage_class', 'STANDARD')
            bucket['last_access_date']  = bucket.get('last_access_date', None)

        return {
            'business_id':    str(business_id),
            'service':        'S3',
            'buckets':        buckets,
            'total_waste_gb': details.get('total_waste_gb', 0),
        }


class EC2UsageService:
    """
    Lógica para el endpoint /businesses/{id}/EC2Usage (fuente: MongoDB).
    """

    CPU_UNDERUTILIZED_THRESHOLD = 20.0   # % promedio por debajo del cual se considera infrautilizado

    def __init__(self):
        self.pg    = PostgresConnector()
        self.mongo = MongoConnector()

    def get(self, business_id: uuid.UUID) -> dict:
        """
        Retorna el detalle de uso EC2.
        Lanza ValueError si el negocio no existe en Postgres.
        Lanza LookupError si no hay telemetría EC2 en Mongo.
        """
        if not self.pg.business_exists(business_id):
            raise ValueError(f"Business {business_id} no encontrado.")

        doc = self.mongo.fetch_ec2_usage(str(business_id))
        if doc is None:
            raise LookupError(f"Sin datos EC2 para {business_id}.")

        details   = doc.get('details', {})
        instances = details.get('instances', [])

        for inst in instances:
            cpu_avg = inst.get('cpu_utilization_avg', 0)
            inst['is_underutilized'] = cpu_avg < self.CPU_UNDERUTILIZED_THRESHOLD
            inst['optimization_suggestions'] = self._build_suggestions(inst)

        return {
            'business_id': str(business_id),
            'service':     'EC2',
            'instances':   instances,
        }

    @staticmethod
    def _build_suggestions(instance: dict) -> list[str]:
        suggestions = []
        cpu = instance.get('cpu_utilization_avg', 0)
        if cpu < 10:
            suggestions.append("Considerar terminar o hibernar la instancia.")
        elif cpu < 20:
            suggestions.append("Reducir el tipo de instancia (downsize).")
        if instance.get('uptime_logs') and len(instance['uptime_logs']) > 720:
            suggestions.append("Revisar si la instancia requiere uptime 24/7.")
        return suggestions