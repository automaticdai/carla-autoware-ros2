cmake_minimum_required(VERSION 3.8)
project(carla_autoware_ue5 NONE)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch config calibration DESTINATION share/${PROJECT_NAME}/)

ament_package()
