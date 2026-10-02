#!/usr/bin/env bash
# docker compose for the CARLA + Autoware stack, with versions.env as the env file.
#
#   scripts/up.sh                      # build if needed, start everything
#   scripts/up.sh --profile spectator up   # also run the chase camera
#   scripts/up.sh down                 # any other docker compose arguments
#   scripts/up.sh --headless up --build carla bridge
#                                      # no renderer/GPU (docker/compose.headless.yaml)
#
# Requires the client wheel in ./dist (scripts/build_client_wheel.sh) and the map
# under $AUTOWARE_DATA/maps/autoware_maps (scripts/fetch_maps.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HOST_UID="${HOST_UID:-$(id -u)}"
export HOST_GID="${HOST_GID:-$(id -g)}"

if ! compgen -G "${ROOT}/dist/carla-*.whl" >/dev/null; then
    echo "error: no CARLA client wheel in dist/; run scripts/build_client_wheel.sh" >&2
    exit 1
fi

files=(-f "${ROOT}/docker/compose.yaml")
if [[ "${1:-}" == "--headless" ]]; then
    shift
    files+=(-f "${ROOT}/docker/compose.headless.yaml")
    export CARLA_NO_RENDERING=true
fi

[[ $# -eq 0 ]] && set -- up --build
exec docker compose --env-file "${ROOT}/versions.env" "${files[@]}" "$@"
