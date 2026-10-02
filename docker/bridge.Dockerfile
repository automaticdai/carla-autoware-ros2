# Autoware runtime + CARLA 0.10 client + an overlay with the CARLA 0.10 bridge.
#
# The released Autoware image ships an autoware_carla_interface that predates
# its CARLA 0.10 workarounds, so the package is rebuilt here from a pinned
# autoware_universe commit, together with this repo's carla_autoware_ue5
# presets. Build context is the repository root (wheel comes from ./dist).

ARG AUTOWARE_IMAGE=ghcr.io/autowarefoundation/autoware:universe-cuda-humble
FROM ${AUTOWARE_IMAGE}

ARG AUTOWARE_UNIVERSE_URL=https://github.com/autowarefoundation/autoware_universe.git
ARG AUTOWARE_UNIVERSE_REF=main

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# CARLA client. Unpacked rather than pip-installed: the runtime image has no
# guaranteed pip, and the wheel is pure binary module + Python glue.
COPY dist/carla-*.whl /tmp/wheels/
RUN SITE="$(python3 -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')" \
    && mkdir -p "${SITE}" \
    && python3 -m zipfile -e /tmp/wheels/carla-*.whl "${SITE}" \
    && rm -rf /tmp/wheels \
    && cd / && python3 -c "import carla; print('carla client OK')"

# Bridge overlay: only autoware_carla_interface from autoware_universe.
RUN git clone --filter=blob:none --no-checkout "${AUTOWARE_UNIVERSE_URL}" /tmp/universe \
    && git -C /tmp/universe sparse-checkout set simulator/autoware_carla_interface \
    && git -C /tmp/universe checkout "${AUTOWARE_UNIVERSE_REF}" \
    && mkdir -p /opt/carla_overlay/src \
    && mv /tmp/universe/simulator/autoware_carla_interface /opt/carla_overlay/src/ \
    && echo "${AUTOWARE_UNIVERSE_REF} $(git -C /tmp/universe rev-parse HEAD)" > /opt/carla_overlay/AUTOWARE_UNIVERSE_REF \
    && rm -rf /tmp/universe
COPY ros/carla_autoware_ue5 /opt/carla_overlay/src/carla_autoware_ue5

RUN source /opt/autoware/setup.bash \
    && cd /opt/carla_overlay \
    && colcon build --merge-install --install-base install \
        --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    && rm -rf build log

# Keep the base image's entrypoint (host UID mapping, Autoware environment) and
# chain the overlay sourcing after it.
COPY docker/bridge-entrypoint.sh /usr/local/bin/bridge-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh", "/usr/local/bin/bridge-entrypoint.sh"]
CMD ["bash"]
