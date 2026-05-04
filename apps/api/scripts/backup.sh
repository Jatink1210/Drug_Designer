#!/usr/bin/env bash
# ─── DrugSynth Workbench — Automated Backup Script (§60.4) ──────────
# Schedule: pg_dump every 6 h, Qdrant snapshots daily, Neo4j dump daily.
# Retention: PostgreSQL 30 days, Qdrant 14 days, Neo4j 14 days.
# Usage: crontab -e
#   0 */6 * * *  /path/to/backup.sh pg
#   0 2   * * *  /path/to/backup.sh qdrant
#   0 3   * * *  /path/to/backup.sh neo4j
#   0 4   * * *  /path/to/backup.sh prune
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/backups}"
TIMESTAMP="$(date +%Y%m%dT%H%M%S)"

PG_RETAIN_DAYS=30
QDRANT_RETAIN_DAYS=14
NEO4J_RETAIN_DAYS=14

# ── PostgreSQL ──────────────────────────────────────────────
backup_pg() {
  local dest="${BACKUP_ROOT}/postgres"
  mkdir -p "${dest}"
  local file="${dest}/pg_${TIMESTAMP}.sql.gz"
  PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD not set}" \
    pg_dump -h "${POSTGRES_HOST:-postgres}" \
            -U "${POSTGRES_USER:?POSTGRES_USER not set}" \
            -d "${POSTGRES_DB:-drugdesigner}" \
            --no-owner --clean --if-exists \
    | gzip > "${file}"
  echo "[backup] PostgreSQL → ${file}"
}

# ── Qdrant ──────────────────────────────────────────────────
backup_qdrant() {
  local dest="${BACKUP_ROOT}/qdrant"
  mkdir -p "${dest}"
  local qdrant_url="http://${QDRANT_HOST:-qdrant}:${QDRANT_PORT:-6333}"
  # List all collections and snapshot each
  collections=$(curl -sf "${qdrant_url}/collections" | python3 -c \
    "import sys,json; [print(c['name']) for c in json.load(sys.stdin)['result']['collections']]")
  for col in ${collections}; do
    snap=$(curl -sf -X POST "${qdrant_url}/collections/${col}/snapshots" \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['name'])")
    curl -sf -o "${dest}/${col}_${TIMESTAMP}.snapshot" \
      "${qdrant_url}/collections/${col}/snapshots/${snap}"
    # Clean up remote snapshot
    curl -sf -X DELETE "${qdrant_url}/collections/${col}/snapshots/${snap}" > /dev/null
    echo "[backup] Qdrant/${col} → ${dest}/${col}_${TIMESTAMP}.snapshot"
  done
}

# ── Neo4j ───────────────────────────────────────────────────
backup_neo4j() {
  local dest="${BACKUP_ROOT}/neo4j"
  mkdir -p "${dest}"
  local file="${dest}/neo4j_${TIMESTAMP}.dump"
  docker exec neo4j neo4j-admin database dump neo4j --to-stdout > "${file}"
  gzip "${file}"
  echo "[backup] Neo4j → ${file}.gz"
}

# ── Prune ───────────────────────────────────────────────────
prune() {
  echo "[prune] Removing backups older than retention policy..."
  find "${BACKUP_ROOT}/postgres" -name "pg_*.sql.gz" -mtime "+${PG_RETAIN_DAYS}" -delete 2>/dev/null || true
  find "${BACKUP_ROOT}/qdrant" -name "*.snapshot" -mtime "+${QDRANT_RETAIN_DAYS}" -delete 2>/dev/null || true
  find "${BACKUP_ROOT}/neo4j" -name "neo4j_*.dump.gz" -mtime "+${NEO4J_RETAIN_DAYS}" -delete 2>/dev/null || true
  echo "[prune] Done."
}

# ── Main ────────────────────────────────────────────────────
case "${1:-all}" in
  pg)     backup_pg ;;
  qdrant) backup_qdrant ;;
  neo4j)  backup_neo4j ;;
  prune)  prune ;;
  all)    backup_pg; backup_qdrant; backup_neo4j; prune ;;
  *)      echo "Usage: $0 {pg|qdrant|neo4j|prune|all}"; exit 1 ;;
esac
