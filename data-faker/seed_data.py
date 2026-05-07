import re
import os
import psycopg2
from pymongo import MongoClient
import uuid
import random
from faker import Faker

fake = Faker('es_CO')

# ---------------------------------------------------------------------------
# Credenciales
# ---------------------------------------------------------------------------

def extract_credentials(filepath="credentials.txt"):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"No se encontró {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    try:
        db_name = re.search(r"'NAME':\s*'([^']+)'", content).group(1)
        db_user = re.search(r"'USER':\s*'([^']+)'", content).group(1)
        db_pass = re.search(r"'PASSWORD':\s*'([^']+)'", content).group(1)
        db_host = re.search(r"'HOST':\s*'([^']+)'", content).group(1)
        db_port = re.search(r"'PORT':\s*'([^']+)'", content).group(1)
        pg_dsn  = f"dbname={db_name} user={db_user} password={db_pass} host={db_host} port={db_port}"
        mongo_uri = re.search(r'MONGO_URI\s*=\s*"([^"]+)"', content).group(1)
        return pg_dsn, mongo_uri
    except AttributeError as e:
        raise ValueError("El formato de credentials.txt no coincide con el esperado.") from e

# ---------------------------------------------------------------------------
# Empresas fijas (4 clientes genéricos de BITE.co)
# ---------------------------------------------------------------------------

EMPRESAS_FIJAS = [
    {
        "id":   "11111111-1111-1111-1111-111111111111",
        "name": "Nexora Technologies",
        "nit":  "900111001-1",
        "governance": {
            "mandatory_tags":          {"env": "prod", "owner": "infra", "cost-center": "ENG-01"},
            "responsible_area":        "Infrastructure Engineering",
            "spend_limits_by_project": {"api-platform": 20000, "data-lake": 15000, "ml-pipeline": 10000},
        },
    },
    {
        "id":   "22222222-2222-2222-2222-222222222222",
        "name": "Veridian Systems",
        "nit":  "900222002-2",
        "governance": {
            "mandatory_tags":          {"env": "staging", "owner": "devops", "cost-center": "OPS-02"},
            "responsible_area":        "DevOps & Reliability",
            "spend_limits_by_project": {"ci-cd": 8000, "monitoring": 5000, "backups": 3000},
        },
    },
    {
        "id":   "33333333-3333-3333-3333-333333333333",
        "name": "Arcturus Cloud",
        "nit":  "900333003-3",
        "governance": {
            "mandatory_tags":          {"env": "prod", "owner": "platform", "cost-center": "PLAT-03"},
            "responsible_area":        "Platform Team",
            "spend_limits_by_project": {"compute": 30000, "storage": 12000, "networking": 8000},
        },
    },
    {
        "id":   "44444444-4444-4444-4444-444444444444",
        "name": "Luminary Data",
        "nit":  "900444004-4",
        "governance": {
            "mandatory_tags":          {"env": "prod", "owner": "data-team", "cost-center": "DATA-04"},
            "responsible_area":        "Data & Analytics",
            "spend_limits_by_project": {"warehouse": 25000, "etl": 10000, "reporting": 5000},
        },
    },
]

MESES = [f"2025-{str(m).zfill(2)}" for m in range(6, 13)] + \
        [f"2026-{str(m).zfill(2)}" for m in range(1, 6)]

AREAS      = ["Engineering", "DevOps", "Data Platform", "Security", "Finance IT", "Product"]
ENVS       = ["prod", "staging", "dev"]
COST_CTRS  = [f"CC-{str(i).zfill(3)}" for i in range(1, 20)]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_governance():
    projects = {fake.slug(): random.randint(2000, 20000) for _ in range(random.randint(2, 5))}
    return {
        "mandatory_tags":          {"env": random.choice(ENVS), "owner": fake.user_name(), "cost-center": random.choice(COST_CTRS)},
        "responsible_area":        random.choice(AREAS),
        "spend_limits_by_project": projects,
    }

def random_s3_doc(business_id: str) -> dict:
    buckets = [
        {
            "name":        fake.domain_word() + "-" + random.choice(["data", "logs", "backup", "assets"]),
            "unused_days": random.randint(0, 400),
            "size_gb":     random.randint(5, 2000),
        }
        for _ in range(random.randint(1, 5))
    ]
    return {
        "business_id": business_id,
        "service":     "S3",
        "details": {
            "total_waste_gb": sum(b["size_gb"] for b in buckets if b["unused_days"] > 90),
            "buckets":        buckets,
        },
    }

