#!/usr/bin/env bash
# Crontab installer for School Email Triage (Linux / macOS)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

UV_BIN="$(command -v uv || true)"
if [ -z "$UV_BIN" ]; then
    echo "Error: 'uv' executable not found in PATH." >&2
    exit 1
fi

LOG_FILE="${PROJECT_DIR}/triage.log"
CRON_SCHEDULE="0 * * * *"  # Runs every hour at minute 0
CRON_CMD="cd ${PROJECT_DIR} && ${UV_BIN} run school-email-triage >> ${LOG_FILE} 2>&1"

echo "Setting up cron job to run hourly..."
(crontab -l 2>/dev/null | grep -v "school-email-triage" || true; echo "${CRON_SCHEDULE} ${CRON_CMD}") | crontab -

echo "Cron job installed successfully:"
echo "  Schedule: ${CRON_SCHEDULE}"
echo "  Command:  ${CRON_CMD}"
echo "  Logs:     ${LOG_FILE}"
