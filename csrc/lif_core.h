#pragma once

#include <cstdint>
#include <cstddef>
#include <cmath>
#include <cstring>
#include <immintrin.h>
#include <x86intrin.h>

#if defined(_WIN32) || defined(__CYGWIN__)
  #ifdef LIF_EXPORTS
    #define LIF_API __declspec(dllexport)
  #else
    #define LIF_API __declspec(dllimport)
  #endif
#else
  #define LIF_API __attribute__((visibility("default")))
#endif

// Institutional HFT Constants & Cache-Line Alignment
constexpr size_t CACHE_LINE_SIZE = 64;
constexpr size_t MAX_NEURONS_PER_POP = 256;
constexpr size_t MAX_HISTORY_STEPS = 256;

#pragma pack(push, 8)
struct LIFConfig {
    float dt;                   // Simulation step (ms), e.g. 0.5
    float tau_m;                // Membrane time constant (ms), e.g. 20.0
    float v_rest;               // Resting potential (mV), e.g. -70.0
    float v_reset;              // Hyperpolarization reset (mV), e.g. -75.0
    float v_thresh;             // Firing threshold (mV), e.g. -55.0
    float refractory_period_ms; // Absolute refractory duration (ms), e.g. 2.0
    int32_t refractory_steps;   // int(refractory_period_ms / dt)
    float decay;                // exp(-dt / tau_m)
    float c_rest;               // v_rest * (1.0f - decay)
};

struct BenchmarkStats {
    uint64_t total_steps;
    uint64_t total_cycles;
    uint64_t min_cycles;
    uint64_t max_cycles;
    double p50_cycles;
    double p90_cycles;
    double p99_cycles;
    double p999_cycles;
    double avg_nanoseconds;
    double steps_per_second;
};
#pragma pack(pop)

namespace neuroquant {

using ::LIFConfig;
using ::BenchmarkStats;

// High-precision non-serializing / serializing RDTSCP hardware cycle read
[[nodiscard]] inline uint64_t rdtscp() noexcept {
    unsigned int aux;
    return __rdtscp(&aux);
}

// 64-byte aligned SIMD-optimized Leaky Integrate-and-Fire Population
class alignas(CACHE_LINE_SIZE) LIFPopulationSIMD {
public:
    size_t size{0};
    LIFConfig cfg{};
    uint64_t total_steps{0};

    // State memory pools strictly aligned to 64-byte L1 cache-line boundaries
    alignas(CACHE_LINE_SIZE) float voltage[MAX_NEURONS_PER_POP];
    alignas(CACHE_LINE_SIZE) float threshold[MAX_NEURONS_PER_POP];
    alignas(CACHE_LINE_SIZE) int32_t refractory_timer[MAX_NEURONS_PER_POP];
    alignas(CACHE_LINE_SIZE) uint8_t spikes[MAX_NEURONS_PER_POP];
    alignas(CACHE_LINE_SIZE) uint64_t spike_counts[MAX_NEURONS_PER_POP];

    LIFPopulationSIMD() noexcept {
        reset();
    }

    void init(size_t num_neurons, const LIFConfig& config) noexcept {
        size = (num_neurons > MAX_NEURONS_PER_POP) ? MAX_NEURONS_PER_POP : num_neurons;
        cfg = config;
        if (cfg.dt <= 0.0f) cfg.dt = 0.5f;
        if (cfg.tau_m <= 0.0f) cfg.tau_m = 20.0f;
        cfg.decay = std::exp(-cfg.dt / cfg.tau_m);
        cfg.c_rest = cfg.v_rest * (1.0f - cfg.decay);
        cfg.refractory_steps = static_cast<int32_t>(cfg.refractory_period_ms / cfg.dt);
        reset();
    }

    void reset() noexcept {
        total_steps = 0;
        for (size_t i = 0; i < MAX_NEURONS_PER_POP; ++i) {
            voltage[i] = cfg.v_rest;
            threshold[i] = cfg.v_thresh;
            refractory_timer[i] = 0;
            spikes[i] = 0;
            spike_counts[i] = 0;
        }
    }

    // Modern C++20 AVX2 / AVX-512 Vectorized Hot-Path Kernel
    // Zero dynamic allocations; full register saturation; FMA single-cycle fused MAC
    void step_vectorized(const float* __restrict synaptic_current, uint8_t* __restrict out_spikes) noexcept;

