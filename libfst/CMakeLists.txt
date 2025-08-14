cmake_minimum_required(VERSION 3.15)
project(libfst C)

# Set C standard
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Find required packages
find_package(ZLIB REQUIRED)

# Define source files
set(SOURCES
    fstapi.c
    fastlz.c
    lz4.c
)

# Define header files
set(HEADERS
    fstapi.h
    fastlz.h
    lz4.h
    fst_config_stub.h
    fst_win_unistd.h
)

# Create the library
add_library(fst STATIC ${SOURCES} ${HEADERS})

# Set compiler-specific flags
if(MSVC)
    # MSVC specific flags
    target_compile_definitions(fst PRIVATE _CRT_SECURE_NO_WARNINGS)
    target_compile_options(fst PRIVATE /W3)
    # Use our config stub instead of config.h
    target_compile_definitions(fst PRIVATE FST_CONFIG_INCLUDE="fst_config_stub.h")
else()
    # GCC/Clang flags
    target_compile_options(fst PRIVATE -Wall -Wextra)
    # Use our config stub instead of config.h
    target_compile_definitions(fst PRIVATE FST_CONFIG_INCLUDE="fst_config_stub.h")
endif()

# Include directories
target_include_directories(fst PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

# Link with zlib
target_link_libraries(fst PRIVATE ZLIB::ZLIB)

# Platform-specific definitions
if(WIN32)
    target_compile_definitions(fst PRIVATE WIN32 _WIN32)
    if(MSVC)
        target_compile_definitions(fst PRIVATE _MSC_VER)
    endif()
endif()

# Set output name
set_target_properties(fst PROPERTIES OUTPUT_NAME "fst")

# Install target
install(TARGETS fst
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

install(FILES ${HEADERS} DESTINATION include)

# Test executable
option(BUILD_TESTS "Build test programs" ON)

if(BUILD_TESTS)
    # C++ test for FST reader
    add_executable(test_fst_reader test_fst_reader.cpp)
    
    # Set C++ standard
    set_target_properties(test_fst_reader PROPERTIES
        CXX_STANDARD 11
        CXX_STANDARD_REQUIRED ON
    )
    
    # Link with fst library
    target_link_libraries(test_fst_reader PRIVATE fst)
    
    # Copy test file to build directory for easier testing
    configure_file(${CMAKE_CURRENT_SOURCE_DIR}/test/vcd_extensions.fst
                   ${CMAKE_CURRENT_BINARY_DIR}/test/vcd_extensions.fst
                   COPYONLY)
    
    # Add test
    enable_testing()
    add_test(NAME test_fst_reader 
             COMMAND test_fst_reader
             WORKING_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR})
endif()
