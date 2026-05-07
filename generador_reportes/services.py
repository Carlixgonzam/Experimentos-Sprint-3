"""
Lógica de negocio del Generador de Reportes.

Orquesta la obtención de datos desde el RecolectorInventarios
(Postgres + Mongo) y los concatena en un payload JSON estructurado
para el frontend / API Gateway.

Diseño:
  - Cada fuente puede fallar de forma independiente (LookupError → sección vacía).
  - Sólo `business_id no encontrado` (ValueError) burbujea, porque significa
    que la solicitud completa es inválida.
"""
import logging
import uuid

from django.utils import timezone

from recolector_inventarios.services import (
    USDConsumptionService,
    CloudGovernanceService,
    S3UsageService,
    EC2UsageService,
)

logger = logging.getLogger(__name__)


class ReportGeneratorService:
    """
    Combina datos de Postgres y Mongo en un único reporte JSON.

    Estructura del reporte:
    {
        "meta": {"generated_at": ISO8601, "business_id": str, "sources": [...]},
        "postgres": {
            "consumption":  [...] | None,
            "governance":   {...} | None
        },
        "mongo": {
            "s3":   {...} | None,
            "ec2":  {...} | None
        },
        "combined": [...]
    }
    """

    def __init__(self) -> None:
        # Los servicios del recolector son baratos de instanciar (no abren
        # conexiones eagerly excepto MongoConnector → cliente reusable por
        # request).
        self._usd  = USDConsumptionService()
        self._gov  = CloudGovernanceService()
        self._s3   = S3UsageService()
        self._ec2  = EC2UsageService()

    # ── API pública ─────────────────────────────────────────────────────────

    def generate_full_inventory_report(
        self,
        business_id: uuid.UUID,
        month_year: str | None = None,
    ) -> dict:
        """
        Args:
            business_id: UUID del negocio cuyo reporte se solicita.
            month_year:  filtro opcional de mes (formato 'YYYY-MM') para el
                         consumo USD; el resto de fuentes lo ignoran.

        Raises:
            ValueError: si el negocio no existe en Postgres (la fuente de verdad).
        """
        postgres_payload = self._fetch_from_postgres(business_id, month_year)
        mongo_payload    = self._fetch_from_mongo(business_id)

        return {
            'meta': {
                'generated_at': timezone.now().isoformat(),
                'business_id':  str(business_id),
                'sources':      ['postgres', 'mongo'],
            },
            'postgres': postgres_payload,
            'mongo':    mongo_payload,
            'combined': self._combine(postgres_payload, mongo_payload),
        }

    # ── Internals ───────────────────────────────────────────────────────────

    def _fetch_from_postgres(
        self,
        business_id: uuid.UUID,
        month_year: str | None,
    ) -> dict:
        """
        Lee consumo USD + gobernanza desde Postgres.
        Si el business no existe (ValueError) propaga; si simplemente no hay
        registros (LookupError) deja la sección como None — el reporte sigue
        siendo válido con datos parciales.
        """
        try:
            consumption = self._usd.get(business_id, month_year)
        except LookupError as exc:
            logger.info("Sin consumo USD para %s: %s", business_id, exc)
            consumption = None

        try:
            governance = self._gov.get(business_id)
        except LookupError as exc:
            logger.info("Sin governance para %s: %s", business_id, exc)
            governance = None

        return {
            'consumption': consumption,
            'governance':  governance,
        }

    def _fetch_from_mongo(self, business_id: uuid.UUID) -> dict:
        """
        Lee telemetría S3 y EC2 desde MongoDB. Cada subfuente es independiente.
        """
        try:
            s3 = self._s3.get(business_id)
        except LookupError as exc:
            logger.info("Sin S3 usage para %s: %s", business_id, exc)
            s3 = None

        try:
            ec2 = self._ec2.get(business_id)
        except LookupError as exc:
            logger.info("Sin EC2 usage para %s: %s", business_id, exc)
            ec2 = None

        return {
            's3':  s3,
            'ec2': ec2,
        }

    @staticmethod
    def _combine(postgres: dict, mongo: dict) -> list[dict]:
        """
        Estrategia simple de combinación: lista de "highlights" útiles para
        un dashboard. Mantenerlo agnóstico al ORM (sólo dicts).
        """
        highlights: list[dict] = []

        consumption = postgres.get('consumption') or []
        if consumption:
            total_spent = sum(float(r['total_usd_spent']) for r in consumption)
            highlights.append({
                'metric': 'total_usd_spent',
                'value':  round(total_spent, 2),
                'unit':   'USD',
                'months_covered': len(consumption),
            })

        s3 = mongo.get('s3')
        if s3 and s3.get('buckets'):
            wasted_buckets = [b for b in s3['buckets']
                              if b.get('waste_percentage', 0) >= 80]
            highlights.append({
                'metric': 's3_wasted_buckets',
                'value':  len(wasted_buckets),
                'detail': [b.get('name') for b in wasted_buckets],
            })

        ec2 = mongo.get('ec2')
        if ec2 and ec2.get('instances'):
            underutilized = [i for i in ec2['instances']
                             if i.get('is_underutilized')]
            highlights.append({
                'metric': 'ec2_underutilized_instances',
                'value':  len(underutilized),
                'detail': [i.get('instance_id') for i in underutilized],
            })

        return highlights
