#!/usr/bin/env bash
# Download the Autoware map for a CARLA 0.10 world from the pinned Hugging Face
# revision into ${AUTOWARE_DATA:-$HOME/autoware_data}/maps/autoware_maps/<World>.
#
#   scripts/fetch_maps.sh [World]     # default: CARLA_WORLD from versions.env
#
# These maps were recorded from CARLA 0.10. Do not use the 0.9 town maps from
# bitbucket.org/carla-simulator/autoware-contents: the UE5 towns are different
# geometry, NDT localizes against walls that no longer exist, and the route
# ends in an emergency stop.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=SCRIPTDIR/../versions.env
source "${ROOT}/versions.env"

WORLD="${1:-${CARLA_WORLD}}"
DEST="${AUTOWARE_DATA:-${HOME}/autoware_data}/maps/autoware_maps/${WORLD}"
BASE="https://huggingface.co/datasets/${MAPS_HF_DATASET}"
TREE_URL="https://huggingface.co/api/datasets/${MAPS_HF_DATASET}/tree/${MAPS_HF_REVISION}/autoware_maps/${WORLD}"

# Path, size and LFS sha256 of every file, so downloads can be verified.
listing="$(curl -fsSL ${HF_TOKEN:+-H "Authorization: Bearer ${HF_TOKEN}"} "${TREE_URL}")" || {
    echo "error: world '${WORLD}' not found in ${MAPS_HF_DATASET}@${MAPS_HF_REVISION}" >&2
    exit 1
}

mkdir -p "${DEST}"
python3 -c '
import json, sys
for f in json.loads(sys.argv[1]):
    if f["type"] == "file":
        print(f["path"], f.get("lfs", {}).get("oid", "-"))
' "${listing}" | while read -r path sha; do
    out="${DEST}/$(basename "${path}")"
    if [[ "${sha}" != "-" && -f "${out}" ]] && echo "${sha}  ${out}" | sha256sum -c --quiet 2>/dev/null; then
        echo "ok      ${out}"
        continue
    fi
    echo "fetch   ${out}"
    curl -fL --retry 3 -sS -o "${out}.part" \
        ${HF_TOKEN:+-H "Authorization: Bearer ${HF_TOKEN}"} \
        "${BASE}/resolve/${MAPS_HF_REVISION}/${path}"
    if [[ "${sha}" != "-" ]]; then
        echo "${sha}  ${out}.part" | sha256sum -c --quiet
    fi
    mv "${out}.part" "${out}"
done

echo "map ready: ${DEST}"
