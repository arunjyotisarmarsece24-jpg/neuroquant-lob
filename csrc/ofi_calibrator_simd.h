#pragma once

#include <cstdint>
#include <cstddef>
#include <cmath>
#include <cstring>
#include <immintrin.h>
#include <x86intrin.h>

#if defined(_WIN32) || defined(__CYGWIN__)
  #ifdef LIF_EXPORTS
    #define OFI_API __declspec(dllexport)
  #else
    #define OFI_API __declspec(dllimport)
  #endif
#else
  #define OFI_API __attribute__((visibility("default")))
#endif

constexpr size_t OFI_SIMD_MAX_LEVELS = 8; // 8 x float32 fits exactly in 256-bit AVX2 register

#pragma pack(push, 8)
struct SIMDOFICalibratorConfig {
    size_t num_levels;                              // Active levels (e.g., 5 or 8)
    float decay_rates[OFI_SIMD_MAX_LEVELS];         // lambda_l per depth level
    float weights[OFI_SIMD_MAX_LEVELS];             // w_l per depth level
    float hawkes_mu[OFI_SIMD_MAX_LEVELS];           // Baseline arrival intensity
    float hawkes_alpha[OFI_SIMD_MAX_LEVELS * OFI_SIMD_MAX_LEVELS]; // Cross-excitation matrix (L x L)
    float hawkes_beta[OFI_SIMD_MAX_LEVELS * OFI_SIMD_MAX_LEVELS];  // Decay rates matrix (L x L)
    float dt;                                       // Discrete step dt (seconds)
};

struct SIMDOFICalibratorState {
    float prev_bid_prices[OFI_SIMD_MAX_LEVELS];
    float prev_bid_sizes[OFI_SIMD_MAX_LEVELS];
    float prev_ask_prices[OFI_SIMD_MAX_LEVELS];
    float prev_ask_sizes[OFI_SIMD_MAX_LEVELS];
    float current_ofi[OFI_SIMD_MAX_LEVELS];         // Raw tick OFI per level
    float integrated_ofi[OFI_SIMD_MAX_LEVELS];      // Exponentially decayed cumulative OFI
    float composite_ofi;                            // w^T * integrated_ofi
    float hawkes_intensities[OFI_SIMD_MAX_LEVELS];  // lambda_l(t)
    uint64_t total_ticks;
};

struct SIMDOFITickData {
    float bid_prices[OFI_SIMD_MAX_LEVELS];
    float bid_sizes[OFI_SIMD_MAX_LEVELS];
    float ask_prices[OFI_SIMD_MAX_LEVELS];
    float ask_sizes[OFI_SIMD_MAX_LEVELS];
};

struct SIMDOFIStats {
    uint64_t total_ticks_processed;
    uint64_t total_cycles;
    double avg_nanoseconds_per_tick;
    double ticks_per_second;
    float final_composite_ofi;
    float max_intensity;
};
#pragma pack(pop)

namespace neuroquant {

class alignas(32) SIMDOFIEngine {
public:
    SIMDOFICalibratorConfig config;
    SIMDOFICalibratorState state;

    explicit SIMDOFIEngine(const SIMDOFICalibratorConfig& cfg) noexcept;
    void reset() noexcept;

    // Process a single tick with AVX2 SIMD vectorization
    void process_tick(const float* __restrict bid_prices,
                      const float* __restrict bid_sizes,
                      const float* __restrict ask_prices,
                      const float* __restrict ask_sizes,
                      float dt) noexcept;

    // Batch process N ticks
    void process_batch(const SIMDOFITickData* __restrict ticks,
                       size_t count,
                       float* __restrict out_composite_ofi,
                       float* __restrict out_integrated_ofi_matrix) noexcept;

    // Direct AVX2 kernel evaluation
    [[nodiscard]] float get_composite_ofi() const noexcept { return state.composite_ofi; }
    void get_state(SIMDOFICalibratorState* out_state) const noexcept;
};

} // namespace neuroquant

// Clean C ABI for Zero-Overhead Python ctypes / CFFI Interoperability
extern "C" {
    OFI_API void* ofi_simd_create(const SIMDOFICalibratorConfig* cfg);
    OFI_API void ofi_simd_reset(void* handle);
    OFI_API void ofi_simd_destroy(void* handle);

    OFI_API void ofi_simd_process_tick(void* handle,
                                       const float* bid_prices,
                                       const float* bid_sizes,
                                       const float* ask_prices,
                                       const float* ask_sizes,
                                       float dt,
                                       float* out_composite_ofi,
                                       float* out_level_ofi);

    OFI_API void ofi_simd_process_batch(void* handle,
                                        const float* flat_bid_prices,
                                        const float* flat_bid_sizes,
                                        const float* flat_ask_prices,
                                        const float* flat_ask_sizes,
                                        size_t num_ticks,
                                        float dt,
                                        float* out_composite_ofi,
                                        float* out_integrated_ofi);

    OFI_API void ofi_simd_get_state(void* handle, SIMDOFICalibratorState* out_state);
    OFI_API void ofi_simd_benchmark(size_t num_ticks, SIMDOFIStats* out_stats);
}
