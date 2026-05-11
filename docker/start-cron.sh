#!/usr/bin/env sh
set -eu

CRON_SCHEDULE="${MLOADER_CRON_SCHEDULE:-0 3 * * 1}"
CRON_ARGS="${MLOADER_CRON_ARGS:---all --language english --format pdf}"
RUN_ON_START="${MLOADER_RUN_ON_START:-false}"
OUT_DIR="${MLOADER_EXTRACT_OUT_DIR:-mloader_downloads}"
RUN_REPORT_PATH="${MLOADER_RUN_REPORT_PATH:-}"
LOCK_DIR="${MLOADER_CRON_LOCK_DIR:-/tmp/mloader-cron.lock}"
CRON_FILE="/etc/cron.d/mloader"
RUNNER_FILE="/usr/local/bin/run-mloader-cron.sh"
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

case " ${CRON_ARGS} " in
  *" --out "*|*" -o "*)
    CRON_ARGS_WITH_OUT="${CRON_ARGS}"
    ;;
  *)
    CRON_ARGS_WITH_OUT="--out ${OUT_DIR} ${CRON_ARGS}"
    ;;
esac

case " ${CRON_ARGS_WITH_OUT} " in
  *" --run-report "*)
    ;;
  *)
    if [ -n "${RUN_REPORT_PATH}" ]; then
      CRON_ARGS_WITH_OUT="${CRON_ARGS_WITH_OUT} --run-report ${RUN_REPORT_PATH}"
    fi
    ;;
esac

echo "Configuring weekly mloader cron job..."
echo "Schedule: ${CRON_SCHEDULE}"
echo "Out dir: ${OUT_DIR}"
echo "Args: ${CRON_ARGS_WITH_OUT}"
echo "Binary: ${MLOADER_BIN}"

cat > "${RUNNER_FILE}" <<EOF
#!/usr/bin/env sh
set -eu

LOCK_DIR="${LOCK_DIR}"
CMD="${MLOADER_BIN} ${CRON_ARGS_WITH_OUT}"

if mkdir "\${LOCK_DIR}" 2>/dev/null; then
  cleanup() {
    rmdir "\${LOCK_DIR}" 2>/dev/null || true
  }
  trap cleanup EXIT INT TERM
  run_started=\$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "mloader cron run started at \${run_started}: \${CMD}"
  set +e
  /bin/sh -lc "\${CMD}"
  exit_code=\$?
  set -e
  run_finished=\$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "mloader cron run finished at \${run_finished} with exit code \${exit_code}"
  exit "\${exit_code}"
else
  echo "Another mloader cron run is still active; skipping this schedule tick."
fi
EOF

chmod +x "${RUNNER_FILE}"

cat > "${CRON_FILE}" <<EOF
SHELL=/bin/sh
PATH=/app/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
${CRON_SCHEDULE} root ${RUNNER_FILE} >> /proc/1/fd/1 2>> /proc/1/fd/2
EOF

chmod 0644 "${CRON_FILE}"

if [ "${RUN_ON_START}" = "true" ]; then
  echo "Running initial mloader execution before cron starts..."
  initial_started=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "mloader initial run started at ${initial_started}: ${MLOADER_BIN} ${CRON_ARGS_WITH_OUT}"
  set +e
  /bin/sh -lc "${MLOADER_BIN} ${CRON_ARGS_WITH_OUT}"
  initial_exit_code=$?
  set -e
  initial_finished=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "mloader initial run finished at ${initial_finished} with exit code ${initial_exit_code}"
  if [ "${initial_exit_code}" -ne 0 ]; then
    exit "${initial_exit_code}"
  fi
fi

echo "Starting cron daemon in foreground..."
exec cron -f
