"""
Seed de datos para el experimento Sprint 3.

Estrategia:
  - PostgreSQL: poblamos vía ORM de Django para garantizar que el esquema
    coincide con `recolector_inventarios/models.py` (incluye CloudGovernance,
    payment_status, currency, assigned_budget, etc.).
  - MongoDB: poblamos `cloud_telemetry` con la estructura que esperan
    `S3UsageService` y `EC2UsageService` (buckets con size_gb / unused_days /
    policy_violations / storage_class / last_access_date; instances con
    cpu_utilization_avg / uptime_logs).

Cómo correrlo (desde la raíz del repo):

    python data-faker/seed_data.py

Lee credenciales desde `settings.py` en la raíz del repo (las mismas que
usa `manage.py`).

Crea 4 empresas predecibles (UUIDs all-1s, all-2s, etc.) más N empresas
aleatorias para que tengas un set estable que probar a mano:

  - 11111111-1111-1111-1111-111111111111  → Universidad de los Andes
  - 22222222-2222-2222-2222-222222222222  → BITE.co (Interno)
  - 33333333-3333-3333-3333-333333333333  → Routask AI
  - 44444444-4444-4444-4444-444444444444  → RAS Robotics SWARM
"""
import os
import sys
import random
import uuid
from pathlib import Path

import django

# Bootstrap Django desde un script que vive fuera de manage.py
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.conf import settings  # noqa: E402
from django.db import transaction  # noqa: E402
from faker import Faker  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from recolector_inventarios.models import (  # noqa: E402
    Business, ConsumptionSummary, CloudGovernance,
)

fake = Faker('es_CO')

# ---------------------------------------------------------------------------
# Configuración del seed
# ---------------------------------------------------------------------------
EMPRESAS_FIJAS = [
    {'id': uuid.UUID('11111111-1111-1111-1111-111111111111'),
     'name': 'Universidad de los Andes', 'nit': '860007386-1'},
    {'id': uuid.UUID('22222222-2222-2222-2222-222222222222'),
     'name': 'BITE.co (Interno)',       'nit': '901234567-8'},
    {'id': uuid.UUID('33333333-3333-3333-3333-333333333333'),
     'name': 'Routask AI',              'nit': '900000000-1'},
    {'id': uuid.UUID('44444444-4444-4444-4444-444444444444'),
     'name': 'RAS Robotics SWARM',      'nit': '900000000-2'},
]
EMPRESAS_ALEATORIAS = int(os.environ.get('SEED_EXTRA_COMPANIES', '50'))
MESES_HISTORICO = (
    [f'2025-{m:02d}' for m in range(6, 13)] +
    [f'2026-{m:02d}' for m in range(1, 6)]
)


# ---------------------------------------------------------------------------
# Postgres (ORM Django)
# ---------------------------------------------------------------------------

def _build_governance_payload() -> dict:
    """Genera tags y límites por proyecto plausibles."""
    return {
        'mandatory_tags': {
            'env':   random.choice(['prod', 'staging', 'dev']),
            'owner': fake.email(),
            'cost_center': f'CC-{random.randint(100, 999)}',
        },
        'responsible_area': random.choice([
            'Plataforma', 'Datos', 'Producto', 'Infraestructura',
        ]),
        'spend_limits_by_project': {
            f'proyecto-{i}': float(random.randint(5_000, 50_000))
            for i in range(1, random.randint(2, 5))
        },
    }


@transaction.atomic
def seed_postgres(empresas: list[dict]) -> None:
    print('[PG] Limpiando tablas...')
    ConsumptionSummary.objects.all().delete()
    CloudGovernance.objects.all().delete()
    Business.objects.all().delete()

    print(f'[PG] Insertando {len(empresas)} empresas + histórico financiero...')
    businesses = [
        Business(id_business=e['id'], name=e['name'], nit=e['nit'])
        for e in empresas
    ]
    Business.objects.bulk_create(businesses, batch_size=200)

    consumptions = []
    governances  = []
    for e in empresas:
        gov_payload = _build_governance_payload()
        governances.append(CloudGovernance(
            id_business_id=e['id'],
            mandatory_tags=gov_payload['mandatory_tags'],
            responsible_area=gov_payload['responsible_area'],
            spend_limits_by_project=gov_payload['spend_limits_by_project'],
        ))
        for mes in MESES_HISTORICO:
            spent  = round(random.uniform(1_000.0, 50_000.0), 2)
            budget = round(spent * random.uniform(0.7, 1.3), 2)
            consumptions.append(ConsumptionSummary(
                id_business_id=e['id'],
                month_year=mes,
                total_usd_spent=spent,
                currency='USD',
                assigned_budget=budget,
                payment_status=random.choice(['pending', 'paid', 'overdue']),
            ))

    CloudGovernance.objects.bulk_create(governances, batch_size=200)
    ConsumptionSummary.objects.bulk_create(consumptions, batch_size=500)

    print(f'[PG] OK — {Business.objects.count()} empresas, '
          f'{ConsumptionSummary.objects.count()} registros de consumo, '
          f'{CloudGovernance.objects.count()} configs de gobernanza.')


