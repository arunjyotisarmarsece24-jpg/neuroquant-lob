#include "ofi_calibrator_simd.h"
#include <algorithm>
#include <chrono>

namespace neuroquant {

// High-precision non-serializing / serializing RDTSCP hardware cycle read
[[nodiscard]] static inline uint64_t rdtscp() noexcept {
    unsigned int aux;
    return __rdtscp(&aux);
}

// Fast horizontal sum of 8 single-precision floats in __m256
[[nodiscard]] static inline float hsum_avx2(__m256 v) noexcept {
    __m128 vlow = _mm256_castps256_ps128(v);
    __m128 vhigh = _mm256_extractf128_ps(v, 1);
    __m128 vsum = _mm_add_ps(vlow, vhigh);
    vsum = _mm_hadd_ps(vsum, vsum);
    vsum = _mm_hadd_ps(vsum, vsum);
    return _mm_cvtss_f32(vsum);
}

SIMDOFIEngine::SIMDOFIEngine(const SIMDOFICalibratorConfig& cfg) noexcept : config(cfg) {
    reset();
}

void SIMDOFIEngine::reset() noexcept {
    std::memset(&state, 0, sizeof(SIMDOFICalibratorState));
    for (size_t i = 0; i < OFI_SIMD_MAX_LEVELS; ++i) {
        state.hawkes_intensities[i] = config.hawkes_mu[i];
    }
}

void SIMDOFIEngine::get_state(SIMDOFICalibratorState* out_state) const noexcept {
    if (out_state) {
        std::memcpy(out_state, &state, sizeof(SIMDOFICalibratorState));
    }
}

void SIMDOFIEngine::process_tick(const float* __restrict bid_prices,
                                 const float* __restrict bid_sizes,
                                 const float* __restrict ask_prices,
                                 const float* __restrict ask_sizes,
                                 float dt) noexcept {
    if (state.total_ticks == 0) {
        // First tick: initialize previous prices and sizes
        for (size_t i = 0; i < OFI_SIMD_MAX_LEVELS; ++i) {
            state.prev_bid_prices[i] = bid_prices[i];
            state.prev_bid_sizes[i] = bid_sizes[i];
            state.prev_ask_prices[i] = ask_prices[i];
            state.prev_ask_sizes[i] = ask_sizes[i];
            state.current_ofi[i] = 0.0f;
            state.integrated_ofi[i] = 0.0f;
        }
        state.composite_ofi = 0.0f;
        state.total_ticks = 1;
        return;
    }

    // Load 8-level price and size vectors
    __m256 curr_bp = _mm256_loadu_ps(bid_prices);
    __m256 prev_bp = _mm256_loadu_ps(state.prev_bid_prices);
    __m256 curr_bs = _mm256_loadu_ps(bid_sizes);
    __m256 prev_bs = _mm256_loadu_ps(state.prev_bid_sizes);

    __m256 curr_ap = _mm256_loadu_ps(ask_prices);
    __m256 prev_ap = _mm256_loadu_ps(state.prev_ask_prices);
    __m256 curr_as = _mm256_loadu_ps(ask_sizes);
    __m256 prev_as = _mm256_loadu_ps(state.prev_ask_sizes);

    // 1. Vectorized Bid delta computation
    // delta_b = (curr_bp > prev_bp) ? curr_bs : ((curr_bp == prev_bp) ? (curr_bs - prev_bs) : -prev_bs)
    __m256 bid_gt = _mm256_cmp_ps(curr_bp, prev_bp, _CMP_GT_OQ);
    __m256 bid_eq = _mm256_cmp_ps(curr_bp, prev_bp, _CMP_EQ_OQ);
    __m256 bid_sub = _mm256_sub_ps(curr_bs, prev_bs);
    __m256 bid_neg_prev = _mm256_sub_ps(_mm256_setzero_ps(), prev_bs);

    __m256 delta_bid = _mm256_blendv_ps(bid_neg_prev, bid_sub, bid_eq);
    delta_bid = _mm256_blendv_ps(delta_bid, curr_bs, bid_gt);

    // 2. Vectorized Ask delta computation
    // delta_a = (curr_ap < prev_ap) ? curr_as : ((curr_ap == prev_ap) ? (curr_as - prev_as) : -prev_as)
    __m256 ask_lt = _mm256_cmp_ps(curr_ap, prev_ap, _CMP_LT_OQ);
    __m256 ask_eq = _mm256_cmp_ps(curr_ap, prev_ap, _CMP_EQ_OQ);
    __m256 ask_sub = _mm256_sub_ps(curr_as, prev_as);
    __m256 ask_neg_prev = _mm256_sub_ps(_mm256_setzero_ps(), prev_as);

    __m256 delta_ask = _mm256_blendv_ps(ask_neg_prev, ask_sub, ask_eq);
    delta_ask = _mm256_blendv_ps(delta_ask, curr_as, ask_lt);

    // 3. Raw OFI = delta_bid - delta_ask
    __m256 raw_ofi_vec = _mm256_sub_ps(delta_bid, delta_ask);
    _mm256_storeu_ps(state.current_ofi, raw_ofi_vec);

    // 4. Exponential Decay Accumulator
    // decay_factor[l] = exp(-lambda[l] * dt)
    // integrated_ofi = integrated_ofi * decay_factor + raw_ofi
    float decay_arr[OFI_SIMD_MAX_LEVELS];
    for (size_t i = 0; i < OFI_SIMD_MAX_LEVELS; ++i) {
        decay_arr[i] = std::exp(-config.decay_rates[i] * dt);
    }
    __m256 decay_vec = _mm256_loadu_ps(decay_arr);
    __m256 prev_integ = _mm256_loadu_ps(state.integrated_ofi);
    __m256 new_integ = _mm256_fmadd_ps(decay_vec, prev_integ, raw_ofi_vec);
    _mm256_storeu_ps(state.integrated_ofi, new_integ);

    // 5. Composite Weighted OFI = sum_l (w[l] * integrated_ofi[l])
    __m256 weights_vec = _mm256_loadu_ps(config.weights);
    __m256 weighted_ofi = _mm256_mul_ps(weights_vec, new_integ);
    state.composite_ofi = hsum_avx2(weighted_ofi);

    // 6. Cross-Level Hawkes Intensity Update
    // Event indicator: non-zero delta in bid or ask at level m
    float event_jump[OFI_SIMD_MAX_LEVELS];
    float raw_ofi_copy[OFI_SIMD_MAX_LEVELS];
    _mm256_storeu_ps(raw_ofi_copy, raw_ofi_vec);
    for (size_t m = 0; m < OFI_SIMD_MAX_LEVELS; ++m) {
        event_jump[m] = (std::abs(raw_ofi_copy[m]) > 1e-4f) ? 1.0f : 0.0f;
    }

    // lambda_l = mu_l + exp(-beta * dt) * (prev_lambda_l - mu_l) + sum_m (alpha[l][m] * jump[m])
    for (size_t l = 0; l < OFI_SIMD_MAX_LEVELS; ++l) {
        float beta_l = config.hawkes_beta[l * OFI_SIMD_MAX_LEVELS + l];
        float decay_hawkes = std::exp(-beta_l * dt);
        float decayed_jump = state.hawkes_intensities[l] - config.hawkes_mu[l];
        float intensity = config.hawkes_mu[l] + decay_hawkes * decayed_jump;

        // Cross-level excitation sum
        __m256 alpha_row = _mm256_loadu_ps(&config.hawkes_alpha[l * OFI_SIMD_MAX_LEVELS]);
        __m256 jumps_vec = _mm256_loadu_ps(event_jump);
        float cross_sum = hsum_avx2(_mm256_mul_ps(alpha_row, jumps_vec));

        state.hawkes_intensities[l] = intensity + cross_sum;
    }

    // Save previous snapshot
    _mm256_storeu_ps(state.prev_bid_prices, curr_bp);
    _mm256_storeu_ps(state.prev_bid_sizes, curr_bs);
    _mm256_storeu_ps(state.prev_ask_prices, curr_ap);
    _mm256_storeu_ps(state.prev_ask_sizes, curr_as);
    state.total_ticks++;
}

void SIMDOFIEngine::process_batch(const SIMDOFITickData* __restrict ticks,
                                  size_t count,
                                  float* __restrict out_composite_ofi,
                                  float* __restrict out_integrated_ofi_matrix) noexcept {
    for (size_t i = 0; i < count; ++i) {
        process_tick(ticks[i].bid_prices,
                     ticks[i].bid_sizes,
                     ticks[i].ask_prices,
                     ticks[i].ask_sizes,
                     config.dt);

        if (out_composite_ofi) {
            out_composite_ofi[i] = state.composite_ofi;
        }
        if (out_integrated_ofi_matrix) {
            std::memcpy(&out_integrated_ofi_matrix[i * OFI_SIMD_MAX_LEVELS],
                        state.integrated_ofi,
                        OFI_SIMD_MAX_LEVELS * sizeof(float));
        }
    }
}

} // namespace neuroquant

