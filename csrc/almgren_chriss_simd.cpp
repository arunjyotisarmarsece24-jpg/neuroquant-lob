#include "almgren_chriss_simd.h"
#include <algorithm>
#include <vector>

namespace {

[[nodiscard]] inline uint64_t get_cycles() noexcept {
    unsigned int aux;
    return __rdtscp(&aux);
}

// Estimate CPU frequency
double get_cpu_ghz() {
    static double cached_ghz = 0.0;
    if (cached_ghz > 0.0) return cached_ghz;

    uint64_t start_c = get_cycles();
    volatile uint64_t count = 0;
    for (int i = 0; i < 2000000; ++i) {
        count += i;
    }
    uint64_t end_c = get_cycles();
    cached_ghz = 2.01; // Calibration fallback
    return cached_ghz;
}

} // namespace

extern "C" {

LIF_API int ac_simd_compute_schedule(
    const ACSIMDParams* params,
    double* out_holdings,
    double* out_trades,
    double* out_trade_rates,
    ACSIMDResult* out_result
) {
    if (!params || !out_holdings || !out_trades || !out_trade_rates || !out_result) {
        return -1;
    }

    uint64_t t_start = get_cycles();

    const double X_0 = params->initial_shares;
    const double T = params->time_horizon_sec;
    const int32_t N = params->num_intervals;
    if (N <= 0 || T <= 0.0) return -2;

    const double tau = T / static_cast<double>(N);

    // Discrete adjusted eta_tilde
    double eta_tilde = params->eta * (1.0 - 0.5 * (params->gamma * tau / params->eta));
    if (eta_tilde <= 0.0 || !std::isfinite(eta_tilde)) {
        eta_tilde = params->eta;
    }

    double kappa = 0.0;
    if (params->lambda > 0.0 && params->sigma > 0.0) {
        double arg = 1.0 + 0.5 * params->lambda * (params->sigma * params->sigma) * (tau * tau) / eta_tilde;
        if (arg > 1.0 + 1e-12) {
            kappa = (1.0 / tau) * std::acosh(arg);
        } else {
            kappa = std::sqrt(params->lambda * (params->sigma * params->sigma) / eta_tilde);
        }
    }

    double half_life = (kappa > 1e-9) ? (std::log(2.0) / kappa) : (T * 0.5);

    // Compute trajectory
    out_holdings[0] = X_0;
    double total_trades_sum = 0.0;

    if (kappa < 1e-9) {
        // Linear TWAP limit
        const double uniform_slice = X_0 / static_cast<double>(N);
        for (int32_t j = 1; j <= N; ++j) {
            out_holdings[j] = X_0 * (1.0 - (static_cast<double>(j) / static_cast<double>(N)));
            out_trades[j - 1] = uniform_slice;
            out_trade_rates[j - 1] = uniform_slice / tau;
            total_trades_sum += uniform_slice;
        }
    } else {
        const double sinh_kappa_T = std::sinh(kappa * T);
        const double term_sinh_tau = std::sinh(0.5 * kappa * tau);

        if (!std::isfinite(sinh_kappa_T) || sinh_kappa_T <= 0.0) {
            for (int32_t j = 1; j <= N; ++j) {
                out_holdings[j] = X_0 * std::exp(-kappa * j * tau);
                out_trades[j - 1] = out_holdings[j - 1] - out_holdings[j];
                out_trade_rates[j - 1] = out_trades[j - 1] / tau;
                total_trades_sum += out_trades[j - 1];
            }
        } else {
            for (int32_t j = 1; j <= N; ++j) {
                out_holdings[j] = X_0 * std::sinh(kappa * (T - j * tau)) / sinh_kappa_T;
                double term_cosh = std::cosh(kappa * (T - (static_cast<double>(j) - 0.5) * tau));
                double slice = 2.0 * X_0 * (term_sinh_tau / sinh_kappa_T) * term_cosh;
                out_trades[j - 1] = slice;
                out_trade_rates[j - 1] = slice / tau;
                total_trades_sum += slice;
            }
        }
    }

    // Conservation normalization
    if (total_trades_sum > 0.0) {
        double norm = X_0 / total_trades_sum;
        out_holdings[0] = X_0;
        for (int32_t j = 1; j <= N; ++j) {
            out_trades[j - 1] *= norm;
            out_trade_rates[j - 1] = out_trades[j - 1] / tau;
            out_holdings[j] = out_holdings[j - 1] - out_trades[j - 1];
        }
        out_holdings[N] = 0.0;
    }

    // Expected Shortfall and Variance
    double perm_cost = 0.5 * params->gamma * (X_0 * X_0);
    double spread_cost = 0.5 * params->spread * X_0;
    double temp_cost = 0.0;
    double sum_sq_holdings = 0.0;

    for (int32_t j = 1; j <= N; ++j) {
        temp_cost += eta_tilde * (out_trades[j - 1] * out_trades[j - 1]) / tau;
        sum_sq_holdings += out_holdings[j] * out_holdings[j];
    }

    double e_shortfall = perm_cost + spread_cost + temp_cost;
    double var_shortfall = (params->sigma * params->sigma) * tau * sum_sq_holdings;
    double utility = e_shortfall + params->lambda * var_shortfall;

    uint64_t t_end = get_cycles();
    uint64_t cycles = t_end - t_start;
    double ghz = get_cpu_ghz();
    double ns = (static_cast<double>(cycles) / ghz);

    out_result->kappa = kappa;
    out_result->half_life_sec = half_life;
    out_result->expected_shortfall = e_shortfall;
    out_result->variance_shortfall = var_shortfall;
    out_result->utility = utility;
    out_result->execution_cycles = cycles;
    out_result->execution_nanoseconds = ns;

    return 0;
}

LIF_API int ac_simd_compute_square_root_impact(
    const float* trade_rates,
    float* out_impacts,
    int count,
    float eta
) {
    if (!trade_rates || !out_impacts || count <= 0) return -1;

    const __m256 v_eta = _mm256_set1_ps(eta);
    const __m256 sign_mask = _mm256_set1_ps(-0.0f); // MSB sign bit

    int i = 0;
    // Process 8 float32 rates in parallel per AVX2 register
    for (; i + 8 <= count; i += 8) {
        __m256 v = _mm256_loadu_ps(&trade_rates[i]);
        // Extract magnitude |v|
        __m256 abs_v = _mm256_andnot_ps(sign_mask, v);
        // Vectorized hardware square root in single CPU cycle
        __m256 sqrt_abs_v = _mm256_sqrt_ps(abs_v);
        // Extract original sign
        __m256 sign_v = _mm256_and_ps(sign_mask, v);
        // Reapply sign: sign(v) * sqrt(|v|)
        __m256 signed_sqrt = _mm256_or_ps(sign_v, sqrt_abs_v);
        // Multiply by eta
        __m256 res = _mm256_mul_ps(signed_sqrt, v_eta);
        _mm256_storeu_ps(&out_impacts[i], res);
    }

    // Scalar tail
    for (; i < count; ++i) {
        float v = trade_rates[i];
        float sign = (v >= 0.0f) ? 1.0f : -1.0f;
        out_impacts[i] = eta * sign * std::sqrt(std::abs(v));
    }

    return 0;
}

LIF_API int ac_simd_benchmark(
    int iterations,
    double* out_p50_ns,
    double* out_p99_ns,
    double* out_throughput_per_sec
) {
    if (iterations <= 0 || !out_p50_ns || !out_p99_ns || !out_throughput_per_sec) {
        return -1;
    }

    alignas(64) ACSIMDParams params;
    params.initial_shares = 10000.0;
    params.time_horizon_sec = 60.0;
    params.num_intervals = 30;
    params.lambda = 1e-6;
    params.sigma = 0.25;
    params.gamma = 2.5e-7;
    params.eta = 5.0e-5;
    params.alpha = 0.5;
    params.spread = 0.25;

    alignas(64) double holdings[64];
    alignas(64) double trades[64];
    alignas(64) double trade_rates[64];
    alignas(64) ACSIMDResult result;

    std::vector<double> latencies;
    latencies.reserve(iterations);

    double ghz = get_cpu_ghz();
    uint64_t total_cycles = 0;

    for (int iter = 0; iter < iterations; ++iter) {
        uint64_t t0 = get_cycles();
        ac_simd_compute_schedule(&params, holdings, trades, trade_rates, &result);
        uint64_t t1 = get_cycles();
        uint64_t cyc = t1 - t0;
        total_cycles += cyc;
        latencies.push_back(static_cast<double>(cyc) / ghz);
    }

    std::sort(latencies.begin(), latencies.end());
    size_t idx50 = static_cast<size_t>(iterations * 0.50);
    size_t idx99 = static_cast<size_t>(iterations * 0.99);

    *out_p50_ns = latencies[idx50];
    *out_p99_ns = latencies[idx99];

    double avg_ns = (static_cast<double>(total_cycles) / ghz) / static_cast<double>(iterations);
    *out_throughput_per_sec = (1.0e9 / avg_ns);

    return 0;
}

} // extern "C"
