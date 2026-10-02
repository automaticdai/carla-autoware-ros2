#!/usr/bin/env python3
"""Publish empty perception outputs so Autoware can plan with perception:=false.

For hosts without a GPU or perception models (headless mode): planning waits
for these topics and will not produce a trajectory without them. The world is
reported as free of obstacles, so this is for exercising localization,
planning, control and the CARLA bridge, not for driving among traffic.
"""

import rclpy
from autoware_perception_msgs.msg import PredictedObjects
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import PointCloud2, PointField

GRID_RESOLUTION = 0.5  # m
GRID_CELLS = 400  # 200 m x 200 m, centred on the ego


class PerceptionStub(Node):
    def __init__(self):
        super().__init__("perception_stub", parameter_overrides=[Parameter("use_sim_time", value=True)])
        self.objects = self.create_publisher(PredictedObjects, "/perception/object_recognition/objects", 1)
        self.grid = self.create_publisher(OccupancyGrid, "/perception/occupancy_grid_map/map", 1)
        self.cloud = self.create_publisher(PointCloud2, "/perception/obstacle_segmentation/pointcloud", 1)
        self.odom = None
        self.create_subscription(Odometry, "/localization/kinematic_state", self._on_odom, 1)
        self.create_timer(0.1, self._publish)

    def _on_odom(self, msg):
        self.odom = msg

    def _publish(self):
        stamp = self.get_clock().now().to_msg()

        objects = PredictedObjects()
        objects.header.stamp, objects.header.frame_id = stamp, "map"
        self.objects.publish(objects)

        cloud = PointCloud2()
        cloud.header.stamp, cloud.header.frame_id = stamp, "base_link"
        cloud.height, cloud.width, cloud.point_step, cloud.is_dense = 1, 0, 12, True
        cloud.fields = [PointField(name=n, offset=4 * i, datatype=PointField.FLOAT32, count=1) for i, n in enumerate("xyz")]
        self.cloud.publish(cloud)

        if self.odom is None:
            return  # the grid is placed around the ego
        grid = OccupancyGrid()
        grid.header.stamp, grid.header.frame_id = stamp, "map"
        grid.info.resolution = GRID_RESOLUTION
        grid.info.width = grid.info.height = GRID_CELLS
        half = GRID_RESOLUTION * GRID_CELLS / 2
        grid.info.origin.position.x = self.odom.pose.pose.position.x - half
        grid.info.origin.position.y = self.odom.pose.pose.position.y - half
        grid.info.origin.orientation.w = 1.0
        grid.data = [0] * (GRID_CELLS * GRID_CELLS)  # all free
        self.grid.publish(grid)


def main():
    rclpy.init()
    rclpy.spin(PerceptionStub())


if __name__ == "__main__":
    main()
