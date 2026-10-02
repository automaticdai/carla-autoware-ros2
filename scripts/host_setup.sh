#!/usr/bin/env bash
# Host kernel settings Autoware's CycloneDDS config needs (run once per boot,
# or with --persist to install them under /etc/sysctl.d).
#
# The Autoware image's cyclonedds.xml requires a 10 MB socket receive buffer.
# With host networking these sysctls belong to the host kernel, so containers
# cannot set them; without them every ROS node fails with
# "rmw_create_node: failed to create domain".
# https://autowarefoundation.github.io/autoware-documentation/main/installation/additional-settings-for-developers/network-configuration/dds-settings/
set -euo pipefail

settings=(
    net.core.rmem_max=2147483647
    net.ipv4.ipfrag_time=3
    net.ipv4.ipfrag_high_thresh=134217728
)

sudo sysctl -w "${settings[@]}"

if [[ "${1:-}" == "--persist" ]]; then
    printf '%s\n' "${settings[@]}" | sudo tee /etc/sysctl.d/10-autoware-dds.conf >/dev/null
    echo "installed /etc/sysctl.d/10-autoware-dds.conf"
fi

# CycloneDDS is pinned to the loopback interface, which needs multicast.
sudo ip link set lo multicast on
