#!/usr/bin/env sh
set -eu

CRON_SCHEDULE="${MLOADER_CRON_SCHEDULE:-0 3 * * 1}"
CRON_ARGS="${MLOADER_CRON_ARGS:---all --language english --format pdf}"
RUN_ON_START="${MLOADER_RUN_ON_START:-false}"
CRON_FILE="/etc/cron.d/mloader"
MLOADER_BIN="${MLOADER_BIN:-/app/.venv/bin/mloader}"
PATH="/app/.venv/bin:${PATH}"

if [ ! -x "${MLOADER_BIN}" ]; then
  if command -v mloader >/dev/null 2>&1; then
    MLOADER_BIN="$(command -v mloader)"
  else
    echo "Error: mloader executable not found (checked ${MLOADER_BIN} and PATH)." >&2
    exit 127
  fi
fi

echo "Configuring weekly mloader cron job..."
echo "Schedule: ${CRON_SCHEDULE}"
echo "Args: ${CRON_ARGS}"
echo "Binary: ${MLOADER_BIN}"

cat > "${CRON_FILE}" <<EOF
SHELL=/bin/sh
PATH=/app/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
${CRON_SCHEDULE} root /bin/sh -lc '${MLOADER_BIN} ${CRON_ARGS}' >> /proc/1/fd/1 2>> /proc/1/fd/2
EOF

chmod 0644 "${CRON_FILE}"

if [ "${RUN_ON_START}" = "true" ]; then
  echo "Running initial mloader execution before cron starts..."
  /bin/sh -lc "${MLOADER_BIN} ${CRON_ARGS}"
fi

echo "Starting cron daemon in foreground..."
exec cron -f
