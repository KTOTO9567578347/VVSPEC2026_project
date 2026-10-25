cmake_minimum_required(VERSION 3.8)
project(grpc_bridge)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# 1. Находим только те пакеты, которые реально имеют CMake-конфиги
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)
find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)
find_package(nav_msgs REQUIRED)

# nlohmann_json ОТСЮДА ПОЛНОСТЬЮ УБРАЛИ. Больше никаких find_package для него.

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

# 2. РЕШЕНИЕ: Просто явно говорим компилятору заглядывать в системную папку include,
# где и лежит наш nlohmann_json после установки через package.xml!
target_include_directories(grpc_bridge_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}>
  /usr/include # <-- Системный путь, где гарантированно лежит nlohmann/json.hpp
)

target_compile_features(grpc_bridge_node PUBLIC c_std_99 cxx_std_17)

# Передаем в ament только чистокровные ROS-пакеты
ament_target_dependencies(
  grpc_bridge_node
  nav_msgs
  "rclcpp"
  "std_msgs"
  "sensor_msgs"
  "tf2_ros"
  "tf2_geometry_msgs"
)

# Линкуем только gRPC и Protobuf. JSON линковать не надо (он header-only)
target_link_libraries(grpc_bridge_node
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
