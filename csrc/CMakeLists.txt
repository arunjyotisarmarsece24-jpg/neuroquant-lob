cmake_minimum_required(VERSION 3.20)
project(neuroquant_lif_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(lif_core SHARED
    lif_core.cpp
    lif_core.h
)

target_compile_definitions(lif_core PRIVATE LIF_EXPORTS)

# Modern SIMD flags for GCC/Clang and MSVC
if(MSVC)
    target_compile_options(lif_core PRIVATE /O2 /arch:AVX2 /fp:fast)
else()
    target_compile_options(lif_core PRIVATE -O3 -mavx2 -mfma -ffast-math)
    if(WIN32)
        target_link_options(lif_core PRIVATE -static -static-libgcc -static-libstdc++)
    endif()
endif()

set_target_properties(lif_core PROPERTIES
    PREFIX ""
    OUTPUT_NAME "lif_core"
)
