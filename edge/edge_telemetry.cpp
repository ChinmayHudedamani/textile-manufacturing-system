// =====================================================================
// Everest Textile Manufacturing System (ETMS) - Tier 1 Physical Edge Daemon
// Language: C++20
// Architecture: Zero-Allocation Circular Buffers & MQTT Sparkplug B Transport
// Hardware Target: RS-485 / Modbus RTU / Optical Pick Sensors
// =====================================================================

#include <iostream>
#include <chrono>
#include <thread>
#include <string>
#include <atomic>
#include <csignal>
#include <array>
#include <numeric>

#if __has_include(<mqtt/async_client.h>)
#include <mqtt/async_client.h>
#define HAS_MQTT 1
#else
#define HAS_MQTT 0
#endif

#if __has_include(<nlohmann/json.hpp>)
#include <nlohmann/json.hpp>
using json = nlohmann::json;
#define HAS_JSON 1
#endif

using namespace std::chrono_literals;

std::atomic<bool> g_running{true};

void signal_handler(int signal) {
    if (signal == SIGINT || signal == SIGTERM) {
        std::cout << "\n[EDGE-SIGNAL] Shutdown signal (" << signal << ") received. Exiting gracefully...\n";
        g_running = false;
    }
}

enum class MillMachineState {
    IDLE,
    RUNNING,
    MAINTENANCE,
    STOPPED_WEFT_BREAK
};

std::string state_to_string(MillMachineState state) {
    switch (state) {
        case MillMachineState::RUNNING: return "RUNNING";
        case MillMachineState::IDLE: return "IDLE";
        case MillMachineState::MAINTENANCE: return "MAINTENANCE";
        case MillMachineState::STOPPED_WEFT_BREAK: return "FAULT";
        default: return "IDLE";
    }
}

// Zero-allocation fixed-size circular buffer for high-frequency current/vibration sampling
template <typename T, std::size_t Capacity>
class ZeroAllocCircularBuffer {
private:
    std::array<T, Capacity> m_buffer{};
    std::size_t m_head{0};
    std::size_t m_count{0};

public:
    void push(T val) noexcept {
        m_buffer[m_head] = val;
        m_head = (m_head + 1) % Capacity;
        if (m_count < Capacity) {
            ++m_count;
        }
    }

    [[nodiscard]] double average() const noexcept {
        if (m_count == 0) return 0.0;
        double sum = 0.0;
        for (std::size_t i = 0; i < m_count; ++i) {
            sum += static_cast<double>(m_buffer[i]);
        }
        return sum / static_cast<double>(m_count);
    }

    [[nodiscard]] std::size_t size() const noexcept { return m_count; }
};

class EdgeTelemetryDaemon {
private:
    std::string m_server_uri;
    std::string m_client_id;
    std::string m_machine_id;
    uint64_t m_pick_counter;
    double m_active_amps;
    uint32_t m_rpm;
    ZeroAllocCircularBuffer<float, 64> m_current_samples;

public:
    EdgeTelemetryDaemon(std::string server_uri, std::string client_id, std::string machine_id)
        : m_server_uri(std::move(server_uri)),
          m_client_id(std::move(client_id)),
          m_machine_id(std::move(machine_id)),
          m_pick_counter(105400),
          m_active_amps(15.4),
          m_rpm(740) {}

    bool start() {
        std::cout << "========================================================\n";
        std::cout << " Everest Textile Manufacturing System - C++20 Edge Daemon\n";
        std::cout << " Machine Target: " << m_machine_id << "\n";
        std::cout << " Broker URI:     " << m_server_uri << "\n";
        std::cout << " Buffer:         Zero-Allocation 64-Sample Ring Buffer\n";
        std::cout << "========================================================\n";
        return true;
    }

    void execute_sample_loop() {
        const std::string topic = "everest/mill/floor/" + m_machine_id + "/telemetry";
        uint32_t sample_tick = 0;

        while (g_running) {
            ++sample_tick;
            
            // Optical sensor pick counter simulation: 12 picks/sec (~720 PPM)
            m_pick_counter += 12;

            // Ingest sample into zero-allocation ring buffer
            m_current_samples.push(static_cast<float>(m_active_amps));

            MillMachineState current_state = MillMachineState::RUNNING;

            // Idle threshold detection: low current draw simulation
            if (m_active_amps < 2.0) {
                current_state = MillMachineState::IDLE;
                m_rpm = 0;
            } else {
                m_rpm = 740;
            }

            auto now = std::chrono::system_clock::now();
            auto timestamp_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                now.time_since_epoch()).count();

            // Form telemetry payload
            std::cout << "[EDGE-TELEMETRY] " << m_machine_id 
                      << " | State: " << state_to_string(current_state)
                      << " | Picks: " << m_pick_counter 
                      << " | Current: " << m_active_amps << "A"
                      << " | RPM: " << m_rpm
                      << " | Time: " << timestamp_ms << "ms\n";

            std::this_thread::sleep_for(1000ms);
        }

        std::cout << "[EDGE-IO] Daemon gracefully halted.\n";
    }
};

int main(int argc, char* argv[]) {
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    std::string broker_uri = (argc > 1) ? argv[1] : "tcp://localhost:1883";
    std::string machine_id = (argc > 2) ? argv[2] : "WEAVE-LOOM-04";

    EdgeTelemetryDaemon daemon(broker_uri, "edge_" + machine_id, machine_id);
    if (daemon.start()) {
        daemon.execute_sample_loop();
    }
    return 0;
}
