cmake_minimum_required(VERSION 3.20)
project(etms_edge_daemon LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(edge_telemetry edge_telemetry.cpp)

# Optional dependencies if building on system with Paho MQTT and nlohmann_json
find_package(PahoMqttCpp QUIET)
find_package(nlohmann_json QUIET)

if(TARGET PahoMqttCpp::paho-mqttpp3)
    target_link_libraries(edge_telemetry PRIVATE PahoMqttCpp::paho-mqttpp3)
endif()

if(TARGET nlohmann_json::nlohmann_json)
    target_link_libraries(edge_telemetry PRIVATE nlohmann_json::nlohmann_json)
endif()
