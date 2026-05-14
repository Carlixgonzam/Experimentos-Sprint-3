#!/bin/bash
# -----------------------------------------------------------------------------
# Setup script for the Application Server (Django) on Ubuntu 24.04 LTS
# -----------------------------------------------------------------------------

set -euo pipefail

echo "========================================================"
echo " Starting Application Server Setup"
echo "========================================================"

# 1. Update and install basic dependencies
echo "=> Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y curl git python3-pip python3-venv libpq-dev

# 2. Install 'uv' (Modern Python package manager)
echo "=> Installing 'uv'..."
curl -LsSf https://astral.sh/uv/install.sh | sh
# Source cargo env to get uv in path immediately
source $HOME/.cargo/env || true

# 3. Setup Project Directory (assuming we are already in the repo or cloning it)
# If this script is run from outside, we might need to clone.
# For now, let's assume we are inside the project root.

echo "=> Installing dependencies with uv..."
uv sync

# 4. Prepare Database Configuration
echo "=> Application setup complete!"
echo "=> NEXT STEP: Run './setups/set-database-ip.sh' to configure your DB connection."
echo "========================================================"
