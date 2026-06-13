#!/bin/bash
# Collect docker logs for all containers defined in docker-compose.yaml
# Usage: ./logs.sh [docker-compose.yaml path]

set -euo pipefail

# Resolve compose file path (default: ../docker-compose.yaml relative to this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${1:-${SCRIPT_DIR}/../docker-compose.yaml}"
LOG_DIR="${SCRIPT_DIR}/logs"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "[ERROR] docker-compose.yaml not found: $COMPOSE_FILE"
    exit 1
fi

# Create logs directory if it does not exist
mkdir -p "$LOG_DIR"

echo "============================================"
echo " Docker Log Collector"
echo " Compose file : $COMPOSE_FILE"
echo " Log directory: $LOG_DIR"
echo " Timestamp    : $TIMESTAMP"
echo "============================================"

# Extract container_name values from docker-compose.yaml
mapfile -t CONTAINERS < <(grep -E '^\s+container_name:' "$COMPOSE_FILE" | awk '{print $2}')

if [[ ${#CONTAINERS[@]} -eq 0 ]]; then
    echo "[WARN] No containers found in $COMPOSE_FILE"
    exit 0
fi

echo "[INFO] Found ${#CONTAINERS[@]} containers: ${CONTAINERS[*]}"
echo ""

SUCCESS=0
FAILED=0

for CONTAINER in "${CONTAINERS[@]}"; do
    LOG_FILE="${LOG_DIR}/${CONTAINER}_${TIMESTAMP}.log"

    if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER"; then
        echo "[INFO] Collecting logs for: $CONTAINER -> $LOG_FILE"
        docker logs "$CONTAINER" > "$LOG_FILE" 2>&1
        SUCCESS=$((SUCCESS + 1))
    else
        echo "[WARN] Container not found (skipped): $CONTAINER"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "============================================"
echo " Done! Success: $SUCCESS | Skipped: $FAILED"
echo " Logs saved to: $LOG_DIR"
echo "============================================"