# ---------------------------------------------------------------------------
# Mongo (telemetría)
# ---------------------------------------------------------------------------

def _build_s3_doc(business_id: str) -> dict:
    n_buckets = random.randint(2, 6)
    buckets = []
    total_waste = 0
    for _ in range(n_buckets):
        size_gb     = random.randint(50, 5_000)
        unused_days = random.randint(5, 400)
        if unused_days >= 90:
            total_waste += size_gb
        buckets.append({
            'name': f'{fake.domain_word()}-data',
            'size_gb': size_gb,
            'unused_days': unused_days,
            'policy_violations': random.sample(
                ['public-read', 'no-encryption', 'no-versioning'],
                k=random.randint(0, 2),
            ),
            'storage_class': random.choice(
                ['STANDARD', 'STANDARD_IA', 'GLACIER']),
            'last_access_date': fake.date_between(
                start_date='-1y', end_date='today').isoformat(),
        })
    return {
        'business_id': business_id,
        'service':     'S3',
        'details': {
            'buckets':         buckets,
            'total_waste_gb':  total_waste,
        },
    }


def _build_ec2_doc(business_id: str) -> dict:
    n_instances = random.randint(2, 10)
    instances = []
    for _ in range(n_instances):
        cpu_avg = round(random.uniform(1, 95), 1)
        n_logs  = random.randint(100, 1_500)
        instances.append({
            'instance_id':         f'i-{uuid.uuid4().hex[:8]}',
            'instance_type':       random.choice(
                ['t3.micro', 't3.small', 'm5.large', 'c5.xlarge']),
            'cpu_utilization_avg': cpu_avg,
            'uptime_logs':         [random.randint(0, 24) for _ in range(n_logs)],
        })
    return {
        'business_id': business_id,
        'service':     'EC2',
        'details': {
            'instances': instances,
        },
    }


def seed_mongo(empresas: list[dict]) -> None:
    print(f'[Mongo] Conectando a {settings.MONGO_URI} → {settings.MONGO_DB_NAME}')
    client = MongoClient(settings.MONGO_URI)
    col    = client[settings.MONGO_DB_NAME]['cloud_telemetry']

    print('[Mongo] Limpiando cloud_telemetry...')
    col.delete_many({})

    docs: list[dict] = []
    for e in empresas:
        bid = str(e['id'])
        docs.append(_build_s3_doc(bid))
        docs.append(_build_ec2_doc(bid))

    print(f'[Mongo] Insertando {len(docs)} documentos...')
    col.insert_many(docs)

    inserted = col.count_documents({})
    expected = len(empresas) * 2
    if inserted != expected:
        raise AssertionError(
            f'Inconsistencia: {inserted} docs en Mongo, esperaba {expected}'
        )
    print(f'[Mongo] OK — {inserted} documentos.')

    client.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    random.seed(42)  # determinismo para que los experimentos sean reproducibles

    empresas = list(EMPRESAS_FIJAS)
    for _ in range(EMPRESAS_ALEATORIAS):
        empresas.append({
            'id':   uuid.uuid4(),
            'name': fake.company(),
            'nit':  f'{random.randint(800_000_000, 999_999_999)}-{random.randint(0, 9)}',
        })

    seed_postgres(empresas)
    seed_mongo(empresas)

    print('\nSeed terminado. Empresas predecibles para tus pruebas:')
    for e in EMPRESAS_FIJAS:
        print(f'  - {e["name"]:30s}  {e["id"]}')


if __name__ == '__main__':
    main()
