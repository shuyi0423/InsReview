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
  ./scripts/run_ui_suite.sh <suite> [extra pytest args...]

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

if [[ $# -eq 0 ]]; then
  SUITE="all"
else
  SUITE="$1"
  shift
fi

cd "${PROJECT_ROOT}"

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
