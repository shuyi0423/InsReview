#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ $# -gt 0 ]]; then
  case "$1" in
    local|dev|online)
      PROFILE="$1"
      shift
      exec "${SCRIPT_DIR}/run_ui_suite.sh" "${PROFILE}" all "$@"
      ;;
  esac
fi

exec "${SCRIPT_DIR}/run_ui_suite.sh" all "$@"
