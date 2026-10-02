"""Shared helpers for the CARLA client tools in this directory."""

import argparse
import contextlib
import math
import os
import sys

try:
    import carla
except ImportError:  # pragma: no cover - depends on the environment
    sys.exit(
        "error: the 'carla' module is not importable.\n"
        "Build the 0.10 client with scripts/build_client_wheel.sh and install "
        "dist/carla-*.whl, or run this tool inside the bridge image."
    )


def add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default=os.environ.get("CARLA_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CARLA_PORT", "2000")))
    parser.add_argument("--timeout", type=float, default=60.0, help="client RPC timeout [s]")
    parser.add_argument("--world", default=os.environ.get("CARLA_WORLD", "Town10HD_Opt"))
    parser.add_argument("--vehicle", default=os.environ.get("EGO_VEHICLE", "vehicle.lincoln.mkz"))
    parser.add_argument("--dt", type=float, default=0.05, help="fixed_delta_seconds (bridge default)")


def connect(args) -> "carla.Client":
    client = carla.Client(args.host, args.port)
    client.set_timeout(args.timeout)
    server = client.get_server_version()
    local = client.get_client_version()
    print(f"client {local}  server {server}")
    if server.split("-")[0] != local.split("-")[0]:
        sys.exit(f"error: client {local} does not match server {server}; rebuild the wheel for the server's tag")
    return client


def load_world(client: "carla.Client", name: str) -> "carla.World":
    world = client.get_world()
    current = world.get_map().name.split("/")[-1]
    if current != name:
        print(f"loading world {name} (was {current})")
        world = client.load_world(name)
    return world


@contextlib.contextmanager
def synchronous(world: "carla.World", dt: float):
    """Run the world in synchronous fixed-step mode, restoring the old settings on exit."""
    original = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = dt
    world.apply_settings(settings)
    try:
        yield
    finally:
        world.apply_settings(original)


@contextlib.contextmanager
def spawned_vehicle(world: "carla.World", blueprint_id: str, transform: "carla.Transform", role: str):
    library = world.get_blueprint_library()
    matches = library.filter(blueprint_id)
    if not matches:
        sys.exit(f"error: blueprint {blueprint_id} is not in this server's catalogue")
    bp = matches[0]
    bp.set_attribute("role_name", role)
    vehicle = world.try_spawn_actor(bp, transform)
    if vehicle is None:
        sys.exit(f"error: could not spawn {blueprint_id} at {transform.location}")
    try:
        world.tick()
        yield vehicle
    finally:
        vehicle.destroy()
        world.tick()


def forward_speed(vehicle: "carla.Vehicle") -> float:
    """Signed speed along the vehicle's heading [m/s]."""
    v = vehicle.get_velocity()
    f = vehicle.get_transform().get_forward_vector()
    return v.x * f.x + v.y * f.y + v.z * f.z


def straightest_spawn_point(world: "carla.World", min_length: float = 60.0) -> "carla.Transform":
    """Spawn point with the longest straight drivable lane ahead of it."""
    cmap = world.get_map()
    best, best_len = None, -1.0
    for sp in cmap.get_spawn_points():
        wp = cmap.get_waypoint(sp.location)
        if wp is None:
            continue
        yaw0, length = wp.transform.rotation.yaw, 0.0
        while length < 300.0:
            nxt = wp.next(2.0)
            if not nxt:
                break
            wp = nxt[0]
            if abs((wp.transform.rotation.yaw - yaw0 + 180.0) % 360.0 - 180.0) > 3.0:
                break
            length += 2.0
        if length > best_len:
            best, best_len = sp, length
    if best is None:
        sys.exit("error: this world has no spawn points")
    if best_len < min_length:
        print(f"warning: longest straight lane is only {best_len:.0f} m")
    print(f"spawn {best.location} yaw {best.rotation.yaw:.1f}, {best_len:.0f} m straight ahead")
    best.location.z += 0.5
    return best


def heading_vector(transform: "carla.Transform", speed: float) -> "carla.Vector3D":
    yaw = math.radians(transform.rotation.yaw)
    return carla.Vector3D(speed * math.cos(yaw), speed * math.sin(yaw), 0.0)
