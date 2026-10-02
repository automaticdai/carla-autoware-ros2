#!/usr/bin/env bash
# Put the CARLA Python client wheel pinned in versions.env into ./dist.
#
#   scripts/build_client_wheel.sh            # extract from CARLA_IMAGE if it has a
#                                            # wheel for CLIENT_PYTHON_TAG, else build
#   scripts/build_client_wheel.sh --source   # always build from CARLA_GIT_REF
#
# carlasim/carla:0.10.0 ships a cp310 wheel (matches Autoware humble). Any other
# Python, e.g. cp312 for jazzy, has to be built from source.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
# shellcheck source=SCRIPTDIR/../versions.env
source "${ROOT}/versions.env"
set +a

mode="${1:-auto}"
wheel_name="carla-${CARLA_VERSION}-${CLIENT_PYTHON_TAG}-${CLIENT_PYTHON_TAG}-linux_x86_64.whl"
mkdir -p "${ROOT}/dist"

if [[ "${mode}" != "--source" ]]; then
    container="$(docker create "${CARLA_IMAGE}")"
    trap 'docker rm -f "${container}" >/dev/null' EXIT
    if docker cp "${container}:/home/carla/PythonAPI/carla/dist/${wheel_name}" "${ROOT}/dist/" 2>/dev/null; then
        echo "extracted ${wheel_name} from ${CARLA_IMAGE}"
        exit 0
    fi
    echo "${CARLA_IMAGE} has no ${wheel_name}; building from source"
fi

docker build \
    -f "${ROOT}/docker/carla-client.Dockerfile" \
    --build-arg CLIENT_BUILD_BASE="${CLIENT_BUILD_BASE}" \
    --build-arg CARLA_GIT_URL="${CARLA_GIT_URL}" \
    --build-arg CARLA_GIT_REF="${CARLA_GIT_REF}" \
    --target wheel \
    --output "type=local,dest=${ROOT}/dist" \
    "${ROOT}/docker"

ls -1 "${ROOT}"/dist/carla-*.whl