def random_ec2_doc(business_id: str) -> dict:
    instances = [
        {
            "instance_id":         f"i-{uuid.uuid4().hex[:8]}",
            "cpu_utilization_avg": random.randint(1, 95),
            "uptime_logs":         [f"up-{h}h" for h in range(random.randint(1, 900))],
        }
        for _ in range(random.randint(2, 10))
    ]
    return {
        "business_id": business_id,
        "service":     "EC2",
        "details":     {"instances": instances},
    }

# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def seed_databases():
    print("🔍 Parseando credentials.txt...")
    PG_DSN, MONGO_URI = extract_credentials()

    print("🔌 Conectando a bases de datos...")
    pg_conn   = psycopg2.connect(PG_DSN)
    pg_cursor = pg_conn.cursor()
    mongo_client   = MongoClient(MONGO_URI)
    mongo_db       = mongo_client["bite_telemetry"]
    cloud_telemetry = mongo_db["cloud_telemetry"]

    # -----------------------------------------------------------------------
    # FASE 1 — Limpiar todo y crear esquema desde cero
    # -----------------------------------------------------------------------
    print("\n🧹 Fase 1: Limpiando y recreando esquema...")

    pg_cursor.execute("""
        DROP TABLE IF EXISTS cloud_governance   CASCADE;
        DROP TABLE IF EXISTS consumption_summary CASCADE;
        DROP TABLE IF EXISTS businesses          CASCADE;

        CREATE TABLE businesses (
            id_business UUID PRIMARY KEY,
            name        VARCHAR(255) NOT NULL,
            nit         VARCHAR(20)  NOT NULL UNIQUE
        );

        CREATE TABLE consumption_summary (
            id              SERIAL PRIMARY KEY,
            id_business     UUID REFERENCES businesses(id_business),
            month_year      VARCHAR(7)      NOT NULL,
            total_usd_spent DECIMAL(12, 2)  NOT NULL
        );

        CREATE TABLE cloud_governance (
            id_business          UUID PRIMARY KEY REFERENCES businesses(id_business),
            mandatory_tags       JSONB NOT NULL DEFAULT '{}',
            responsible_area     VARCHAR(255) NOT NULL,
            spend_limits_by_project JSONB NOT NULL DEFAULT '{}'
        );
    """)
    pg_conn.commit()
    cloud_telemetry.delete_many({})
    print("   ✅ Esquema Postgres recreado y Mongo limpio.")

    # -----------------------------------------------------------------------
    # FASE 2 — Verificar conectividad y esquema antes de insertar
    # -----------------------------------------------------------------------
    print("\n🔎 Fase 2: Verificando conectividad y esquema...")

    pg_cursor.execute("SELECT COUNT(*) FROM businesses;")
    assert pg_cursor.fetchone()[0] == 0, "businesses debería estar vacía"

    pg_cursor.execute("SELECT COUNT(*) FROM consumption_summary;")
    assert pg_cursor.fetchone()[0] == 0, "consumption_summary debería estar vacía"

    pg_cursor.execute("SELECT COUNT(*) FROM cloud_governance;")
    assert pg_cursor.fetchone()[0] == 0, "cloud_governance debería estar vacía"

    assert cloud_telemetry.count_documents({}) == 0, "cloud_telemetry debería estar vacía"

    # Verificar que las columnas esperadas existen
    pg_cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'consumption_summary'
        ORDER BY ordinal_position;
    """)
    cols = [r[0] for r in pg_cursor.fetchall()]
    for expected in ("id", "id_business", "month_year", "total_usd_spent"):
        assert expected in cols, f"Columna '{expected}' no encontrada en consumption_summary"

    pg_cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'cloud_governance'
        ORDER BY ordinal_position;
    """)
    cols = [r[0] for r in pg_cursor.fetchall()]
    for expected in ("id_business", "mandatory_tags", "responsible_area", "spend_limits_by_project"):
        assert expected in cols, f"Columna '{expected}' no encontrada en cloud_governance"

    print("   ✅ Todas las tablas y columnas verificadas correctamente.")

    # -----------------------------------------------------------------------
    # FASE 3 — Construir lista completa de empresas
    # -----------------------------------------------------------------------
    print("\n🏗️  Fase 3: Preparando empresas...")

    TOTAL_EXTRA = 300
    empresas_extra = [
        {
            "id":         str(uuid.uuid4()),
            "name":       fake.company(),
            "nit":        f"{random.randint(800000000, 999999999)}-{random.randint(0, 9)}",
            "governance": random_governance(),
        }
        for _ in range(TOTAL_EXTRA)
    ]

    todas = EMPRESAS_FIJAS + empresas_extra
    print(f"   Total empresas a insertar: {len(todas)} (4 fijas + {TOTAL_EXTRA} aleatorias)")

    # -----------------------------------------------------------------------
    # FASE 4 — Insertar con auditorías intermedias cada 50 empresas
    # -----------------------------------------------------------------------
    print("\n🚀 Fase 4: Insertando datos...\n")

    LOTE = 50
    for i, emp in enumerate(todas, start=1):
        b_id = emp["id"]
        gov  = emp["governance"]

        # Postgres — businesses
        pg_cursor.execute(
            "INSERT INTO businesses (id_business, name, nit) VALUES (%s, %s, %s)",
            (b_id, emp["name"], emp["nit"])
        )

        # Postgres — consumption_summary (un año de historial)
        for mes in MESES:
            pg_cursor.execute(
                "INSERT INTO consumption_summary (id_business, month_year, total_usd_spent) VALUES (%s, %s, %s)",
                (b_id, mes, round(random.uniform(1000.0, 50000.0), 2))
            )

        # Postgres — cloud_governance
        import json
        pg_cursor.execute(
            """INSERT INTO cloud_governance
               (id_business, mandatory_tags, responsible_area, spend_limits_by_project)
               VALUES (%s, %s, %s, %s)""",
            (
                b_id,
                json.dumps(gov["mandatory_tags"]),
                gov["responsible_area"],
                json.dumps(gov["spend_limits_by_project"]),
            )
        )

        # Mongo — S3 y EC2
        cloud_telemetry.insert_many([
            random_s3_doc(b_id),
            random_ec2_doc(b_id),
        ])

        # Auditoría cada LOTE empresas
        if i % LOTE == 0:
            pg_conn.commit()

            pg_cursor.execute("SELECT COUNT(*) FROM businesses;")
            n_biz = pg_cursor.fetchone()[0]

            pg_cursor.execute("SELECT COUNT(*) FROM consumption_summary;")
            n_cons = pg_cursor.fetchone()[0]

            pg_cursor.execute("SELECT COUNT(*) FROM cloud_governance;")
            n_gov = pg_cursor.fetchone()[0]

            n_mongo = cloud_telemetry.count_documents({})

            print(f"   ✅ Lote {i}/{len(todas)} — "
                  f"businesses={n_biz} | consumption={n_cons} | governance={n_gov} | mongo={n_mongo}")

            assert n_biz  == i,     f"businesses: esperaba {i}, tengo {n_biz}"
            assert n_gov  == i,     f"cloud_governance: esperaba {i}, tengo {n_gov}"
            assert n_mongo == i * 2, f"mongo: esperaba {i*2}, tengo {n_mongo}"

    pg_conn.commit()

    # -----------------------------------------------------------------------
    # FASE 5 — Verificación final
    # -----------------------------------------------------------------------
    print("\n🔎 Fase 5: Verificación final...")

    pg_cursor.execute("SELECT COUNT(*) FROM businesses;")
    n_biz = pg_cursor.fetchone()[0]

    pg_cursor.execute("SELECT COUNT(*) FROM consumption_summary;")
    n_cons = pg_cursor.fetchone()[0]

    pg_cursor.execute("SELECT COUNT(*) FROM cloud_governance;")
    n_gov = pg_cursor.fetchone()[0]

    n_mongo = cloud_telemetry.count_documents({})

    assert n_biz == len(todas),          f"businesses: {n_biz} vs {len(todas)}"
    assert n_cons == len(todas) * len(MESES), f"consumption_summary: {n_cons}"
    assert n_gov == len(todas),          f"cloud_governance: {n_gov} vs {len(todas)}"
    assert n_mongo == len(todas) * 2,    f"mongo: {n_mongo} vs {len(todas)*2}"

    print(f"   ✅ businesses:         {n_biz}")
    print(f"   ✅ consumption_summary: {n_cons}")
    print(f"   ✅ cloud_governance:    {n_gov}")
    print(f"   ✅ mongo docs:          {n_mongo}")

    pg_cursor.close()
    pg_conn.close()
    mongo_client.close()

    print("\n🎉 ¡Todo listo! Empresas fijas disponibles:")
    for emp in EMPRESAS_FIJAS:
        print(f"   - {emp['name']}: {emp['id']}")

if __name__ == "__main__":
    seed_databases()