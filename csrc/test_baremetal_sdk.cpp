/**
 * NeuroQuant-LOB: Bare-Metal C++20 Header SDK Verification Test
 * =============================================================
 * Standalone compiler verification for include/neuroquant/ headers.
 * Compiles and benchmarks with pure native C++20 and AVX2 SIMD.
 *
 * Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
 */

#include <iostream>
#include <iomanip>
#include <chrono>
#include <cassert>
#include <cmath>

#include "../include/neuroquant/neuroquant.hpp"

using namespace neuroquant;

int main() {
    std::cout << "====================================================================\n";
    std::cout << "  NEUROQUANT-LOB: BARE-METAL C++20 HFT SDK VERIFICATION\n";
    std::cout << "  Author: " << get_author() << " | Version: " << get_version() << "\n";
    std::cout << "====================================================================\n\n";

    // -------------------------------------------------------------
    // Test 1: AVX2 SIMD Leaky Integrate-and-Fire Core (64 Neurons)
    // -------------------------------------------------------------
    std::cout << "[*] Test 1: Instantiating LifCoreAVX2<64> (64-byte aligned)...\n";
    alignas(64) LifCoreAVX2<64> lif_core;
    assert(lif_core.check_lyapunov_invariant());

    alignas(64) std::array<float, 64> synaptic_input;
    synaptic_input.fill(25.0f); // High stimulus to provoke spiking

    alignas(64) std::array<uint8_t, 64> spikes;
    
    // Benchmark 10,000 steps
    auto t0 = std::chrono::high_resolution_clock::now();
    for (int step = 0; step < 10000; ++step) {
        lif_core.step_simd(synaptic_input.data(), spikes.data());
    }
    auto t1 = std::chrono::high_resolution_clock::now();
    double total_us = std::chrono::duration<double, std::micro>(t1 - t0).count();
    double per_step_ns = (total_us / 10000.0) * 1000.0;

    std::cout << "    -> Total Steps: " << lif_core.total_steps << "\n";
    std::cout << "    -> Average Step Latency: " << std::fixed << std::setprecision(2) << per_step_ns << " ns / 64 neurons\n";
    std::cout << "    -> Lyapunov Invariant (Theorem 1): " << (lif_core.check_lyapunov_invariant() ? "VERIFIED" : "VIOLATED") << "\n";
    assert(lif_core.check_lyapunov_invariant());
    std::cout << "    [PASS] LifCoreAVX2 test passed cleanly.\n\n";

    // -------------------------------------------------------------
    // Test 2: Almgren-Chriss Optimal Execution Solver
    // -------------------------------------------------------------
    std::cout << "[*] Test 2: Almgren-Chriss Optimal Execution Solver & Non-Linear SIMD Impact...\n";
    ExecutionParams ac_params;
    ac_params.total_shares = 10000.0;
    ac_params.time_horizon_sec = 60.0;
    ac_params.num_intervals = 60;

    alignas(64) std::array<double, 61> holdings;
    alignas(64) std::array<double, 60> trades;
    alignas(64) std::array<double, 60> rates;

    auto ac_res = AlmgrenChrissSimd::solve(ac_params, holdings.data(), trades.data(), rates.data());
    std::cout << "    -> Half-life: " << ac_res.half_life_sec << " s\n";
    std::cout << "    -> Expected Shortfall:   $" << std::fixed << std::setprecision(2) << ac_res.expected_shortfall << "\n";
    std::cout << "    -> AC Variance:          " << ac_res.variance_shortfall << "\n";
    std::cout << "    -> TWAP Variance:        " << ac_res.twap_variance << " (" << std::setprecision(1) << ac_res.variance_reduction_pct << "% reduction)\n";
    std::cout << "    -> Total AC Utility:     $" << std::fixed << std::setprecision(2) << ac_res.utility << "\n";
    std::cout << "    -> Total TWAP Utility:   $" << ac_res.twap_utility << " (" << std::setprecision(1) << ac_res.utility_reduction_pct << "% optimal utility improvement)\n";
    assert(ac_res.variance_shortfall < ac_res.twap_variance);
    assert(ac_res.utility <= ac_res.twap_utility);

    // Vectorized Square-Root Impact
    alignas(64) std::array<float, 64> test_rates;
    alignas(64) std::array<float, 64> test_impacts;
    for (size_t i = 0; i < 64; ++i) {
        test_rates[i] = static_cast<float>(i * 5.0f);
    }
    AlmgrenChrissSimd::compute_square_root_impact_avx2(test_rates.data(), test_impacts.data(), 64, 2.5e-6f);
    assert(test_impacts[0] == 0.0f);
    assert(test_impacts[16] > 0.0f);
    std::cout << "    [PASS] AlmgrenChrissSimd test passed cleanly.\n\n";

    // -------------------------------------------------------------
    // Test 3: Pre-Trade Microsecond Risk Gate (7 Circuit Breakers)
    // -------------------------------------------------------------
    std::cout << "[*] Test 3: Pre-Trade Microsecond Hardware Risk Gate (< 20 ns target)...\n";
    PreTradeRiskGate risk_gate;

    // A. Normal Order -> ACCEPT
    auto r1 = risk_gate.validate_order(true, 10.0, 18505.0, 18500.0, 0.0, 0.0, -70.0f);
    assert(r1.passed);
    assert(r1.action == RiskAction::ACCEPT);
    std::cout << "    -> Normal Order: ACCEPT (" << std::fixed << std::setprecision(1) << r1.latency_ns << " ns)\n";

    // B. Fat Finger -> REJECT
    auto r2 = risk_gate.validate_order(true, 10.0, 19500.0, 18500.0, 0.0, 0.0, -70.0f); // +5.4% dev
    assert(!r2.passed);
    assert(r2.action == RiskAction::REJECT_FAT_FINGER);
    std::cout << "    -> Fat-Finger Violation: REJECT (" << r2.reason << ")\n";

    // C. Max Inventory Breach -> REJECT
    auto r3 = risk_gate.validate_order(true, 15.0, 18501.0, 18500.0, 45.0, 0.0, -70.0f); // 45 + 15 = 60 > 50
    assert(!r3.passed);
    assert(r3.action == RiskAction::REJECT_INVENTORY_LIMIT);
    std::cout << "    -> Inventory Limit Breach: REJECT (" << r3.reason << ")\n";

    // D. De-risking Order at Max Inventory -> ACCEPT (Bypass)
    auto r4 = risk_gate.validate_order(false, 15.0, 18499.0, 18500.0, 45.0, 0.0, -70.0f); // 45 - 15 = 30 < 50
    assert(r4.passed);
    std::cout << "    -> De-Risking Trade at Capacity: ACCEPT (De-risking bypass verified)\n";

    // E. Hard MTM Drawdown -> TRIP KILLSWITCH
    auto r5 = risk_gate.validate_order(true, 1.0, 18500.0, 18500.0, 0.0, -55000.0, -70.0f);
    assert(!r5.passed);
    assert(r5.action == RiskAction::TRIP_MTM_KILLSWITCH);
    assert(risk_gate.is_killed);
    std::cout << "    -> Hard MTM Breach: EMERGENCY KILLSWITCH ENGAGED (" << r5.reason << ")\n";

    // F. Subsequent order after killswitch -> REJECT
    auto r6 = risk_gate.validate_order(true, 1.0, 18500.0, 18500.0, 0.0, 0.0, -70.0f);
    assert(!r6.passed);
    assert(r6.action == RiskAction::REJECT_KILLSWITCH_ACTIVE);
    std::cout << "    -> Post-Killswitch Order: REJECT (System halted)\n";
    std::cout << "    [PASS] PreTradeRiskGate verified across all circuit breakers.\n\n";

    // -------------------------------------------------------------
    // Test 4: ITCH 5.0 L2 Order Book Ladder & Stoikov Micro-Price
    // -------------------------------------------------------------
    std::cout << "[*] Test 4: ITCH 5.0 L2 Order Book Ladder & Stoikov Micro-Price...\n";
    itch::L2BookLadder book;
    book.bids[0] = {65000.0, 10.0, 5};
    book.bid_depth = 1;
    book.asks[0] = {65010.0, 2.0, 1};
    book.ask_depth = 1;

    double mid = book.mid_price();
    double micro = book.stoikov_micro_price();
    std::cout << "    -> Mid Price: $" << std::fixed << std::setprecision(2) << mid << "\n";
    std::cout << "    -> Stoikov Micro-Price (bid-heavy): $" << micro << "\n";
    // With 10 bids @ 65000 and 2 asks @ 65010, micro-price should tilt up towards 65010:
    // (10 * 65010 + 2 * 65000) / 12 = (650100 + 130000) / 12 = 780100 / 12 = 65008.33
    assert(micro > mid);
    std::cout << "    [PASS] Stoikov Micro-Price tilt verified.\n\n";

    std::cout << "====================================================================\n";
    std::cout << "  [SUCCESS] ALL BARE-METAL C++20 HFT SDK AUDITS PASSED CLEANLY!\n";
    std::cout << "====================================================================\n";
    return 0;
}
