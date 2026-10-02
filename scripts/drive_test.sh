#!/usr/bin/env bash
# Headless end-to-end check: start CARLA, the bridge and Autoware (no GPU
# needed), then have Autoware drive to a goal straight ahead and arrive.
#
#   scripts/drive_test.sh [--distance 80] [--timeout 180]   # extra args go to drive_test.py
#   KEEP_RUNNING=1 scripts/drive_test.sh                    # leave the stack up afterwards
#
# The ego is spawned at SPAWN_POINT (CARLA x,y,z,roll,pitch,yaw); the default is
# the start of a 164 m straight lane in Town10HD_Opt.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SPAWN_POINT="${SPAWN_POINT:--44.98,114.96,0.6,0,0,-90.2}"
up() { "${ROOT}/scripts/up.sh" --headless "$@"; }

up up -d --build --wait carla bridge
up up -d autoware perception-stub
[[ "${KEEP_RUNNING:-0}" == 1 ]] || trap 'up down' EXIT

status=0
up exec -T autoware /docker-entrypoint.sh /usr/local/bin/bridge-entrypoint.sh \
    python3 -u /opt/carla-autoware-tools/autoware/drive_test.py "$@" || status=$?
exit "${status}"
