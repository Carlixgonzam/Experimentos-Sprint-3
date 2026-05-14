#!/bin/bash
# -----------------------------------------------------------------------------
# Configuration script to set the Database IP in settings.py
# -----------------------------------------------------------------------------

set -euo pipefail

SETTINGS_FILE="settings.py"

echo "========================================================"
echo " Database Configuration Wizard"
echo "========================================================"

# Ask for the IP Address
read -p "Enter the IP address of your Database Server: " DB_IP

if [[ -z "$DB_IP" ]]; then
    echo "Error: IP address cannot be empty."
    exit 1
fi

echo "=> Updating $SETTINGS_FILE with IP: $DB_IP"

# Backup settings.py before modifying
cp "$SETTINGS_FILE" "${SETTINGS_FILE}.bak"

# Use sed to update the HOST in DATABASES
# We look for 'HOST': '...' and replace the value
sed -i "s/'HOST': '[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}'/'HOST': '$DB_IP'/g" "$SETTINGS_FILE"

# Use sed to update the IP in MONGO_URI
# We look for @IP:27017 and replace it
sed -i "s/@[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}:27017/@$DB_IP:27017/g" "$SETTINGS_FILE"

echo "=> Settings updated successfully!"
echo "=> Running migrations..."
# Assuming uv is installed and we are in the environment
if command -v uv &> /dev/null; then
    uv run python manage.py migrate
else
    python3 manage.py migrate
fi

echo "========================================================"
echo " Configuration complete! You can now start the server with:"
echo " uv run python manage.py runserver 0.0.0.0:8000"
echo "========================================================"
