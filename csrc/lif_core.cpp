#include "lif_core.h"
#include <vector>
#include <numeric>
#include <algorithm>
#include <chrono>
#include <random>
#include <memory>

namespace neuroquant {

void LIFPopulationSIMD::step_scalar(const float* __restrict synaptic_current, uint8_t* __restrict out_spikes) noexcept {
    total_steps++;
    const float decay = cfg.decay;
    const float c_rest = cfg.c_rest;
    const float v_reset = cfg.v_reset;
    const int32_t refr_steps = cfg.refractory_steps;

    for (size_t i = 0; i < size; ++i) {
        bool is_refr = refractory_timer[i] > 0;
        if (is_refr) {
            refractory_timer[i]--;
            voltage[i] = v_reset;
            spikes[i] = 0;
            if (out_spikes) out_spikes[i] = 0;
        } else {
            float v = voltage[i] * decay + c_rest + synaptic_current[i];
            if (v >= threshold[i]) {
                spikes[i] = 1;
                if (out_spikes) out_spikes[i] = 1;
                voltage[i] = v_reset;
                refractory_timer[i] = refr_steps;
                spike_counts[i]++;
            } else {
                spikes[i] = 0;
                if (out_spikes) out_spikes[i] = 0;
                voltage[i] = v;
            }
        }
    }
}

void LIFPopulationSIMD::step_vectorized(const float* __restrict synaptic_current, uint8_t* __restrict out_spikes) noexcept {
    total_steps++;
    size_t i = 0;

    const float decay = cfg.decay;
    const float c_rest = cfg.c_rest;
    const float v_reset = cfg.v_reset;
    const int32_t refr_steps = cfg.refractory_steps;

#if defined(__AVX512F__)
    const __m512 v_decay_512 = _mm512_set1_ps(decay);
    const __m512 v_crest_512 = _mm512_set1_ps(c_rest);
    const __m512 v_reset_512 = _mm512_set1_ps(v_reset);
    const __m512i v_zero_512i = _mm512_setzero_si512();
    const __m512i v_one_512i = _mm512_set1_epi32(1);
    const __m512i v_refr_steps_512i = _mm512_set1_epi32(refr_steps);

    for (; i + 16 <= size; i += 16) {
        __m512 v = _mm512_load_ps(&voltage[i]);
        __m512 thresh = _mm512_load_ps(&threshold[i]);
        __m512 isyn = _mm512_load_ps(&synaptic_current[i]);
        __m512i refr = _mm512_load_si512(reinterpret_cast<const void*>(&refractory_timer[i]));

        __mmask16 refr_mask = _mm512_cmpgt_epi32_mask(refr, v_zero_512i);
        __m512i refr_dec = _mm512_mask_sub_epi32(refr, refr_mask, refr, v_one_512i);

        __m512 v_int = _mm512_fmadd_ps(v, v_decay_512, _mm512_add_ps(v_crest_512, isyn));
        __m512 v_sub = _mm512_mask_blend_ps(refr_mask, v_int, v_reset_512);

        __mmask16 fire_mask = _mm512_cmp_ps_mask(v_sub, thresh, _CMP_GE_OQ);
        __mmask16 spike_mask = fire_mask & (~refr_mask);

        __m512 v_final = _mm512_mask_blend_ps(spike_mask, v_sub, v_reset_512);
        _mm512_store_ps(&voltage[i], v_final);

        __m512i refr_final = _mm512_mask_blend_epi32(spike_mask, refr_dec, v_refr_steps_512i);
        _mm512_store_si512(reinterpret_cast<void*>(&refractory_timer[i]), refr_final);

        for (size_t k = 0; k < 16; ++k) {
            uint8_t sp = (spike_mask >> k) & 1;
            spikes[i + k] = sp;
            if (out_spikes) out_spikes[i + k] = sp;
            spike_counts[i + k] += sp;
        }
    }
#elif defined(__AVX2__)
    const __m256 v_decay_256 = _mm256_set1_ps(decay);
    const __m256 v_crest_256 = _mm256_set1_ps(c_rest);
    const __m256 v_reset_256 = _mm256_set1_ps(v_reset);
    const __m256i v_zero_256i = _mm256_setzero_si256();
    const __m256i v_one_256i = _mm256_set1_epi32(1);
    const __m256i v_refr_steps_256i = _mm256_set1_epi32(refr_steps);

    for (; i + 8 <= size; i += 8) {
        __m256 v = _mm256_load_ps(&voltage[i]);
        __m256 thresh = _mm256_load_ps(&threshold[i]);
        __m256 isyn = _mm256_load_ps(&synaptic_current[i]);
        __m256i refr = _mm256_load_si256(reinterpret_cast<const __m256i*>(&refractory_timer[i]));

        // Mask of refractory neurons: refr > 0
        __m256i refr_mask_i = _mm256_cmpgt_epi32(refr, v_zero_256i);
        __m256 refr_mask_ps = _mm256_castsi256_ps(refr_mask_i);

        // Decrement refractory timer: refr[refr > 0] -= 1
        __m256i refr_dec = _mm256_sub_epi32(refr, v_one_256i);
        refr = _mm256_blendv_epi8(refr, refr_dec, refr_mask_i);

        // Sub-threshold integration: v * decay + (c_rest + isyn)
        __m256 v_int = _mm256_fmadd_ps(v, v_decay_256, _mm256_add_ps(v_crest_256, isyn));

        // Refractory neurons clamped to v_reset
        __m256 v_sub = _mm256_blendv_ps(v_int, v_reset_256, refr_mask_ps);

        // Detect action potential: v_sub >= thresh and not refractory
        __m256 fire_cmp = _mm256_cmp_ps(v_sub, thresh, _CMP_GE_OQ);
        __m256 spike_mask_ps = _mm256_andnot_ps(refr_mask_ps, fire_cmp);

        // Post-spike reset
        __m256 v_final = _mm256_blendv_ps(v_sub, v_reset_256, spike_mask_ps);
        _mm256_store_ps(&voltage[i], v_final);

        // Set refractory timers for spiked neurons
        __m256i spike_mask_i = _mm256_castps_si256(spike_mask_ps);
        __m256i refr_final = _mm256_blendv_epi8(refr, v_refr_steps_256i, spike_mask_i);
        _mm256_store_si256(reinterpret_cast<__m256i*>(&refractory_timer[i]), refr_final);

        // Extract spike bitmask
        int mask = _mm256_movemask_ps(spike_mask_ps);
        for (int k = 0; k < 8; ++k) {
            uint8_t sp = static_cast<uint8_t>((mask >> k) & 1);
            spikes[i + k] = sp;
            if (out_spikes) out_spikes[i + k] = sp;
            spike_counts[i + k] += sp;
        }
    }
#endif

    // Remainder loop for tail elements (< 8 or scalar)
    for (; i < size; ++i) {
        bool is_refr = refractory_timer[i] > 0;
        if (is_refr) {
            refractory_timer[i]--;
            voltage[i] = v_reset;
            spikes[i] = 0;
            if (out_spikes) out_spikes[i] = 0;
        } else {
            float v = voltage[i] * decay + c_rest + synaptic_current[i];
            if (v >= threshold[i]) {
                spikes[i] = 1;
                if (out_spikes) out_spikes[i] = 1;
                voltage[i] = v_reset;
                refractory_timer[i] = refr_steps;
                spike_counts[i]++;
            } else {
                spikes[i] = 0;
                if (out_spikes) out_spikes[i] = 0;
                voltage[i] = v;
            }
        }
    }
}

void RSNNCoreSIMD::init(size_t n_sensory, size_t n_hidden, size_t n_motor, const LIFConfig& config) noexcept {
    num_sensory = std::min(n_sensory, MAX_NEURONS_PER_POP);
    num_hidden = std::min(n_hidden, MAX_NEURONS_PER_POP);
    num_motor = std::min(n_motor, MAX_NEURONS_PER_POP);

    sensory_pop.init(num_sensory, config);
    hidden_pop.init(num_hidden, config);
    motor_pop.init(num_motor, config);

    std::memset(w_in_hidden, 0, sizeof(w_in_hidden));
    std::memset(w_hidden_hidden, 0, sizeof(w_hidden_hidden));
    std::memset(w_motor, 0, sizeof(w_motor));

    std::memset(current_sensory, 0, sizeof(current_sensory));
    std::memset(current_hidden, 0, sizeof(current_hidden));
    std::memset(current_motor, 0, sizeof(current_motor));
}

void RSNNCoreSIMD::reset() noexcept {
    sensory_pop.reset();
    hidden_pop.reset();
    motor_pop.reset();
    std::memset(current_sensory, 0, sizeof(current_sensory));
    std::memset(current_hidden, 0, sizeof(current_hidden));
    std::memset(current_motor, 0, sizeof(current_motor));
}

void RSNNCoreSIMD::step(const uint8_t* __restrict sensory_spikes_in,
                        uint8_t* __restrict out_sensory_spikes,
                        uint8_t* __restrict out_hidden_spikes,
                        uint8_t* __restrict out_motor_spikes) noexcept {
    // 1. Sensory Input Passthrough
    if (out_sensory_spikes) {
        std::memcpy(out_sensory_spikes, sensory_spikes_in, num_sensory * sizeof(uint8_t));
    }

    // 2. Hidden Layer Synaptic Current Accumulation
    // I_hidden = 12.0f * (S_sensory @ W_in) + 8.0f * (S_hidden_prev @ W_rec)
    // Clear accumulation buffer with AVX2 zeroing
    size_t h_vec_end = (num_hidden / 8) * 8;
    for (size_t j = 0; j < h_vec_end; j += 8) {
        _mm256_store_ps(&current_hidden[j], _mm256_setzero_ps());
    }
    for (size_t j = h_vec_end; j < num_hidden; ++j) {
        current_hidden[j] = 0.0f;
    }

    // Sparse feedforward accumulation from incoming sensory spikes (scale = 12.0f)
    const float scale_in = 12.0f;
    const __m256 v_scale_in = _mm256_set1_ps(scale_in);

    for (size_t s = 0; s < num_sensory; ++s) {
        if (sensory_spikes_in[s]) {
            const float* __restrict w_row = &w_in_hidden[s * num_hidden];
            size_t j = 0;
            for (; j + 8 <= num_hidden; j += 8) {
                __m256 cur = _mm256_load_ps(&current_hidden[j]);
                __m256 w = _mm256_loadu_ps(&w_row[j]);
                cur = _mm256_fmadd_ps(w, v_scale_in, cur);
                _mm256_store_ps(&current_hidden[j], cur);
            }
            for (; j < num_hidden; ++j) {
                current_hidden[j] += w_row[j] * scale_in;
            }
        }
    }

    // Sparse recurrent accumulation from hidden spikes (scale = 8.0f)
    const float scale_rec = 8.0f;
    const __m256 v_scale_rec = _mm256_set1_ps(scale_rec);

    for (size_t h = 0; h < num_hidden; ++h) {
        if (hidden_pop.spikes[h]) {
            const float* __restrict w_row = &w_hidden_hidden[h * num_hidden];
            size_t j = 0;
            for (; j + 8 <= num_hidden; j += 8) {
                __m256 cur = _mm256_load_ps(&current_hidden[j]);
                __m256 w = _mm256_loadu_ps(&w_row[j]);
                cur = _mm256_fmadd_ps(w, v_scale_rec, cur);
                _mm256_store_ps(&current_hidden[j], cur);
            }
            for (; j < num_hidden; ++j) {
                current_hidden[j] += w_row[j] * scale_rec;
            }
        }
    }

    hidden_pop.step_vectorized(current_hidden, out_hidden_spikes);

    // 3. Motor Layer Accumulation (scale = 15.0f)
    for (size_t m = 0; m < num_motor; ++m) {
        current_motor[m] = 0.0f;
    }
    const float scale_motor = 15.0f;
    for (size_t h = 0; h < num_hidden; ++h) {
        if (hidden_pop.spikes[h]) {
            const float* __restrict w_row = &w_motor[h * num_motor];
            for (size_t m = 0; m < num_motor; ++m) {
                current_motor[m] += w_row[m] * scale_motor;
            }
        }
    }

    motor_pop.step_vectorized(current_motor, out_motor_spikes);
}

} // namespace neuroquant

