#!/usr/bin/env python3
"""End-to-end check that a CARLA 0.10 server can be driven the way the bridge drives it.

Connects with the locally installed client, checks the versions match, loads
the world, spawns the ego blueprint in synchronous mode and tries to drive it.
It also reports the two CARLA 0.10 quirks the bridge preset works around:

* a resting Chaos body ignores throttle until it is woken (wake_sleeping_physics)
* a speed->steering curve whose points are out of order (flatten_steering_curve)

Exit status is 0 when the ego can be made to move, 1 otherwise.
"""

import argparse
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


def steering_curve_corrupt(vehicle) -> bool:
    """True when the speed->steer curve is not ordered by speed (a CARLA 0.10 asset defect)."""
    xs = [p.x for p in vehicle.get_physics_control().steering_curve]
    return any(b < a for a, b in zip(xs, xs[1:]))


def drive(world, vehicle, start, throttle, seconds, dt, nudge, rest) -> float:
    """Teleport to start, rest, optionally nudge, hold throttle; return distance travelled [m]."""
    vehicle.set_transform(start)
    vehicle.set_target_velocity(carla.Vector3D())
    vehicle.apply_control(carla.VehicleControl(brake=1.0))
    for _ in range(int(rest / dt)):
        world.tick()
    origin = vehicle.get_location()
    if nudge > 0.0:
        vehicle.set_target_velocity(heading_vector(start, nudge))
    vehicle.apply_control(carla.VehicleControl(throttle=throttle))
    for _ in range(int(seconds / dt)):
        world.tick()
    return vehicle.get_location().distance(origin)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_connection_args(parser)
    parser.add_argument("--throttle", type=float, default=0.5)
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--rest", type=float, default=10.0, help="seconds at rest before pulling away (lets Chaos put the body to sleep)")
    args = parser.parse_args()

    client = connect(args)
    world = load_world(client, args.world)
    print(f"world {world.get_map().name}, {len(world.get_map().get_spawn_points())} spawn points")

    with synchronous(world, args.dt):
        start = straightest_spawn_point(world)
        with spawned_vehicle(world, args.vehicle, start, "smoke_test") as ego:
            steer = ego.get_physics_control().wheels[0].max_steer_angle
            corrupt = steering_curve_corrupt(ego)
            print(f"ego {args.vehicle}: max front wheel steer {steer:.1f} deg, steering curve {'CORRUPT' if corrupt else 'ok'}")
            if corrupt:
                print("result: steering curve out of order -> keep flatten_steering_curve:=true")

            plain = drive(world, ego, start, args.throttle, args.seconds, args.dt, 0.0, args.rest)
            print(f"throttle {args.throttle} for {args.seconds} s after {args.rest:g} s at rest: {plain:.2f} m")
            woken = drive(world, ego, start, args.throttle, args.seconds, args.dt, 0.2, args.rest)
            print(f"same, after a 0.2 m/s wake nudge: {woken:.2f} m, {forward_speed(ego):.2f} m/s")

    if plain < 0.5 <= woken:
        print("result: sleeping-body quirk present -> keep wake_sleeping_physics:=true")
    moved = max(plain, woken) >= 0.5
    print("PASS" if moved else "FAIL: ego did not move")
    return 0 if moved else 1


if __name__ == "__main__":
    sys.exit(main())
