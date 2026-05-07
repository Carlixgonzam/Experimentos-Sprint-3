import re
import os
import time
import psycopg2
from pymongo import MongoClient
import uuid
import random
from faker import Faker

fake = Faker('es_CO')

def extract_credentials(filepath="credentials.txt"):
    """Parsea el archivo txt para extraer el DSN de Postgres y la URI de Mongo."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"¡No se encontró el archivo {filepath}! Crea el archivo con el output del bash script.")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        # Extraer credenciales Postgres usando Regex
        db_name = re.search(r"'NAME':\s*'([^']+)'", content).group(1)
        db_user = re.search(r"'USER':\s*'([^']+)'", content).group(1)
        db_pass = re.search(r"'PASSWORD':\s*'([^']+)'", content).group(1)
        db_host = re.search(r"'HOST':\s*'([^']+)'", content).group(1)
        db_port = re.search(r"'PORT':\s*'([^']+)'", content).group(1)
        
        pg_dsn = f"dbname={db_name} user={db_user} password={db_pass} host={db_host} port={db_port}"
        
        # Extraer credencial Mongo
        mongo_uri = re.search(r'MONGO_URI\s*=\s*"([^"]+)"', content).group(1)
        
        return pg_dsn, mongo_uri
    except AttributeError as e:
        raise ValueError("El formato de credentials.txt no coincide con el esperado.") from e

def seed_databases():
    print("🔍 Parseando credentials.txt...")
    PG_DSN, MONGO_URI = extract_credentials()
    
    print("🔌 Conectando a bases de datos...")
    pg_conn = psycopg2.connect(PG_DSN)
    pg_cursor = pg_conn.cursor()
    
    mongo_client = MongoClient(MONGO_URI)
    mongo_db = mongo_client["bite_telemetry"]
    cloud_telemetry = mongo_db["cloud_telemetry"]
    
    print("🧹 Preparando y limpiando tablas en Postgres...")
    # Crear las tablas desde cero si no existen, o reiniciarlas si ya existen
    pg_cursor.execute("""
        DROP TABLE IF EXISTS consumption_summary CASCADE;
        DROP TABLE IF EXISTS businesses CASCADE;

        CREATE TABLE businesses (
            id_business UUID PRIMARY KEY,
            name VARCHAR(255),
            nit VARCHAR(20)
        );

        CREATE TABLE consumption_summary (
            id SERIAL PRIMARY KEY,
            id_business UUID REFERENCES businesses(id_business),
            month_year VARCHAR(7),
            total_usd_spent DECIMAL(12, 2)
        );
    """)
    
    print("🧹 Limpiando colecciones en Mongo...")
    cloud_telemetry.delete_many({})
    
    # ==========================================
    # 1. DEFINIR 4 EMPRESAS PREDECIBLES
    # ==========================================
    empresas_fijas = [
        {"id": "11111111-1111-1111-1111-111111111111", "name": "Universidad de los Andes", "nit": "860007386-1"},
        {"id": "22222222-2222-2222-2222-222222222222", "name": "BITE.co (Interno)", "nit": "901234567-8"},
        {"id": "33333333-3333-3333-3333-333333333333", "name": "Routask AI", "nit": "900000000-1"},
        {"id": "44444444-4444-4444-4444-444444444444", "name": "RAS Robotics SWARM", "nit": "900000000-2"},
    ]
    
    # ==========================================
    # 2. GENERAR CIENTOS DE EMPRESAS ALEATORIAS
    # ==========================================
    TOTAL_EMPRESAS_EXTRA = 300
    todas_las_empresas = empresas_fijas.copy()
    
    for _ in range(TOTAL_EMPRESAS_EXTRA):
        todas_las_empresas.append({
            "id": str(uuid.uuid4()),
            "name": fake.company(),
            "nit": f"{random.randint(800000000, 999999999)}-{random.randint(0, 9)}"
        })

    print(f"🚀 Iniciando inyección de {len(todas_las_empresas)} empresas...")
    
    meses_historico = [f"2025-{str(m).zfill(2)}" for m in range(6, 13)] + [f"2026-{str(m).zfill(2)}" for m in range(1, 6)]
    
    contador_insertados = 0
    lote_size = 50  # Cada cuántas empresas hacemos comprobación
    
    for emp in todas_las_empresas:
        b_id = emp["id"]
        
        # --- A. INSERTAR EN POSTGRES ---
        pg_cursor.execute(
            "INSERT INTO businesses (id_business, name, nit) VALUES (%s, %s, %s)",
            (b_id, emp["name"], emp["nit"])
        )
        
        # Generar un año de historiales financieros en Postgres
        for mes in meses_historico:
            gasto = round(random.uniform(1000.0, 50000.0), 2)
            pg_cursor.execute(
                "INSERT INTO consumption_summary (id_business, month_year, total_usd_spent) VALUES (%s, %s, %s)",
                (b_id, mes, gasto)
            )
            
        # --- B. INSERTAR EN MONGO (Varios documentos por empresa) ---
        docs_mongo = [
            {
                "business_id": b_id,
                "service": "S3",
                "details": {
                    "total_waste_gb": random.randint(100, 5000),
                    "buckets": [{"name": fake.domain_word() + "-data", "unused_days": random.randint(30, 400)}]
                }
            },
            {
                "business_id": b_id,
                "service": "EC2",
                "details": {
                    "instances": [{"instance_id": f"i-{uuid.uuid4().hex[:8]}", "cpu_utilization_avg": random.randint(1, 80)} for _ in range(random.randint(2, 10))]
                }
            }
        ]
        cloud_telemetry.insert_many(docs_mongo)
        
        contador_insertados += 1
        
        # ==========================================
        # 3. COMPROBACIONES PERIÓDICAS (Auditoría en vivo)
        # ==========================================
        if contador_insertados % lote_size == 0:
            pg_conn.commit() # Asegurar que Postgres guarde el lote
            
            # Comprobación Postgres
            pg_cursor.execute("SELECT COUNT(*) FROM businesses;")
            pg_b_count = pg_cursor.fetchone()[0]
            
            pg_cursor.execute("SELECT COUNT(*) FROM consumption_summary;")
            pg_c_count = pg_cursor.fetchone()[0]
            
            # Comprobación Mongo
            mongo_docs = cloud_telemetry.count_documents({})
            
            print(f"✅ Lote {contador_insertados}/{len(todas_las_empresas)} completado.")
            print(f"   📊 Auditoría Parcial -> Postgres: {pg_b_count} Empresas, {pg_c_count} Registros | Mongo: {mongo_docs} Documentos")
            
            # Validar integridad: Los docs en Mongo deben ser el doble de las empresas (porque insertamos S3 y EC2)
            assert mongo_docs == pg_b_count * 2, "¡Alerta! Inconsistencia detectada entre Postgres y Mongo"

    pg_conn.commit()
    pg_cursor.close()
    pg_conn.close()
    mongo_client.close()
    
    print("\n🎉 ¡Población de datos y comprobaciones finalizadas con éxito!")
    print("Empresas predecibles listas para probar en tus endpoints:")
    for emp in empresas_fijas:
        print(f" - {emp['name']}: {emp['id']}")

if __name__ == "__main__":
    seed_databases()