cmake_minimum_required(VERSION 3.8)
project(grpc_bridge)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 1. Находим только те пакеты, которые реально имеют CMake-конфиги
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(nlohmann_json REQUIRED)
find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

set(PROTO_FILE "proto/telemetry.proto")

protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS ${PROTO_FILE})

set(GRPC_SRCS "${CMAKE_CURRENT_BINARY_DIR}/telemetry.grpc.pb.cc")
set(GRPC_HDRS "${CMAKE_CURRENT_BINARY_DIR}/telemetry.grpc.pb.h")
add_custom_command(
    OUTPUT "${GRPC_SRCS}" "${GRPC_HDRS}"
    COMMAND ${Protobuf_PROTOC_EXECUTABLE}
    ARGS --grpc_out="${CMAKE_CURRENT_BINARY_DIR}"
         --plugin=protoc-gen-grpc=$<TARGET_FILE:gRPC::grpc_cpp_plugin>
         -I "${CMAKE_CURRENT_SOURCE_DIR}/proto"
         "${CMAKE_CURRENT_SOURCE_DIR}/${PROTO_FILE}"
    DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/${PROTO_FILE}"
)

add_executable(grpc_bridge_node
  src/grpc_bridge_node.cpp
  ${PROTO_SRCS}
  ${GRPC_SRCS}
)

target_include_directories(grpc_bridge_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}>
)

target_compile_features(grpc_bridge_node PUBLIC c_std_99 cxx_std_17)

ament_target_dependencies(
  grpc_bridge_node
  "rclcpp"
  "std_msgs"
  "geometry_msgs"
  "sensor_msgs"
  "nav_msgs"
  "tf2_ros"
  "tf2_geometry_msgs"
)

target_link_libraries(grpc_bridge_node
  nlohmann_json::nlohmann_json
  gRPC::grpc++
  ${Protobuf_LIBRARIES}
  utf8_validity
)

install(TARGETS grpc_bridge_node
  DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