// C ABI Bindings
extern "C" {

LIF_API void* lif_create(size_t num_neurons,
                         float dt, float tau_m,
                         float v_rest, float v_reset,
                         float v_thresh, float refractory_ms) {
    auto* pop = new neuroquant::LIFPopulationSIMD();
    neuroquant::LIFConfig cfg;
    cfg.dt = dt;
    cfg.tau_m = tau_m;
    cfg.v_rest = v_rest;
    cfg.v_reset = v_reset;
    cfg.v_thresh = v_thresh;
    cfg.refractory_period_ms = refractory_ms;
    pop->init(num_neurons, cfg);
    return pop;
}

LIF_API void lif_reset(void* handle) {
    if (handle) {
        static_cast<neuroquant::LIFPopulationSIMD*>(handle)->reset();
    }
}

LIF_API void lif_destroy(void* handle) {
    if (handle) {
        delete static_cast<neuroquant::LIFPopulationSIMD*>(handle);
    }
}

LIF_API void lif_step(void* handle,
                      const float* synaptic_current,
                      uint8_t* out_spikes) {
    if (handle) {
        static_cast<neuroquant::LIFPopulationSIMD*>(handle)->step_vectorized(synaptic_current, out_spikes);
    }
}

LIF_API void lif_get_state(void* handle,
                           float* out_voltage,
                           int32_t* out_refr,
                           uint64_t* out_counts) {
    if (!handle) return;
    auto* pop = static_cast<neuroquant::LIFPopulationSIMD*>(handle);
    if (out_voltage) {
        std::memcpy(out_voltage, pop->voltage, pop->size * sizeof(float));
    }
    if (out_refr) {
        std::memcpy(out_refr, pop->refractory_timer, pop->size * sizeof(int32_t));
    }
    if (out_counts) {
        std::memcpy(out_counts, pop->spike_counts, pop->size * sizeof(uint64_t));
    }
}

LIF_API void lif_set_state(void* handle,
                           const float* voltage,
                           const float* threshold,
                           const int32_t* refr) {
    if (!handle) return;
    auto* pop = static_cast<neuroquant::LIFPopulationSIMD*>(handle);
    if (voltage) {
        std::memcpy(pop->voltage, voltage, pop->size * sizeof(float));
    }
    if (threshold) {
        std::memcpy(pop->threshold, threshold, pop->size * sizeof(float));
    }
    if (refr) {
        std::memcpy(pop->refractory_timer, refr, pop->size * sizeof(int32_t));
    }
}

LIF_API void* rsnn_create(size_t n_sensory, size_t n_hidden, size_t n_motor,
                          float dt, float tau_m,
                          float v_rest, float v_reset,
                          float v_thresh, float refractory_ms) {
    auto* rsnn = new neuroquant::RSNNCoreSIMD();
    neuroquant::LIFConfig cfg;
    cfg.dt = dt;
    cfg.tau_m = tau_m;
    cfg.v_rest = v_rest;
    cfg.v_reset = v_reset;
    cfg.v_thresh = v_thresh;
    cfg.refractory_period_ms = refractory_ms;
    rsnn->init(n_sensory, n_hidden, n_motor, cfg);
    return rsnn;
}

LIF_API void rsnn_destroy(void* handle) {
    if (handle) {
        delete static_cast<neuroquant::RSNNCoreSIMD*>(handle);
    }
}

LIF_API void rsnn_reset(void* handle) {
    if (handle) {
        static_cast<neuroquant::RSNNCoreSIMD*>(handle)->reset();
    }
}

LIF_API void rsnn_set_weights(void* handle,
                              const float* w_in,
                              const float* w_rec,
                              const float* w_out) {
    if (!handle) return;
    auto* rsnn = static_cast<neuroquant::RSNNCoreSIMD*>(handle);
    if (w_in) {
        std::memcpy(rsnn->w_in_hidden, w_in, rsnn->num_sensory * rsnn->num_hidden * sizeof(float));
    }
    if (w_rec) {
        std::memcpy(rsnn->w_hidden_hidden, w_rec, rsnn->num_hidden * rsnn->num_hidden * sizeof(float));
    }
    if (w_out) {
        std::memcpy(rsnn->w_motor, w_out, rsnn->num_hidden * rsnn->num_motor * sizeof(float));
    }
}

LIF_API void rsnn_step(void* handle,
                       const uint8_t* sensory_spikes_in,
                       uint8_t* out_s_spikes,
                       uint8_t* out_h_spikes,
                       uint8_t* out_m_spikes) {
    if (handle) {
        static_cast<neuroquant::RSNNCoreSIMD*>(handle)->step(
            sensory_spikes_in, out_s_spikes, out_h_spikes, out_m_spikes
        );
    }
}

LIF_API void rsnn_get_motor_voltage(void* handle, float* out_v_motor) {
    if (!handle || !out_v_motor) return;
    auto* rsnn = static_cast<neuroquant::RSNNCoreSIMD*>(handle);
    std::memcpy(out_v_motor, rsnn->motor_pop.voltage, rsnn->num_motor * sizeof(float));
}

LIF_API uint64_t get_hardware_cycles() {
    return neuroquant::rdtscp();
}

LIF_API void run_lif_benchmark(size_t num_neurons, size_t iterations, BenchmarkStats* stats) {
    if (!stats || iterations == 0) return;

    auto pop_ptr = std::make_unique<neuroquant::LIFPopulationSIMD>();
    auto& pop = *pop_ptr;
    neuroquant::LIFConfig cfg{0.5f, 20.0f, -70.0f, -75.0f, -55.0f, 2.0f, 4, 0.0f, 0.0f};
    pop.init(num_neurons, cfg);

    alignas(64) float input_current[MAX_NEURONS_PER_POP];
    alignas(64) uint8_t out_spikes[MAX_NEURONS_PER_POP];

    std::mt19937 rng(42);
    std::uniform_real_distribution<float> dist(0.0f, 35.0f);
    for (size_t i = 0; i < num_neurons; ++i) {
        input_current[i] = dist(rng);
    }

    // Warm-up cache lines
    for (size_t w = 0; w < 1000; ++w) {
        pop.step_vectorized(input_current, out_spikes);
    }

    std::vector<uint64_t> cycles_list;
    cycles_list.reserve(iterations);

    auto t_start = std::chrono::high_resolution_clock::now();
    uint64_t total_cycles = 0;

    for (size_t it = 0; it < iterations; ++it) {
        uint64_t c0 = neuroquant::rdtscp();
        pop.step_vectorized(input_current, out_spikes);
        uint64_t c1 = neuroquant::rdtscp();
        uint64_t diff = (c1 > c0) ? (c1 - c0) : 0;
        cycles_list.push_back(diff);
        total_cycles += diff;
    }

    auto t_end = std::chrono::high_resolution_clock::now();
    double total_ns = std::chrono::duration<double, std::nano>(t_end - t_start).count();

    std::sort(cycles_list.begin(), cycles_list.end());

    stats->total_steps = iterations;
    stats->total_cycles = total_cycles;
    stats->min_cycles = cycles_list.front();
    stats->max_cycles = cycles_list.back();
    stats->p50_cycles = static_cast<double>(cycles_list[iterations * 50 / 100]);
    stats->p90_cycles = static_cast<double>(cycles_list[iterations * 90 / 100]);
    stats->p99_cycles = static_cast<double>(cycles_list[iterations * 99 / 100]);
    stats->p999_cycles = static_cast<double>(cycles_list[iterations * 999 / 1000]);
    stats->avg_nanoseconds = total_ns / static_cast<double>(iterations);
    stats->steps_per_second = (iterations / total_ns) * 1e9;
}

LIF_API void run_rsnn_benchmark(size_t iterations, BenchmarkStats* stats) {
    if (!stats || iterations == 0) return;

    auto rsnn_ptr = std::make_unique<neuroquant::RSNNCoreSIMD>();
    auto& rsnn = *rsnn_ptr;
    neuroquant::LIFConfig cfg{0.5f, 20.0f, -70.0f, -75.0f, -55.0f, 2.0f, 4, 0.0f, 0.0f};
    rsnn.init(32, 64, 4, cfg);

    std::mt19937 rng(1337);
    std::uniform_real_distribution<float> w_dist(-0.2f, 0.3f);
    for (size_t i = 0; i < 32 * 64; ++i) rsnn.w_in_hidden[i] = w_dist(rng);
    for (size_t i = 0; i < 64 * 64; ++i) rsnn.w_hidden_hidden[i] = w_dist(rng);
    for (size_t i = 0; i < 64 * 4; ++i) rsnn.w_motor[i] = w_dist(rng);

    alignas(64) uint8_t s_in[32] = {0};
    s_in[0] = 1; s_in[5] = 1; s_in[22] = 1; // 3 sensory spikes active
    alignas(64) uint8_t s_out[32];
    alignas(64) uint8_t h_out[64];
    alignas(64) uint8_t m_out[4];

    // Warm-up
    for (size_t w = 0; w < 1000; ++w) {
        rsnn.step(s_in, s_out, h_out, m_out);
    }

    std::vector<uint64_t> cycles_list;
    cycles_list.reserve(iterations);

    auto t_start = std::chrono::high_resolution_clock::now();
    uint64_t total_cycles = 0;

    for (size_t it = 0; it < iterations; ++it) {
        uint64_t c0 = neuroquant::rdtscp();
        rsnn.step(s_in, s_out, h_out, m_out);
        uint64_t c1 = neuroquant::rdtscp();
        uint64_t diff = (c1 > c0) ? (c1 - c0) : 0;
        cycles_list.push_back(diff);
        total_cycles += diff;
    }

    auto t_end = std::chrono::high_resolution_clock::now();
    double total_ns = std::chrono::duration<double, std::nano>(t_end - t_start).count();

    std::sort(cycles_list.begin(), cycles_list.end());

    stats->total_steps = iterations;
    stats->total_cycles = total_cycles;
    stats->min_cycles = cycles_list.front();
    stats->max_cycles = cycles_list.back();
    stats->p50_cycles = static_cast<double>(cycles_list[iterations * 50 / 100]);
    stats->p90_cycles = static_cast<double>(cycles_list[iterations * 90 / 100]);
    stats->p99_cycles = static_cast<double>(cycles_list[iterations * 99 / 100]);
    stats->p999_cycles = static_cast<double>(cycles_list[iterations * 999 / 1000]);
    stats->avg_nanoseconds = total_ns / static_cast<double>(iterations);
    stats->steps_per_second = (iterations / total_ns) * 1e9;
}

} // extern "C"
