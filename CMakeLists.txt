cmake_minimum_required(VERSION 3.16)
project(SRDetector LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(Geant4 REQUIRED ui_all vis_all)
include(${Geant4_USE_FILE})

file(GLOB SRDET_SOURCES ${PROJECT_SOURCE_DIR}/app/src/*.cc)
add_executable(srdet-sim ${PROJECT_SOURCE_DIR}/app/srdet.cc ${SRDET_SOURCES})
target_include_directories(srdet-sim PRIVATE ${PROJECT_SOURCE_DIR}/app/include)
target_link_libraries(srdet-sim PRIVATE ${Geant4_LIBRARIES})
target_compile_options(srdet-sim PRIVATE -Wall -Wextra -Wno-unused-parameter)

install(TARGETS srdet-sim DESTINATION bin)
