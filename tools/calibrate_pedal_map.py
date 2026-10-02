#!/usr/bin/env python3
"""Measure accel/brake maps for autoware_raw_vehicle_cmd_converter on a CARLA server.

The maps shipped with autoware_carla_interface were measured on the 0.9
vehicle.toyota.prius. 0.10 vehicles have different powertrains (and the Prius
is gone), so Autoware's longitudinal controller gets the wrong acceleration for
every pedal command. This tool measures the real response of the ego blueprint.

For every (pedal, speed) cell the ego is teleported to the start of a long
straight lane, launched at that speed with set_target_velocity, held at the
pedal for a settle window and then a measurement window; the cell value is the
least-squares slope of forward speed over the measurement window.

Output: accel_map.csv and brake_map.csv in the converter's format
(rows = pedal, columns = speed [m/s]), plus the lowest throttle that starts the
ego from rest (the bridge's min_positive_throttle).
"""

import argparse
import csv
import os
import sys

from carla_session import (
    add_connection_args,
    carla,
    connect,
    forward_speed,
    heading_vector,
    load_world,
    spawned_vehicle,
    straightest_spawn_point,
    synchronous,
)

# Same grid as the upstream maps, so the files are drop-in replacements.
SPEEDS = [0.0, 1.39, 2.78, 4.17, 5.56, 6.94, 8.33, 9.72, 11.11, 12.5, 13.89]
ACCEL_PEDALS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
BRAKE_PEDALS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]


def slope(samples):
    """Least-squares dv/dt of (t, v) samples."""
    n = len(samples)
    mt = sum(t for t, _ in samples) / n
    mv = sum(v for _, v in samples) / n
    den = sum((t - mt) ** 2 for t, _ in samples)
    return sum((t - mt) * (v - mv) for t, v in samples) / den


def measure(world, ego, start, speed, control, dt, settle, window):
    ego.set_transform(start)
    ego.apply_control(carla.VehicleControl(brake=1.0))
    ego.set_target_velocity(carla.Vector3D())
    world.tick()
    # A small floor on the launch speed also wakes a sleeping Chaos body.
    ego.set_target_velocity(heading_vector(start, max(speed, 0.05)))
    ego.apply_control(control)
    for _ in range(int(settle / dt)):
        world.tick()
    samples = []
    for i in range(int(window / dt)):
        world.tick()
        v = forward_speed(ego)
        # Once stopped the speed stays at zero; including that tail would
        # understate braking at low speed.
        if speed > 0.0 and v < 0.05 and len(samples) >= 2:
            break
        samples.append((i * dt, v))
    return slope(samples)


def start_throttle(world, ego, start, dt, pedals, nudge, seconds=3.0, moving=0.5):
    """Lowest throttle that gets the ego from rest to `moving` m/s, optionally after a wake nudge."""
    for p in pedals:
        ego.set_transform(start)
        ego.set_target_velocity(carla.Vector3D())
        ego.apply_control(carla.VehicleControl(brake=1.0))
        for _ in range(int(1.0 / dt)):
            world.tick()
        if nudge > 0.0:
            ego.set_target_velocity(heading_vector(start, nudge))
        ego.apply_control(carla.VehicleControl(throttle=p))
        for _ in range(int(seconds / dt)):
            world.tick()
        if forward_speed(ego) >= moving:
            return p
    return None


def monotonic(rows, increasing, margin=0.01):
    """Make each speed column strictly monotonic in pedal.

    autoware_raw_vehicle_cmd_converter rejects the whole map ("Accel/Brake map
    is invalid") unless every row is strictly above (accel) or below (brake)
    the previous one in every column. Ties come from noise, gear shifts, and
    low-speed braking where the ego stops inside the measurement window.
    """
    fixed, changed = [list(rows[0])], False
    for row in rows[1:]:
        prev = fixed[-1]
        if increasing:
            new = [max(a, b + margin) for a, b in zip(row, prev)]
        else:
            new = [min(a, b - margin) for a, b in zip(row, prev)]
        changed |= new != list(row)
        fixed.append(new)
    return fixed, changed


def write_map(path, pedals, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["default"] + [f"{s:g}" for s in SPEEDS])
        for p, row in zip(pedals, rows):
            w.writerow([f"{p:.3f}"] + [f"{a:.3f}" for a in row])
    print(f"wrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_connection_args(parser)
    parser.add_argument("--settle", type=float, default=0.5, help="throttle: seconds before measuring (gear/torque settle)")
    parser.add_argument("--brake-settle", type=float, default=0.1, help="brake: seconds before measuring (actuation lag)")
    parser.add_argument("--window", type=float, default=1.0, help="measurement window [s]")
    parser.add_argument("--out", default="ros/carla_autoware_ue5/calibration", help="output directory")
    args = parser.parse_args()

    client = connect(args)
    world = load_world(client, args.world)
    os.makedirs(args.out, exist_ok=True)

    with synchronous(world, args.dt):
        start = straightest_spawn_point(world)
        with spawned_vehicle(world, args.vehicle, start, "calibration") as ego:
            accel = []
            for p in ACCEL_PEDALS:
                row = [measure(world, ego, start, v, carla.VehicleControl(throttle=p), args.dt, args.settle, args.window) for v in SPEEDS]
                print(f"throttle {p:.1f}: " + " ".join(f"{a:+.2f}" for a in row))
                accel.append(row)
            brake = [accel[0]]  # pedal 0 is coasting in both maps
            for p in BRAKE_PEDALS[1:]:
                row = [measure(world, ego, start, v, carla.VehicleControl(brake=p), args.dt, args.brake_settle, args.window) for v in SPEEDS]
                print(f"brake    {p:.1f}: " + " ".join(f"{a:+.2f}" for a in row))
                brake.append(row)
            pedals = [x / 20 for x in range(1, 21)]
            creep_plain = start_throttle(world, ego, start, args.dt, pedals, nudge=0.0)
            creep_woken = start_throttle(world, ego, start, args.dt, pedals, nudge=0.2)

    accel, a_fixed = monotonic(accel, increasing=True)
    brake, b_fixed = monotonic(brake, increasing=False)
    if a_fixed or b_fixed:
        print("note: measurements were not strictly monotonic in pedal; clamped (noise, gear shifts, low-speed stops)")
    write_map(os.path.join(args.out, "accel_map.csv"), ACCEL_PEDALS, accel)
    write_map(os.path.join(args.out, "brake_map.csv"), BRAKE_PEDALS, brake)
    fmt = lambda p: "never" if p is None else f"{p:.2f}"
    print(f"lowest throttle that starts {args.vehicle} from rest: {fmt(creep_plain)} plain, {fmt(creep_woken)} after a wake nudge")
    if creep_plain is None and creep_woken is not None:
        print("-> keep wake_sleeping_physics:=true")
    if creep_woken is not None:
        print(f"-> min_positive_throttle:={creep_woken:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
