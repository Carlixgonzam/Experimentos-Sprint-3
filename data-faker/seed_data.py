"""
Seed de datos para el experimento Sprint 3.

Uso (desde la raíz del repo):

    uv run python data-faker/seed_data.py                         # usa el HOST de credentials.txt
    uv run python data-faker/seed_data.py --host 100.31.110.6     # override del HOST de Postgres
    SEED_EXTRA_COMPANIES=200 uv run python data-faker/seed_data.py --host <ip>

Estrategia:
  - PostgreSQL: ORM de Django (garantiza que el esquema coincide con los modelos).
  - MongoDB: pymongo directo sobre cloud_telemetry.

Empresas predecibles:
  11111111-1111-1111-1111-111111111111  → Nexora Technologies
  22222222-2222-2222-2222-222222222222  → Veridian Systems
  33333333-3333-3333-3333-333333333333  → Arcturus Cloud
  44444444-4444-4444-4444-444444444444  → Luminary Data
"""
import argparse
import os
import sys
import random
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Parsear --host ANTES de tocar Django para poder inyectarlo en el entorno
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description='Seed de bases de datos Sprint-3')
parser.add_argument(
    '--host',
    default=None,
    help='IP o hostname del servidor Postgres (override del valor en credentials.txt)',
)
args = parser.parse_args()

# ---------------------------------------------------------------------------
# Bootstrap Django
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import django  # noqa: E402
django.setup()

from django.conf import settings      # noqa: E402
from django.db import transaction     # noqa: E402
from faker import Faker               # noqa: E402
from pymongo import MongoClient       # noqa: E402

from recolector_inventarios.models import (  # noqa: E402
    Business, ConsumptionSummary, CloudGovernance,
)

# Aplicar override de HOST después de django.setup() — Django ya cargó
# settings pero aún no abrió ninguna conexión, así que esto funciona.
if args.host:
    settings.DATABASES['default']['HOST'] = args.host
    print(f'[config] HOST de Postgres sobreescrito → {args.host}')

fake = Faker('es_CO')

# ---------------------------------------------------------------------------
# Empresas fijas
# ---------------------------------------------------------------------------
EMPRESAS_FIJAS = [
    {
        'id':   uuid.UUID('11111111-1111-1111-1111-111111111111'),
        'name': 'Nexora Technologies',
        'nit':  '900111001-1',
    },
    {
        'id':   uuid.UUID('22222222-2222-2222-2222-222222222222'),
        'name': 'Veridian Systems',
        'nit':  '900222002-2',
    },
    {
        'id':   uuid.UUID('33333333-3333-3333-3333-333333333333'),
        'name': 'Arcturus Cloud',
        'nit':  '900333003-3',
    },
    {
        'id':   uuid.UUID('44444444-4444-4444-4444-444444444444'),
        'name': 'Luminary Data',
        'nit':  '900444004-4',
    },
]

EMPRESAS_ALEATORIAS = int(os.environ.get('SEED_EXTRA_COMPANIES', '300'))

MESES_HISTORICO = (
    [f'2025-{m:02d}' for m in range(6, 13)] +
    [f'2026-{m:02d}' for m in range(1, 6)]
)

# ---------------------------------------------------------------------------
# PostgreSQL — vía ORM Django
# ---------------------------------------------------------------------------

def _build_governance_payload() -> dict:
    return {
        'mandatory_tags': {
            'env':         random.choice(['prod', 'staging', 'dev']),
            'owner':       fake.email(),
            'cost_center': f'CC-{random.randint(100, 999)}',
        },
        'responsible_area': random.choice([
            'Plataforma', 'Datos', 'Producto', 'Infraestructura',
            'Engineering', 'DevOps', 'Security', 'Finance IT',
        ]),
        'spend_limits_by_project': {
            f'proyecto-{i}': float(random.randint(5_000, 50_000))
            for i in range(1, random.randint(2, 5))
        },
    }


