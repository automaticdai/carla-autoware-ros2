#!/usr/bin/env python3
"""Closed-loop drive through Autoware's AD API, the calls RViz makes.

Initializes localization from the GNSS pose, sets a goal DISTANCE metres
straight ahead, engages autonomous mode and waits for the route to report
ARRIVED. Exit status 0 on arrival. Spawn the ego on a straight lane
(SPAWN_POINT) so the goal lands on the same lane.

Two refusals are normal on a fresh stack and are retried past: the explicit
localization init can return "The vehicle is not stopped" while Autoware's
automatic GNSS initializer completes it anyway, and the first route request
can return "The route is already set" before the next one succeeds.
"""

import argparse
import math
import sys
import time

import rclpy
from autoware_adapi_v1_msgs.msg import LocalizationInitializationState, OperationModeState, RouteState
from autoware_adapi_v1_msgs.srv import ChangeOperationMode, InitializeLocalization, SetRoutePoints
from geometry_msgs.msg import Pose, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import DurabilityPolicy, QoSProfile

API_QOS = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)


class DriveTest(Node):
    def __init__(self):
        super().__init__("drive_test", parameter_overrides=[Parameter("use_sim_time", value=True)])
        self.latest = {}
        for key, msg_type, topic, qos in (
            ("gnss", PoseWithCovarianceStamped, "/sensing/gnss/pose_with_covariance", 1),
            ("odom", Odometry, "/localization/kinematic_state", 1),
            ("localization", LocalizationInitializationState, "/api/localization/initialization_state", API_QOS),
            ("route", RouteState, "/api/routing/state", API_QOS),
            ("mode", OperationModeState, "/api/operation_mode/state", API_QOS),
        ):
            self.create_subscription(msg_type, topic, lambda m, k=key: self.latest.__setitem__(k, m), qos)

    def get(self, key):
        return self.latest.get(key)

    def wait_for(self, cond, what, timeout):
        start = time.time()
        while time.time() - start < timeout:
            rclpy.spin_once(self, timeout_sec=0.2)
            if cond():
                print(f"ok: {what} ({time.time() - start:.0f} s)", flush=True)
                return
        sys.exit(f"TIMEOUT after {timeout} s: {what}")

    def call(self, srv_type, name, request, timeout=30.0):
        client = self.create_client(srv_type, name)
        if not client.wait_for_service(timeout_sec=timeout):
            sys.exit(f"service {name} not available")
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=timeout)
        status = future.result().status
        print(f"{name}: success={status.success} {status.message!r}", flush=True)
        return status.success


def yaw_of(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--distance", type=float, default=80.0, help="goal distance ahead [m]")
    parser.add_argument("--timeout", type=float, default=180.0, help="seconds allowed to arrive")
    args = parser.parse_args()

    rclpy.init()
    node = DriveTest()
    node.wait_for(lambda: node.get("gnss") and node.get("localization"), "GNSS pose and localization state", 240)

    start = node.get("gnss")
    start.pose.covariance = [0.0] * 36
    for i, var in ((0, 0.25), (7, 0.25), (35, 0.07)):  # x, y, yaw
        start.pose.covariance[i] = var
    yaw = yaw_of(start.pose.pose.orientation)
    print(f"start x={start.pose.pose.position.x:.1f} y={start.pose.pose.position.y:.1f} yaw={math.degrees(yaw):.1f} deg")
    if node.get("localization").state != LocalizationInitializationState.INITIALIZED:
        node.call(InitializeLocalization, "/api/localization/initialize", InitializeLocalization.Request(pose=[start]), 60)
    node.wait_for(lambda: node.get("localization").state == LocalizationInitializationState.INITIALIZED, "localization initialized", 120)
    node.wait_for(lambda: node.get("odom"), "kinematic state", 60)

    origin = node.get("odom").pose.pose.position
    goal = Pose()
    goal.position.x = origin.x + args.distance * math.cos(yaw)
    goal.position.y = origin.y + args.distance * math.sin(yaw)
    goal.position.z = origin.z
    goal.orientation = start.pose.pose.orientation
    route = SetRoutePoints.Request(goal=goal)
    route.header.frame_id = "map"
    for _ in range(10):  # planning may still be loading the map
        if node.call(SetRoutePoints, "/api/routing/set_route_points", route):
            break
        time.sleep(3)
    node.wait_for(lambda: node.get("route") and node.get("route").state == RouteState.SET, "route set", 60)
    node.wait_for(lambda: node.get("mode") and node.get("mode").is_autonomous_mode_available, "autonomous mode available", 120)
    node.call(ChangeOperationMode, "/api/operation_mode/change_to_autonomous", ChangeOperationMode.Request())

    t0 = last_report = time.time()
    while time.time() - t0 < args.timeout:
        rclpy.spin_once(node, timeout_sec=0.2)
        odom = node.get("odom")
        p = odom.pose.pose.position
        travelled = math.hypot(p.x - origin.x, p.y - origin.y)
        if node.get("route").state == RouteState.ARRIVED:
            print(f"ARRIVED after {time.time() - t0:.0f} s, travelled {travelled:.1f} m")
            return 0
        if time.time() - last_report >= 5:
            last_report = time.time()
            remaining = math.hypot(p.x - goal.position.x, p.y - goal.position.y)
            print(f"t={time.time() - t0:4.0f} s  travelled {travelled:5.1f} m  v={odom.twist.twist.linear.x:4.1f} m/s  remaining {remaining:5.1f} m", flush=True)
    print(f"FAIL: did not arrive within {args.timeout:.0f} s")
    return 1


if __name__ == "__main__":
    sys.exit(main())
