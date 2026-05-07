#!/bin/bash
# -----------------------------------------------------------------------------
# Setup script for PostgreSQL & MongoDB on Ubuntu 24.04 LTS (Noble Numbat)
# -----------------------------------------------------------------------------

# Fail immediately on errors or unbound variables
set -euo pipefail

# Prevent interactive prompts from halting the script (critical for EC2)
export DEBIAN_FRONTEND=noninteractive

echo "========================================================"
echo " Starting Database Setup: PostgreSQL & MongoDB"
echo "========================================================"

# 1. Defeat the apt lock issue (waits for background EC2 updates to finish)
echo "=> Checking for apt locks..."
while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 ; do
    echo "Waiting for unattended-upgrades to release apt lock..."
    sleep 5
done

# 2. System Update & Prerequisites
echo "=> Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y curl gnupg software-properties-common apt-transport-https

# 3. PostgreSQL Installation
# Ubuntu 24.04 includes PostgreSQL (v16) in its default repositories.
echo "=> Installing PostgreSQL..."
sudo apt-get install -y postgresql postgresql-contrib

echo "=> Starting and enabling PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 4. MongoDB Installation 
# Ubuntu 24.04 requires the official MongoDB 8.0 repository
echo "=> Importing MongoDB GPG key..."
curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | \
    sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor --yes

echo "=> Adding MongoDB APT repository for Noble..."
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list > /dev/null

echo "=> Installing MongoDB..."
sudo apt-get update -y
sudo apt-get install -y mongodb-org

echo "=> Starting and enabling MongoDB..."
sudo systemctl start mongod
sudo systemctl enable mongod

echo "========================================================"
echo " Setup Complete! "
echo "========================================================"