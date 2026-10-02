#!/usr/bin/env bash
# Source Autoware, then the CARLA overlay on top, then run the command.
set -e
# shellcheck disable=SC1091
source /opt/autoware/setup.bash
# shellcheck disable=SC1091
source /opt/carla_overlay/install/setup.bash
exec "$@"
