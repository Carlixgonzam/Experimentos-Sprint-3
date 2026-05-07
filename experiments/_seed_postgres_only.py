"""
Seed minimalista de Postgres solamente — para correr los experimentos
y los tests del recolector cuando NO hay Mongo accesible.

Uso (con DJANGO_SETTINGS_MODULE apuntando a settings_test):
    python experiments/_seed_postgres_only.py

Carga las 4 empresas con UUIDs predecibles que esperan tanto los tests
de Felipe (nexora/veridian/arcturus/luminary) como los experimentos.
"""
import os
import sys
import uuid
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings_test')
django.setup()

from django.db import transaction  # noqa: E402
from recolector_inventarios.models import (  # noqa: E402
    Business, ConsumptionSummary, CloudGovernance,
)

EMPRESAS = [
    (uuid.UUID('11111111-1111-1111-1111-111111111111'), 'Nexora',   '860007386-1'),
    (uuid.UUID('22222222-2222-2222-2222-222222222222'), 'Veridian', '901234567-8'),
    (uuid.UUID('33333333-3333-3333-3333-333333333333'), 'Arcturus', '900000000-1'),
    (uuid.UUID('44444444-4444-4444-4444-444444444444'), 'Luminary', '900000000-2'),
]

MESES = ['2026-03', '2026-04', '2026-05']


@transaction.atomic
def main() -> None:
    print('Limpiando tablas...')
    ConsumptionSummary.objects.all().delete()
    CloudGovernance.objects.all().delete()
    Business.objects.all().delete()

    for bid, name, nit in EMPRESAS:
        b = Business.objects.create(id_business=bid, name=name, nit=nit)
        CloudGovernance.objects.create(
            id_business=b,
            mandatory_tags={'env': 'prod', 'owner': f'{name.lower()}@bite.co'},
            responsible_area='Plataforma',
            spend_limits_by_project={'p1': 5000.0, 'p2': 12000.0},
        )
        for m in MESES:
            ConsumptionSummary.objects.create(
                id_business=b,
                month_year=m,
                total_usd_spent=1500.50 + (MESES.index(m) * 100),
                currency='USD',
                assigned_budget=2000.00,
                payment_status='paid',
            )
    print(f'OK — {Business.objects.count()} empresas, '
          f'{ConsumptionSummary.objects.count()} registros, '
          f'{CloudGovernance.objects.count()} governance.')


if __name__ == '__main__':
    main()
