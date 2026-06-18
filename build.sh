#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────
#  build.sh — Render build hook for LogiControl India SaaS
#
#  Executed automatically by Render on every deploy.
#  Connects the Django runtime to TiDB Cloud Serverless
#  (MySQL wire-protocol over port 4000 with TLS).
# ────────────────────────────────────────────────────────────
set -o errexit   # abort on any non-zero exit
set -o pipefail  # catch failures inside piped commands

echo "══════════════════════════════════════════════"
echo "  LogiControl Build Pipeline — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "══════════════════════════════════════════════"

# ── 1. System-level dependencies ──────────────────────────
# mysqlclient requires libmysqlclient-dev and pkg-config
# on Render's Ubuntu-based build image.
echo ""
echo "▸ Step 1/4 — Installing system packages for mysqlclient..."
apt-get update -qq && apt-get install -y -qq \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    > /dev/null 2>&1
echo "  ✓ System packages installed"

# ── 2. Python dependencies ────────────────────────────────
echo ""
echo "▸ Step 2/4 — Installing Python dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  ✓ Python packages installed"

# ── 3. Static file collection ─────────────────────────────
# WhiteNoise serves these from STATIC_ROOT in production.
echo ""
echo "▸ Step 3/4 — Collecting static assets..."
python backend/manage.py collectstatic --no-input --clear
echo "  ✓ Static files collected to 'staticfiles/'"

# ── 4. Database migrations ────────────────────────────────
# Runs against TiDB Cloud Serverless via DATABASE_URL env var.
# Skipped gracefully if DATABASE_URL is not yet configured.
echo ""
echo "▸ Step 4/4 — Applying migrations to TiDB Cloud Serverless..."
if [ -z "${DATABASE_URL}" ]; then
    echo "  ⚠ DATABASE_URL is not set — skipping migrations."
    echo "    Set DATABASE_URL in Render → Environment and redeploy."
else
    python backend/manage.py migrate --no-input
    echo "  ✓ Migrations applied to TiDB Cloud"
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  Build complete ✓"
echo "══════════════════════════════════════════════"