@transaction.atomic
def seed_postgres(empresas: list[dict]) -> None:
    print('\n[PG] Limpiando tablas...')
    ConsumptionSummary.objects.all().delete()
    CloudGovernance.objects.all().delete()
    Business.objects.all().delete()

    print(f'[PG] Insertando {len(empresas)} empresas...')
    Business.objects.bulk_create(
        [Business(id_business=e['id'], name=e['name'], nit=e['nit']) for e in empresas],
        batch_size=200,
    )

    consumptions = []
    governances  = []

    for e in empresas:
        gov = _build_governance_payload()
        governances.append(CloudGovernance(
            id_business_id=e['id'],
            mandatory_tags=gov['mandatory_tags'],
            responsible_area=gov['responsible_area'],
            spend_limits_by_project=gov['spend_limits_by_project'],
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

    n_biz  = Business.objects.count()
    n_cons = ConsumptionSummary.objects.count()
    n_gov  = CloudGovernance.objects.count()

    assert n_biz  == len(empresas),                    f'businesses: {n_biz}'
    assert n_cons == len(empresas) * len(MESES_HISTORICO), f'consumption: {n_cons}'
    assert n_gov  == len(empresas),                    f'governance: {n_gov}'

    print(f'[PG] ✅  {n_biz} empresas | {n_cons} registros consumo | {n_gov} gobernanzas')


# ---------------------------------------------------------------------------
# MongoDB — telemetría S3 y EC2
# ---------------------------------------------------------------------------

def _build_s3_doc(business_id: str) -> dict:
    buckets     = []
    total_waste = 0
    for _ in range(random.randint(2, 6)):
        size_gb     = random.randint(50, 5_000)
        unused_days = random.randint(5, 400)
        if unused_days >= 90:
            total_waste += size_gb
        buckets.append({
            'name':             f'{fake.domain_word()}-data',
            'size_gb':          size_gb,
            'unused_days':      unused_days,
            'policy_violations': random.sample(
                ['public-read', 'no-encryption', 'no-versioning'],
                k=random.randint(0, 2),
            ),
            'storage_class':    random.choice(['STANDARD', 'STANDARD_IA', 'GLACIER']),
            'last_access_date': fake.date_between(
                start_date='-1y', end_date='today').isoformat(),
        })
    return {
        'business_id': business_id,
        'service':     'S3',
        'details':     {'buckets': buckets, 'total_waste_gb': total_waste},
    }


def _build_ec2_doc(business_id: str) -> dict:
    instances = []
    for _ in range(random.randint(2, 10)):
        n_logs = random.randint(100, 1_500)
        instances.append({
            'instance_id':         f'i-{uuid.uuid4().hex[:8]}',
            'instance_type':       random.choice(
                ['t3.micro', 't3.small', 'm5.large', 'c5.xlarge']),
            'cpu_utilization_avg': round(random.uniform(1, 95), 1),
            'uptime_logs':         [random.randint(0, 24) for _ in range(n_logs)],
        })
    return {
        'business_id': business_id,
        'service':     'EC2',
        'details':     {'instances': instances},
    }


def seed_mongo(empresas: list[dict]) -> None:
    print(f'\n[Mongo] Conectando → {settings.MONGO_DB_NAME}')
    client = MongoClient(settings.MONGO_URI)
    col    = client[settings.MONGO_DB_NAME]['cloud_telemetry']

    print('[Mongo] Limpiando cloud_telemetry...')
    col.delete_many({})

    docs = []
    for e in empresas:
        bid = str(e['id'])
        docs.append(_build_s3_doc(bid))
        docs.append(_build_ec2_doc(bid))

    print(f'[Mongo] Insertando {len(docs)} documentos...')
    col.insert_many(docs)

    inserted = col.count_documents({})
    expected = len(empresas) * 2
    assert inserted == expected, f'Mongo: {inserted} docs, esperaba {expected}'

    print(f'[Mongo] ✅  {inserted} documentos insertados')
    client.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    random.seed(42)

    empresas = list(EMPRESAS_FIJAS)
    for _ in range(EMPRESAS_ALEATORIAS):
        empresas.append({
            'id':   uuid.uuid4(),
            'name': fake.company(),
            'nit':  f'{random.randint(800_000_000, 999_999_999)}-{random.randint(0, 9)}',
        })

    seed_postgres(empresas)
    seed_mongo(empresas)

    print('\n🎉 Seed terminado. Empresas predecibles:')
    for e in EMPRESAS_FIJAS:
        print(f'   {e["name"]:25s}  {e["id"]}')


if __name__ == '__main__':
    main()