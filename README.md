# carla-autoware-hil

Run [Autoware](https://github.com/autowarefoundation/autoware) (ROS 2 Humble) against
[CARLA](https://github.com/carla-simulator/carla) **0.10 (Unreal Engine 5)**.

Autoware's own CARLA demo stops at CARLA 0.9.16. Its bridge,
[`autoware_carla_interface`](https://github.com/autowarefoundation/autoware_universe/tree/main/simulator/autoware_carla_interface),
has opt-in 0.10 workarounds on `main`, but nothing ships them together with a 0.10
client, a 0.10 vehicle and maps recorded on the UE5 towns. This repository is that
missing glue. It does not fork CARLA or the bridge: it pins them and adds:

| Piece | What it does |
| --- | --- |
| [`versions.env`](versions.env) | Every version pin in one place: CARLA image/tag, Autoware image, bridge commit, map revision, ego vehicle |
| [`scripts/build_client_wheel.sh`](scripts/build_client_wheel.sh) | Gets the CARLA 0.10 Python client: extracted from the server image (cp310), or built from source for other Pythons ([`docker/carla-client.Dockerfile`](docker/carla-client.Dockerfile)) |
| [`docker/bridge.Dockerfile`](docker/bridge.Dockerfile) | Autoware image + the client + `autoware_carla_interface` rebuilt from a pinned `main` commit |
| [`ros/carla_autoware_ue5`](ros/carla_autoware_ue5) | ROS 2 package: `bridge.launch.xml` with the 0.10 settings, plus pedal maps measured for `vehicle.lincoln.mkz` on 0.10 |
| [`scripts/fetch_maps.sh`](scripts/fetch_maps.sh) | Downloads Autoware maps recorded *from* CARLA 0.10 (checksum-verified) |
| [`docker/compose.yaml`](docker/compose.yaml) | CARLA server, bridge, Autoware and an optional chase camera |
| [`tools/`](tools) | `smoke_test.py` (can the server be driven?) and `calibrate_pedal_map.py` (regenerates the pedal maps) |

[docs/compatibility.md](docs/compatibility.md) lists every CARLA 0.10 difference
found and how each one is handled.

## Requirements

- Ubuntu 22.04/24.04 x86_64, an NVIDIA GPU (RTX 3070 class or better) with the
  [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/),
  Docker Compose v2.24+
- About 25 GB of disk for the images
- Autoware perception models under `~/autoware_data/ml_models`, see
  [Autoware's artifacts setup](https://autowarefoundation.github.io/autoware-documentation/main/installation/autoware/source-installation/#how-to-set-up-a-development-environment)

## Quick start

```bash
scripts/build_client_wheel.sh     # -> dist/carla-0.10.0-cp310-cp310-linux_x86_64.whl
scripts/fetch_maps.sh             # -> ~/autoware_data/maps/autoware_maps/Town10HD_Opt
xhost +local:docker
scripts/up.sh                     # builds the bridge image on first run, starts everything
```

The stack starts in order: CARLA → bridge (healthy once the ego is spawned) →
Autoware. In RViz: set the initial pose (Init by GNSS), set a goal, then engage.

Options:

```bash
scripts/up.sh --profile spectator up       # spectator camera follows the ego
scripts/up.sh --headless up --build carla bridge
                                           # no renderer / no GPU: physics, LiDAR,
                                           # IMU, GNSS only (CI, WSL2 without toolkit)
CARLA_RENDER_FLAG=-windowed scripts/up.sh  # show the CARLA window (default is off-screen)
scripts/up.sh down
```

## Without Docker

`ros/carla_autoware_ue5` is an ordinary ament package. Put it in a colcon workspace
next to `autoware_carla_interface` from the commit pinned in `versions.env`,
install the wheel from `dist/`, and run:

```bash
ros2 launch carla_autoware_ue5 bridge.launch.xml \
    map_path:=$HOME/autoware_data/maps/autoware_maps/Town10HD_Opt
ros2 launch autoware_launch e2e_simulator.launch.xml \
    vehicle_model:=sample_vehicle sensor_model:=carla_sensor_kit \
    simulator_type:=carla launch_simulator_interface:=false \
    map_path:=$HOME/autoware_data/maps/autoware_maps/Town10HD_Opt
```

## Checking a server and recalibrating

Both tools need only the CARLA client, so they run in the bridge image or anywhere
the wheel is installed:

```bash
python3 tools/smoke_test.py                 # PASS/FAIL, and which 0.10 quirks are present
python3 tools/calibrate_pedal_map.py        # rewrites ros/carla_autoware_ue5/calibration/*.csv
python3 tools/calibrate_pedal_map.py --vehicle vehicle.dodge.charger --out /tmp/charger
```

Run the calibration again whenever you change `EGO_VEHICLE` or the CARLA version.
It also prints the `min_positive_throttle` to use in `bridge.launch.xml`.

## Changing versions

Edit `versions.env`, then rebuild: `scripts/build_client_wheel.sh && scripts/up.sh build`.
The client wheel must come from the same CARLA tag as the server. For Autoware
Jazzy, set `AUTOWARE_IMAGE=...:universe-cuda-jazzy`, `CLIENT_PYTHON_TAG=cp312`
and `CLIENT_BUILD_BASE=ubuntu:24.04`; the wheel is then built from source.

## History

This work began on a fork of `carla-simulator/carla`
([automaticdai/carla-autoware](https://github.com/automaticdai/carla-autoware));
it moved here so the repository holds only the integration, not the simulator
sources. CARLA and Autoware remain under their own licenses
(MIT and Apache-2.0); `steer_map.csv` is copied unchanged from
`autoware_carla_interface`.
