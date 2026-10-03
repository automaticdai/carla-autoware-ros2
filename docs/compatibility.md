# CARLA 0.10 compatibility notes

What differs between the CARLA 0.9 setup Autoware supports and CARLA 0.10 (UE5),
and how this repository handles each difference. "Measured" means checked against a
running `carlasim/carla:0.10.0` server (null RHI, Town10HD_Opt) with the tools in
`tools/`, on 2026-10-02.

| # | Difference on 0.10 | Effect on Autoware | Handling here | Evidence |
| - | --- | --- | --- | --- |
| 1 | No `carla` 0.10 wheel on PyPI (last release there is 0.9.16) | Autoware's CARLA demo can't install a client | Wheel taken from the server image; source build for other Pythons | Measured: `carlasim/carla:0.10.0` contains `PythonAPI/carla/dist/carla-0.10.0-cp310-cp310-linux_x86_64.whl`; it imports on stock Ubuntu 22.04 and handshakes as `client 0.10.0 server 0.10.0`. (Autoware's demo README says the release ships no wheel, which is wrong for the Docker image.) |
| 2 | `vehicle.toyota.prius` (bridge default) removed | Ego spawn fails | `vehicle_type:=vehicle.lincoln.mkz` | 0.10 catalogue; the MKZ spawns and drives in `smoke_test.py` |
| 3 | The bridge's 0.10 options (`wake_sleeping_physics`, `min_positive_throttle`, `flatten_steering_curve`, ground snapping) are on `autoware_universe` `main` only | The released Autoware image has a bridge without them | Bridge rebuilt from a pinned `main` commit in `bridge.Dockerfile` | Those args are absent from `autoware_carla_interface.launch.xml` at 0.48.0, 0.50.0 and 0.52.1 |
| 4 | Pedal response differs from the 0.9 Prius maps | Longitudinal control tracks the wrong acceleration | `calibration/accel_map.csv` and `brake_map.csv` measured for the MKZ | `calibrate_pedal_map.py`: e.g. throttle 0.3 gives +0.47 to +0.74 m/s², where the Prius map assumed +0.78 to +1.75 |
| 5 | MKZ needs throttle ≥ 0.20 to pull away from rest | A small creep command stalls at standstill | `min_positive_throttle:=0.2`, `max_throttle: 0.5` | Measured: 0.20 with and without a wake nudge |
| 6 | MKZ speed→steering curve has out-of-order points | The bridge's steer normalization reads a corrupt curve | `flatten_steering_curve:=true` | Measured: curve x-values `0, 10, 0, 20, 60, 120` |
| 7 | Chaos puts resting bodies to sleep (`sleep_threshold` 10) | Throttle from a long standstill may not wake the ego | `wake_sleeping_physics:=true` | **Not reproduced** after 10 s at rest under null RHI; kept on following upstream's guidance, since it is harmless when the body is awake |
| 8 | Towns re-authored in UE5 | 0.9 point clouds don't match, so NDT drifts and MRM stops the route | Maps from `AutowareFoundation/carla-ue5-maps` (recorded on 0.10), pinned revision, SHA-256 checked | Upstream `demo_artifacts` role documentation |
| 9 | Only `Town10HD_Opt` (and Mine_01/Town15) ship with 0.10; no Town01 | The default `map_path` world doesn't exist | `CARLA_WORLD=Town10HD_Opt` | `carla-ue5-maps` currently publishes only `Town10HD_Opt` |
| 10 | `WheelPhysicsControl.position` renamed to `location`, and it reads as zeros | Tools that derive wheelbase from physics break | `smoke_test.py` no longer derives the wheelbase; the bridge default of 2.85 m is the MKZ spec | Measured: all four wheel `location`/`offset` values are `(0, 0, 0)` |
| 11 | (Autoware, not CARLA) `autoware_raw_vehicle_cmd_converter` rejects a pedal map unless every row is *strictly* above (accel) or below (brake) the previous one | One tie in a calibrated map crashes the converter (`Brake map is invalid`); no actuation reaches CARLA and the ego never moves | `calibrate_pedal_map.py` enforces a 0.01 m/s² margin; CI checks the same strict rule | Measured: the first calibrated brake map tied at 1.39 m/s, where the ego stops inside the measurement window |

## End-to-end check

### Bridge only

On 2026-10-02 the compose stack (`scripts/up.sh --headless up carla bridge`) was
run on WSL2 with the host DDS settings from `scripts/host_setup.sh`:

- The bridge became healthy (ego spawned) about 70 s after start.
- Rates: `/clock`, IMU, GNSS and `/vehicle/status/velocity_status` at 20 Hz;
  `/sensing/lidar/top/pointcloud_before_sync` at 10 Hz. Camera topics are
  advertised but silent, as expected without a renderer.
- Publishing `/control/command/actuation_cmd` at throttle 0.4 took the ego from
  0 to 3.0 m/s in 6 s; brake 0.8 stopped it.
- Without the host DDS settings every bridge node fails with
  `rmw_create_node: failed to create domain`; `scripts/up.sh` now refuses to start.

### Full closed loop

`scripts/drive_test.sh` (headless; Autoware with `perception:=false` and
`tools/autoware/perception_stub.py`) was run four times from a cold start on
2026-10-02. Every run passed identically: localization initialized on the 0.10
point cloud, the route was set 80 m ahead, the ego pulled away (3.1–3.3 m/s after
5 s), cruised at about 4.3 m/s and stopped 0.5 m from the goal. That's ARRIVED
after 26 s, with 79.5 m travelled and about 1 min 46 s for the whole script.

The bridge health check must call `wait_for_tick()` before listing actors: a
fresh client sees an empty actor list until it receives a tick, so without it the
check fails at random.

### Repeat check on 2026-10-03

The headless CARLA 0.10 drive test passed again: ARRIVED after 26 s, 79.5 m
travelled, stopping about 0.5 m from the goal. Live sampling confirmed IMU,
GNSS, localization, control, actuation and vehicle feedback at about 20 Hz,
with LiDAR and planning at 10 Hz. The map-to-vehicle and vehicle-to-IMU TF
connections passed. ShellCheck, Python compilation, launch XML, calibration
monotonicity and both Compose configurations also passed.

### Windows CARLA 0.9.16 with cameras

On 2026-10-03, a separate compatibility test used the installed Windows CARLA
0.9.16 server on an RTX 5080 and the ROS 2 Humble stack in WSL2. Installing
NVIDIA Container Toolkit made the GPU visible to Docker, but the Linux CARLA
0.10 container still exposed only the llvmpipe CPU Vulkan renderer and exited
during rendered startup. The camera test therefore used native Windows CARLA.

This test required a separate image with the **0.9.16 cp310 client**, upstream
`autoware_carla_interface` launch defaults for `vehicle.toyota.prius` and its
pedal maps, and CARLA 0.9 maps. The point cloud and lanelet map came from
`carla-simulator/autoware-contents` at revision
`062f94b5322e679ee0430e2daa6995dca9f7f0ea` (`Town10HD.pcd` and
`Town10HD.osm`), placed in a `Town10HD_Opt` directory with the Local projector.
The repository's CARLA 0.10 pins and presets were unchanged; the default
Compose stack does not reproduce this Windows configuration.

The bridge used all six cameras (`use_light_weight_sensor_mapping:=false`),
ROS domain 42, and spawn point `-87.276062,24.441530,0.6,0,0,0.2`.
Autoware ran with `launch_simulator_interface:=false`, `perception:=false`
and `rviz:=false`, alongside the empty-world perception stub. The existing
`tools/autoware/drive_test.py --distance 80 --timeout 180` exercised the AD API.

- The clean run reached ARRIVED after **58 wall-clock seconds**, travelling
  **79.6 m** and stopping about **0.4 m** from the goal.
- A CARLA collision sensor reported **zero collisions** during the clean run.
  Sampled simulator ground truth showed a peak speed of **4.49 m/s**, maximum
  lane-center distance of **0.176 m**, and effectively zero final speed.
- All six **1600×900** camera feeds, the combined image and front compressed
  image published. Saved raw-camera images were nonblank; the combined view
  was also inspected visually.
- LiDAR, IMU, GNSS, localization, trajectory, control, actuation and vehicle
  feedback all published. TF checks passed for `map` → `base_link`,
  `base_link` → `tamagawa/imu_link` and `base_link` → `velodyne_top`.
- During a separate 30-second sample after arrival, the simulator ran at about
  **0.15× real time**: cameras, LiDAR and planning were about **1.5 Hz wall
  time**, with clock, IMU, GNSS and control about **3.1 Hz**. The combined-image
  publisher ran at about 9.7 Hz; that does not imply fresh camera frames at
  that rate. These measurements are not a real-time performance pass.

The first attempt was obstructed by the parked vehicle created for the earlier
camera preview. It stopped moving after about 18 m while throttle remained
commanded. That attempt was interrupted, the preview vehicle and orphaned test
sensors were removed, and the clean run above was performed. This demonstrates
why the empty-world stub requires an obstacle-free test scene.

**Scope:** this validates rendered sensor transport and a straight-line
localization/planning/control loop on **0.9.16**. Learned obstacle detection,
traffic-light recognition, driving among traffic, curved-route tracking and
rendering on **0.10** remain unvalidated. Perception model files were absent.

Committed evidence: [report](test-results/2026-10-03/windows-report.json),
[clean drive log](test-results/2026-10-03/windows-drive.log),
[topic sample](test-results/2026-10-03/windows-topics.log) and
[six-camera view](test-results/2026-10-03/windows-cameras.jpg).

## Open items

- **Steering gain.** The physics reports a 70° front-wheel max steer, which is
  implausible for an MKZ (about 35–40° in reality). A full-lock low-speed circle
  measured a 2–3 m radius, but those runs were disturbed by roadside geometry. If
  lateral tracking oscillates, measure on an open area and set
  `max_wheel_steer_angle_deg`.
- **Rendering.** CARLA 0.10 remains tested only with `-nullrhi`; its camera
  sensors and camera-based perception are untested. The Windows 0.9.16 camera
  test above does not establish 0.10 rendering compatibility.
- **Sleeping bodies.** `sleep_threshold` is exposed in `VehiclePhysicsControl`.
  Setting it to 0 could replace the wake nudge in the bridge, but that is untested.
