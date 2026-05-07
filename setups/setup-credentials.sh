#!/bin/bash
# -----------------------------------------------------------------------------
# Script para crear bases de datos, usuarios y generar config para Django
# -----------------------------------------------------------------------------

set -euo pipefail

# === 1. DEFINICIÓN DE CREDENCIALES (Principio KISS) ===
PG_DB="bite_db"
PG_USER="bite_user"
PG_PASS="Bite_KISS_2026!"

MONGO_DB="bite_telemetry"
MONGO_USER="bite_mongo_user"
MONGO_PASS="Mongo_KISS_2026!"

echo "=> Configurando PostgreSQL..."
# Crear base de datos y usuario en Postgres
sudo -u postgres psql -c "CREATE DATABASE $PG_DB;" || true
sudo -u postgres psql -c "CREATE USER $PG_USER WITH PASSWORD '$PG_PASS';" || true
sudo -u postgres psql -c "ALTER ROLE $PG_USER SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE $PG_USER SET default_transaction_isolation TO 'read committed';"
sudo -u postgres psql -c "ALTER ROLE $PG_USER SET timezone TO 'UTC';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $PG_DB TO $PG_USER;"
sudo -u postgres psql -d $PG_DB -c "GRANT ALL ON SCHEMA public TO $PG_USER;"

echo "=> Configurando MongoDB..."
# Crear usuario y base de datos en MongoDB
mongosh $MONGO_DB --eval "
  db.createUser({
    user: '$MONGO_USER',
    pwd: '$MONGO_PASS',
    roles: [{ role: 'readWrite', db: '$MONGO_DB' }]
  })
"

# === 2. GENERAR SALIDA PARA DJANGO ===
echo ""
echo "========================================================"
echo " BASES DE DATOS CREADAS CON ÉXITO"
echo " COPIA Y PEGA ESTO EN TU config.py o settings.py:"
echo "========================================================"
cat << EOF

# --- PostgreSQL (Datos Relacionales y Financieros) ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': '$PG_DB',
        'USER': '$PG_USER',
        'PASSWORD': '$PG_PASS',
        'HOST': '127.0.0.1',  # Cambia esto por la IP privada de EC2 si tu API está en otra máquina
        'PORT': '5432',
    }
}

# --- MongoDB (Datos Documentales y Telemetría) ---
# URI de conexión para tu MongoConnector (usando PyMongo o Motor)
MONGO_URI = "mongodb://$MONGO_USER:$MONGO_PASS@127.0.0.1:27017/$MONGO_DB?authSource=$MONGO_DB"
MONGO_DB_NAME = "$MONGO_DB"

EOF
echo "========================================================"