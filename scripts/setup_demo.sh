#!/usr/bin/env bash
# Creates the first admin user and prints login credentials.
# Usage: bash scripts/setup_demo.sh [EMAIL] [PASSWORD] [FULL_NAME]
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${1:-admin@demo.local}"
PASSWORD="${2:-DemoPass123!}"
FULL_NAME="${3:-Demo Admin}"

echo ""
echo "=== Document Intelligence Platform — Demo Setup ==="
echo ""
echo "Registering admin user: $EMAIL"

RESPONSE=$(curl -sf -X POST "$BASE_URL/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"full_name\":\"$FULL_NAME\"}" \
  2>&1) || {
    echo ""
    echo "Registration failed. The first user may already exist."
    echo "Try logging in at $BASE_URL/login with your existing credentials."
    exit 1
  }

echo ""
echo "=== Admin user created successfully! ==="
echo ""
echo "  URL:       $BASE_URL"
echo "  Email:     $EMAIL"
echo "  Password:  $PASSWORD"
echo "  API Docs:  $BASE_URL/api/docs"
echo ""
echo "Open $BASE_URL in your browser to get started."
echo ""
