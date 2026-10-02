# Builds the CARLA Python client wheel from source, without Unreal Engine.
#
# CARLA 0.10 publishes no client wheel (not on PyPI, not in the release
# tarball), so it has to be built against the same Python as the Autoware
# image that imports it. CLIENT_BUILD_BASE picks that Python:
#   ubuntu:22.04 -> cp310 (Autoware humble), ubuntu:24.04 -> cp312 (jazzy).
#
# Usage (see scripts/build_client_wheel.sh):
#   docker build -f docker/carla-client.Dockerfile --output type=local,dest=dist .

ARG CLIENT_BUILD_BASE=ubuntu:22.04

FROM ${CLIENT_BUILD_BASE} AS build

ARG CARLA_GIT_URL=https://github.com/carla-simulator/carla.git
ARG CARLA_GIT_REF=0.10.0
ARG CMAKE_VERSION=3.28.3

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Same client-side packages as CarlaSetup.sh at 0.10.0, minus the UE5 ones.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential g++-12 gcc-12 make ninja-build \
        python3 python3-dev python3-pip python3-venv \
        libpng-dev libtiff5-dev libjpeg-dev libxml2-dev \
        autoconf libtool curl ca-certificates git rsync sed tzdata \
    && rm -rf /var/lib/apt/lists/*

# CARLA needs CMake >= 3.28; Ubuntu 22.04 ships 3.22.
RUN curl -fsSL "https://github.com/Kitware/CMake/releases/download/v${CMAKE_VERSION}/cmake-${CMAKE_VERSION}-linux-x86_64.tar.gz" \
        | tar -xz -C /opt \
    && ln -s /opt/cmake-${CMAKE_VERSION}-linux-x86_64/bin/* /usr/local/bin/

RUN git clone --depth 1 --branch "${CARLA_GIT_REF}" "${CARLA_GIT_URL}" /carla

# A venv keeps the build tools off the system Python (Ubuntu 24.04 refuses
# system-wide pip installs) while still targeting the system interpreter ABI.
RUN python3 -m venv /venv \
    && /venv/bin/pip install --no-cache-dir --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r /carla/requirements.txt
ENV PATH=/venv/bin:${PATH}

WORKDIR /carla

# No --toolchain: CMake/LinuxToolchain.cmake requires the UE5 clang sysroot.
# Client-only, so the server, UE project, examples and tests are all off.
# Configure fetches every dependency from GitHub and one dropped transfer
# fails it, so retry like CarlaSetup.sh does (finished downloads are reused).
RUN for attempt in 1 2 3 4 5; do \
        cmake -G Ninja -S . -B Build \
            -DCMAKE_BUILD_TYPE=Release \
            -DCMAKE_C_COMPILER=gcc-12 \
            -DCMAKE_CXX_COMPILER=g++-12 \
            -DBUILD_CARLA_UNREAL=OFF \
            -DBUILD_CARLA_SERVER=OFF \
            -DBUILD_CARLA_CLIENT=ON \
            -DBUILD_PYTHON_API=ON \
            -DBUILD_EXAMPLES=OFF \
            -DBUILD_LIBCARLA_TESTS=OFF \
            -DENABLE_ROS2=OFF \
            -DPython3_EXECUTABLE=/venv/bin/python \
        && break; \
        [ "$attempt" = 5 ] && exit 1; \
        echo "configure failed (attempt $attempt), retrying in 30 s"; sleep 30; \
    done \
    && cmake --build Build --target carla-python-api

# Fail the build here rather than at runtime if the module does not import.
RUN pip install --no-cache-dir Build/PythonAPI/dist/carla-*.whl \
    && cd / && python -c "import carla; print('carla client', carla.__file__)"

FROM scratch AS wheel
COPY --from=build /carla/Build/PythonAPI/dist/ /
