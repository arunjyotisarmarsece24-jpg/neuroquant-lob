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

constexpr size_t AC_CACHE_LINE = 64;
constexpr size_t AC_MAX_INTERVALS = 512;

#pragma pack(push, 8)
struct ACSIMDParams {
    double initial_shares;
    double time_horizon_sec;
    int32_t num_intervals;
    double lambda;
    double sigma;
    double gamma;
    double eta;
    double alpha;
    double spread;
};

struct ACSIMDResult {
    double kappa;
    double half_life_sec;
    double expected_shortfall;
    double variance_shortfall;
    double utility;
    uint64_t execution_cycles;
    double execution_nanoseconds;
};
#pragma pack(pop)

extern "C" {

LIF_API int ac_simd_compute_schedule(
    const ACSIMDParams* params,
    double* out_holdings,     // buffer of size num_intervals + 1
    double* out_trades,       // buffer of size num_intervals
    double* out_trade_rates,  // buffer of size num_intervals
    ACSIMDResult* out_result
);

LIF_API int ac_simd_compute_square_root_impact(
    const float* trade_rates, // float32 array of trade rates v
    float* out_impacts,       // float32 array: eta * sign(v) * sqrt(|v|) via AVX2
    int count,
    float eta
);

LIF_API int ac_simd_benchmark(
    int iterations,
    double* out_p50_ns,
    double* out_p99_ns,
    double* out_throughput_per_sec
);

}
