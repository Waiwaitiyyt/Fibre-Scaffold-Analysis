cmake_minimum_required(VERSION 3.15)
project(FiberAnalyzer VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "Project directory: ${CMAKE_SOURCE_DIR}")

# 去掉固定的 3.11，让调用方决定 Python 版本
find_package(Python COMPONENTS Interpreter Development REQUIRED)
message(STATUS "Found Python: ${Python_VERSION}")
message(STATUS "Python include: ${Python_INCLUDE_DIRS}")

add_subdirectory(src/cpp/extern/pybind11)
message(STATUS "Using bundled pybind11")

# 本地开发时仍输出到 lib/，wheel 构建时 scikit-build-core 会覆盖这个
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/lib)

foreach(CONFIG ${CMAKE_CONFIGURATION_TYPES})
    string(TOUPPER ${CONFIG} CONFIG_UPPER)
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_${CONFIG_UPPER} ${CMAKE_SOURCE_DIR}/lib)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_${CONFIG_UPPER} ${CMAKE_SOURCE_DIR}/lib)
endforeach()

set(SOURCES
    ${CMAKE_SOURCE_DIR}/src/cpp/measure_tool.cpp
)

foreach(SOURCE_FILE ${SOURCES})
    if(NOT EXISTS ${SOURCE_FILE})
        message(FATAL_ERROR "Source file not found: ${SOURCE_FILE}")
    else()
        message(STATUS "Found source file: ${SOURCE_FILE}")
    endif()
endforeach()

pybind11_add_module(measure_tool ${SOURCES})

if(MSVC)
    target_compile_options(measure_tool PRIVATE
        /O2 /W3 /utf-8 /bigobj
    )
    target_compile_definitions(measure_tool PRIVATE
        _CRT_SECURE_NO_WARNINGS
        _SILENCE_ALL_CXX17_DEPRECATION_WARNINGS
    )
else()
    target_compile_options(measure_tool PRIVATE
        -O3 -Wall -Wextra
        # 去掉 -march=native，CI 环境 CPU 架构不固定，会导致非法指令
    )
endif()

# ============================================
# 关键：告诉 scikit-build-core 把 .pyd/.so 装到 wheel 根目录
# ============================================
install(TARGETS measure_tool DESTINATION .)

message(STATUS "")
message(STATUS "===========================================")
message(STATUS "Configuration Summary:")
message(STATUS "  Module name: measure_tool")
message(STATUS "  Output directory: ${CMAKE_SOURCE_DIR}/lib")
message(STATUS "  Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "  Python: ${Python_VERSION}")
message(STATUS "  Compiler: ${CMAKE_CXX_COMPILER_ID}")
message(STATUS "===========================================")
message(STATUS "")