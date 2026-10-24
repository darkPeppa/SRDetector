#!/usr/bin/env bash
# Container entry point: sets up the Geant4 environment (datasets) and dispatches.
#   docker run srdet run ...      -> python CLI (srdet run ...)
#   docker run srdet srdet-sim m  -> the bare Geant4 application
#   docker run srdet bash         -> shell
set -e
# geant4.sh exports the G4*DATA variables for the installed datasets
# shellcheck disable=SC1091
source /opt/geant4/bin/geant4.sh >/dev/null 2>&1 || true
export PATH="${SRDET_HOME}/bin:${PATH}"

case "${1:-}" in
  bash|sh|python|python3|srdet-sim|pytest|jupyter|root|make|cmake)
    exec "$@" ;;
  "")
    exec srdet --help ;;
  *)
    exec srdet "$@" ;;
esac
