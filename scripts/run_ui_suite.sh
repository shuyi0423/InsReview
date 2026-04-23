#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_ui_suite.sh [profile] <suite> [extra pytest args...]

Supported profiles:
  local          Do not load an env profile file
  dev            Load env/dev.env
  test           Load env/test.env
  online         Load env/online.env

Supported suites:
  all            Run all UI tests
  smoke          Run lightweight smoke tests
  auth           Run Feishu login tests
  review         Run intelligent review flow tests
  checklist      Run checklist module tests
  review-rule    Run review rule module tests
  import         Run checklist import tests
  regression     Run all regression-tagged suites
  collect        Collect tests without executing them
EOF
}

load_profile_env() {
  local profile="$1"
  local env_file="${PROJECT_ROOT}/env/${profile}.env"
  if [[ ! -f "${env_file}" ]]; then
    echo "Missing env profile file: ${env_file}" >&2
    exit 1
  fi

  set -a
  # shellcheck disable=SC1090
  source "${env_file}"
  set +a
}

PROFILE="local"
if [[ $# -gt 0 ]]; then
  case "$1" in
    local|dev|test|online)
      PROFILE="$1"
      shift
      ;;
  esac
fi

if [[ $# -eq 0 ]]; then
  SUITE="all"
else
  SUITE="$1"
  shift
fi

cd "${PROJECT_ROOT}"

if [[ "${PROFILE}" != "local" ]]; then
  load_profile_env "${PROFILE}"
fi

export INSREVIEW_ENV_PROFILE="${PROFILE}"

case "${SUITE}" in
  all)
    exec "${PYTHON_BIN}" -m pytest -s tests "$@"
    ;;
  smoke)
    exec "${PYTHON_BIN}" -m pytest -s -m smoke tests "$@"
    ;;
  auth)
    exec "${PYTHON_BIN}" -m pytest -s -m auth tests "$@"
    ;;
  review)
    exec "${PYTHON_BIN}" -m pytest -s -m review_flow tests "$@"
    ;;
  checklist)
    exec "${PYTHON_BIN}" -m pytest -s -m checklist tests "$@"
    ;;
  review-rule)
    exec "${PYTHON_BIN}" -m pytest -s -m review_rule tests "$@"
    ;;
  import)
    exec "${PYTHON_BIN}" -m pytest -s -m checklist_import tests "$@"
    ;;
  regression)
    exec "${PYTHON_BIN}" -m pytest -s -m regression tests "$@"
    ;;
  collect)
    exec "${PYTHON_BIN}" -m pytest --collect-only tests -q "$@"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