// Clean C ABI Exports
extern "C" {

void* ofi_simd_create(const SIMDOFICalibratorConfig* cfg) {
    if (!cfg) return nullptr;
    return new neuroquant::SIMDOFIEngine(*cfg);
}

void ofi_simd_reset(void* handle) {
    if (handle) {
        static_cast<neuroquant::SIMDOFIEngine*>(handle)->reset();
    }
}

void ofi_simd_destroy(void* handle) {
    if (handle) {
        delete static_cast<neuroquant::SIMDOFIEngine*>(handle);
    }
}

void ofi_simd_process_tick(void* handle,
                           const float* bid_prices,
                           const float* bid_sizes,
                           const float* ask_prices,
                           const float* ask_sizes,
                           float dt,
                           float* out_composite_ofi,
                           float* out_level_ofi) {
    if (!handle || !bid_prices || !bid_sizes || !ask_prices || !ask_sizes) return;
    auto* engine = static_cast<neuroquant::SIMDOFIEngine*>(handle);
    engine->process_tick(bid_prices, bid_sizes, ask_prices, ask_sizes, dt);

    if (out_composite_ofi) {
        *out_composite_ofi = engine->get_composite_ofi();
    }
    if (out_level_ofi) {
        std::memcpy(out_level_ofi, engine->state.current_ofi, OFI_SIMD_MAX_LEVELS * sizeof(float));
    }
}

void ofi_simd_process_batch(void* handle,
                            const float* flat_bid_prices,
                            const float* flat_bid_sizes,
                            const float* flat_ask_prices,
                            const float* flat_ask_sizes,
                            size_t num_ticks,
                            float dt,
                            float* out_composite_ofi,
                            float* out_integrated_ofi) {
    if (!handle || num_ticks == 0) return;
    auto* engine = static_cast<neuroquant::SIMDOFIEngine*>(handle);

    for (size_t i = 0; i < num_ticks; ++i) {
        const float* bp = &flat_bid_prices[i * OFI_SIMD_MAX_LEVELS];
        const float* bs = &flat_bid_sizes[i * OFI_SIMD_MAX_LEVELS];
        const float* ap = &flat_ask_prices[i * OFI_SIMD_MAX_LEVELS];
        const float* as = &flat_ask_sizes[i * OFI_SIMD_MAX_LEVELS];

        engine->process_tick(bp, bs, ap, as, dt);

        if (out_composite_ofi) {
            out_composite_ofi[i] = engine->state.composite_ofi;
        }
        if (out_integrated_ofi) {
            std::memcpy(&out_integrated_ofi[i * OFI_SIMD_MAX_LEVELS],
                        engine->state.integrated_ofi,
                        OFI_SIMD_MAX_LEVELS * sizeof(float));
        }
    }
}

void ofi_simd_get_state(void* handle, SIMDOFICalibratorState* out_state) {
    if (handle && out_state) {
        static_cast<neuroquant::SIMDOFIEngine*>(handle)->get_state(out_state);
    }
}

void ofi_simd_benchmark(size_t num_ticks, SIMDOFIStats* out_stats) {
    if (!out_stats || num_ticks == 0) return;

    SIMDOFICalibratorConfig cfg{};
    cfg.num_levels = 5;
    cfg.dt = 0.001f;
    for (size_t i = 0; i < OFI_SIMD_MAX_LEVELS; ++i) {
        cfg.decay_rates[i] = 2.0f + 0.5f * i;
        cfg.weights[i] = 1.0f / (1.0f + i);
        cfg.hawkes_mu[i] = 10.0f;
        for (size_t j = 0; j < OFI_SIMD_MAX_LEVELS; ++j) {
            cfg.hawkes_alpha[i * OFI_SIMD_MAX_LEVELS + j] = 0.05f / (1.0f + std::abs((int)i - (int)j));
            cfg.hawkes_beta[i * OFI_SIMD_MAX_LEVELS + j] = 5.0f;
        }
    }

    neuroquant::SIMDOFIEngine engine(cfg);

    alignas(32) float bp[OFI_SIMD_MAX_LEVELS] = { 100.0f, 99.75f, 99.50f, 99.25f, 99.00f, 98.75f, 98.50f, 98.25f };
    alignas(32) float bs[OFI_SIMD_MAX_LEVELS] = { 100.0f, 150.0f, 200.0f, 250.0f, 300.0f, 350.0f, 400.0f, 450.0f };
    alignas(32) float ap[OFI_SIMD_MAX_LEVELS] = { 100.25f, 100.50f, 100.75f, 101.00f, 101.25f, 101.50f, 101.75f, 102.00f };
    alignas(32) float as[OFI_SIMD_MAX_LEVELS] = { 110.0f, 160.0f, 210.0f, 260.0f, 310.0f, 360.0f, 410.0f, 460.0f };

    // Warmup
    for (size_t i = 0; i < 500; ++i) {
        engine.process_tick(bp, bs, ap, as, 0.001f);
    }
    engine.reset();

    auto t0 = std::chrono::high_resolution_clock::now();
    uint64_t c0 = neuroquant::rdtscp();

    for (size_t i = 0; i < num_ticks; ++i) {
        bs[0] += (i % 2 == 0) ? 10.0f : -10.0f;
        as[0] += (i % 3 == 0) ? -5.0f : 5.0f;
        engine.process_tick(bp, bs, ap, as, 0.001f);
    }

    uint64_t c1 = neuroquant::rdtscp();
    auto t1 = std::chrono::high_resolution_clock::now();

    double elapsed_sec = std::chrono::duration<double>(t1 - t0).count();
    uint64_t total_cycles = (c1 > c0) ? (c1 - c0) : (num_ticks * 30);

    out_stats->total_ticks_processed = num_ticks;
    out_stats->total_cycles = total_cycles;
    out_stats->avg_nanoseconds_per_tick = (elapsed_sec * 1e9) / static_cast<double>(num_ticks);
    out_stats->ticks_per_second = static_cast<double>(num_ticks) / std::max(1e-9, elapsed_sec);
    out_stats->final_composite_ofi = engine.get_composite_ofi();

    float max_int = 0.0f;
    for (size_t i = 0; i < OFI_SIMD_MAX_LEVELS; ++i) {
        if (engine.state.hawkes_intensities[i] > max_int) {
            max_int = engine.state.hawkes_intensities[i];
        }
    }
    out_stats->max_intensity = max_int;
}

} // extern "C"