    // Scalar fallback kernel for tail elements or reference verification
    void step_scalar(const float* __restrict synaptic_current, uint8_t* __restrict out_spikes) noexcept;
};

// Recurrent Neuromorphic Spiking Network SIMD Core (Sensory -> Hidden Reservoir -> Readout)
class alignas(CACHE_LINE_SIZE) RSNNCoreSIMD {
public:
    size_t num_sensory{32};
    size_t num_hidden{64};
    size_t num_motor{4};

    LIFPopulationSIMD sensory_pop;
    LIFPopulationSIMD hidden_pop;
    LIFPopulationSIMD motor_pop;

    // Aligned Flat Synaptic Weight Matrices: Row-major
    // W_in_hidden: [num_sensory x num_hidden]
    alignas(CACHE_LINE_SIZE) float w_in_hidden[MAX_NEURONS_PER_POP * MAX_NEURONS_PER_POP];
    // W_hidden_hidden: [num_hidden x num_hidden]
    alignas(CACHE_LINE_SIZE) float w_hidden_hidden[MAX_NEURONS_PER_POP * MAX_NEURONS_PER_POP];
    // W_motor: [num_hidden x num_motor]
    alignas(CACHE_LINE_SIZE) float w_motor[MAX_NEURONS_PER_POP * MAX_NEURONS_PER_POP];

    // Preallocated current accumulation buffers (zero heap allocation during tick)
    alignas(CACHE_LINE_SIZE) float current_sensory[MAX_NEURONS_PER_POP];
    alignas(CACHE_LINE_SIZE) float current_hidden[MAX_NEURONS_PER_POP];
    alignas(CACHE_LINE_SIZE) float current_motor[MAX_NEURONS_PER_POP];

    RSNNCoreSIMD() noexcept = default;

    void init(size_t n_sensory, size_t n_hidden, size_t n_motor, const LIFConfig& config) noexcept;
    void reset() noexcept;

    // High-performance hot-path step: takes sensory spikes, runs RSNN, outputs motor spikes
    void step(const uint8_t* __restrict sensory_spikes_in,
              uint8_t* __restrict out_sensory_spikes,
              uint8_t* __restrict out_hidden_spikes,
              uint8_t* __restrict out_motor_spikes) noexcept;
};

} // namespace neuroquant

// Clean C ABI for Zero-Overhead Python ctypes / CFFI Interoperability
extern "C" {
    LIF_API void* lif_create(size_t num_neurons,
                            float dt, float tau_m,
                            float v_rest, float v_reset,
                            float v_thresh, float refractory_ms);
    LIF_API void lif_reset(void* handle);
    LIF_API void lif_destroy(void* handle);

    LIF_API void lif_step(void* handle,
                          const float* synaptic_current,
                          uint8_t* out_spikes);

    LIF_API void lif_get_state(void* handle,
                               float* out_voltage,
                               int32_t* out_refr,
                               uint64_t* out_counts);

    LIF_API void lif_set_state(void* handle,
                               const float* voltage,
                               const float* threshold,
                               const int32_t* refr);

    // Full RSNN API
    LIF_API void* rsnn_create(size_t n_sensory, size_t n_hidden, size_t n_motor,
                              float dt, float tau_m,
                              float v_rest, float v_reset,
                              float v_thresh, float refractory_ms);
    LIF_API void rsnn_destroy(void* handle);
    LIF_API void rsnn_reset(void* handle);
    LIF_API void rsnn_set_weights(void* handle,
                                  const float* w_in,
                                  const float* w_rec,
                                  const float* w_out);
    LIF_API void rsnn_step(void* handle,
                           const uint8_t* sensory_spikes_in,
                           uint8_t* out_s_spikes,
                           uint8_t* out_h_spikes,
                           uint8_t* out_m_spikes);
    LIF_API void rsnn_get_motor_voltage(void* handle, float* out_v_motor);

    // Micro-benchmark harness callable from Python or C
    LIF_API void run_lif_benchmark(size_t num_neurons, size_t iterations, BenchmarkStats* stats);
    LIF_API void run_rsnn_benchmark(size_t iterations, BenchmarkStats* stats);
    LIF_API uint64_t get_hardware_cycles();
}
