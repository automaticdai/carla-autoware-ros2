# Calibration maps

Inputs for `autoware_raw_vehicle_cmd_converter` (rows: pedal, columns: speed in m/s,
values: acceleration in m/s²).

| File | Source |
| --- | --- |
| `accel_map.csv`, `brake_map.csv` | Measured for `vehicle.lincoln.mkz` on CARLA 0.10.0, Town10HD_Opt, `fixed_delta_seconds` 0.05, by `tools/calibrate_pedal_map.py` |
| `steer_map.csv` | Copied unchanged from `autoware_carla_interface` (Apache-2.0). Unused, since the converter runs with `convert_steer_cmd: false` |

The throttle rows drop above about 11 m/s, where the MKZ shifts from 1st to 2nd
gear; that is real vehicle behaviour, not noise. Regenerate the maps after changing
the ego vehicle or the CARLA version:

```bash
python3 tools/calibrate_pedal_map.py --vehicle <blueprint> --out ros/carla_autoware_ue5/calibration
```
