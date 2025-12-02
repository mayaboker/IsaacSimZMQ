cmake_minimum_required(VERSION 3.12)
project(isaac_zmq_msgpack_server CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Default to Release to avoid linking debug-suffixed OpenCV (e.g., *.so.4.5d)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

find_package(PkgConfig REQUIRED)
pkg_check_modules(PC_ZMQ REQUIRED libzmq)

find_path(ZMQ_INCLUDE_DIR zmq.hpp)
find_library(ZMQ_LIBRARY NAMES zmq)

find_path(MSGPACK_INCLUDE_DIR msgpack.hpp PATH_SUFFIXES msgpack)
find_library(MSGPACK_LIBRARY NAMES msgpackc msgpackc-static)

find_package(OpenCV REQUIRED COMPONENTS core imgproc highgui)

add_executable(msgpack_server msgpack_server.cpp)
target_include_directories(msgpack_server PRIVATE ${ZMQ_INCLUDE_DIR} ${MSGPACK_INCLUDE_DIR} ${OpenCV_INCLUDE_DIRS})
target_link_libraries(msgpack_server PRIVATE ${ZMQ_LIBRARY} ${MSGPACK_LIBRARY} ${OpenCV_LIBS})

message(STATUS "ZMQ include: ${ZMQ_INCLUDE_DIR}")
message(STATUS "ZMQ lib: ${ZMQ_LIBRARY}")
message(STATUS "MSGPACK include: ${MSGPACK_INCLUDE_DIR}")
message(STATUS "MSGPACK lib: ${MSGPACK_LIBRARY}")
message(STATUS "OpenCV include: ${OpenCV_INCLUDE_DIRS}")
message(STATUS "OpenCV libs: ${OpenCV_LIBS}")
