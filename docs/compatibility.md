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

## Open items

- **Steering gain.** The physics reports a 70° front-wheel max steer, which is
  implausible for an MKZ (about 35–40° in reality). A full-lock low-speed circle
  measured a 2–3 m radius, but those runs were disturbed by roadside geometry. If
  lateral tracking oscillates, measure on an open area and set
  `max_wheel_steer_angle_deg`.
- **Rendering.** Everything here was measured with `-nullrhi`, so camera sensors
  and camera-based perception on 0.10 are untested in this repository.
- **Sleeping bodies.** `sleep_threshold` is exposed in `VehiclePhysicsControl`.
  Setting it to 0 could replace the wake nudge in the bridge, but that is untested.
