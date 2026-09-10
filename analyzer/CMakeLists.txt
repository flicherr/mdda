find_package(LLVM 22.1.8 EXACT CONFIG REQUIRED)
find_package(Clang 22.1.8 EXACT CONFIG REQUIRED)

message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
message(STATUS "Using LLVMConfig.cmake in: ${LLVM_DIR}")
message(STATUS "Using ClangConfig.cmake in: ${Clang_DIR}")

add_executable(manalyzer
    src/main.cpp
    src/Analyzer.cpp
    src/Normalizer.cpp
    src/StableId.cpp
)

# Keep the documented path stable even though this target is declared in a
# subdirectory of the top-level CMake project.
set_target_properties(manalyzer PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
)

target_include_directories(manalyzer
    PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_include_directories(manalyzer
    SYSTEM PRIVATE
    ${LLVM_INCLUDE_DIRS}
    ${CLANG_INCLUDE_DIRS}
)

add_definitions(${LLVM_DEFINITIONS})

if(MANALYZER_ENABLE_WARNINGS)
    if(MSVC)
        target_compile_options(manalyzer PRIVATE /W4 /permissive-)
    else()
        target_compile_options(manalyzer PRIVATE -Wall -Wextra -Wpedantic)
    endif()
endif()

target_compile_definitions(manalyzer
    PRIVATE MANALYZER_VERSION="${PROJECT_VERSION}"
)

set(MANALYZER_CLANG_LIBRARIES)
if(TARGET clang-cpp)
    # Prefer the monolithic target when the package exports it so the package
    # supplies all transitive link dependencies and library paths.
    list(APPEND MANALYZER_CLANG_LIBRARIES clang-cpp)
else()
    find_library(MANALYZER_CLANG_CPP_LIBRARY
        NAMES clang-cpp libclang-cpp.so.22.1 libclang-cpp.so.22
        HINTS ${LLVM_LIBRARY_DIRS}
    )
    if(MANALYZER_CLANG_CPP_LIBRARY)
        list(APPEND MANALYZER_CLANG_LIBRARIES ${MANALYZER_CLANG_CPP_LIBRARY})
    else()
        # Static/component fallback for installations built without clang-cpp.
        foreach(CLANG_TARGET
            clangTooling
            clangToolingCore
            clangFrontend
            clangSerialization
            clangIndex
            clangAST
            clangLex
            clangBasic)
            if(NOT TARGET ${CLANG_TARGET})
                message(FATAL_ERROR
                    "Clang pkg exports neither clang-cpp nor ${CLANG_TARGET}. "
                    "Set Clang_DIR to the Clang 22.1.8 CMake package directory."
                )
            endif()
            list(APPEND MANALYZER_CLANG_LIBRARIES ${CLANG_TARGET})
        endforeach()
    endif()
endif()

set(MANALYZER_LLVM_LIBRARIES)
if(TARGET LLVM)
    list(APPEND MANALYZER_LLVM_LIBRARIES LLVM)
else()
    find_library(MANALYZER_LLVM_DYLIB
        NAMES LLVM LLVM-22 libLLVM.so.22.1 libLLVM.so.22
        HINTS ${LLVM_LIBRARY_DIRS}
    )
    if(MANALYZER_LLVM_DYLIB)
        list(APPEND MANALYZER_LLVM_LIBRARIES ${MANALYZER_LLVM_DYLIB})
    else()
        # Component-based SDK fallback when no monolithic library is installed.
        llvm_map_components_to_libnames(MANALYZER_LLVM_LIBRARIES option support)
    endif()
endif()

target_link_libraries(manalyzer
    PRIVATE
    ${MANALYZER_CLANG_LIBRARIES}
    ${MANALYZER_LLVM_LIBRARIES}
)

install(TARGETS manalyzer RUNTIME DESTINATION bin)
