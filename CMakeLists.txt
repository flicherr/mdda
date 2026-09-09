cmake_minimum_required(VERSION 3.20)

project(
    module_declaration_dependency_analysis
    VERSION 0.4.0
    DESCRIPTION "Experimental analysis of declaration dependencies in modules"
    LANGUAGES C CXX
)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(MANALYZER_ENABLE_WARNINGS "Enable strict warnings for manalyzer" ON)

add_subdirectory(analyzer)
