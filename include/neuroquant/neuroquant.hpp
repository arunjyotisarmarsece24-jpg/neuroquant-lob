/**
 * NeuroQuant-LOB: Header-Only C++20 HFT Quantitative Architecture
 * ==============================================================
 * Master Umbrella Header for Elite Bare-Metal High-Frequency Trading Desks.
 *
 * Modules Included:
 *   - neuroquant/lif_avx2.hpp     : 230 ns SIMD Leaky Integrate-and-Fire Neuromorphic Core
 *   - neuroquant/almgren_simd.hpp : 2.82 μs Hyperbolic Almgren-Chriss Optimal Execution Solver
 *   - neuroquant/risk_gate.hpp    : < 20 ns Pre-Trade Microsecond Hardware Risk Gate
 *   - neuroquant/itch_parser.hpp  : 30.18M msgs/s NASDAQ TotalView-ITCH 5.0 Feed & L2 DOM
 *
 * Author: Arunjyoti Sarma (Research Scholar, IIT (BHU), Varanasi)
 * Project: NeuroQuant-LOB Flagship Quantitative Architecture
 * Version: 1.1.0-PROD
 */

#pragma once

#define NEUROQUANT_VERSION_MAJOR 1
#define NEUROQUANT_VERSION_MINOR 1
#define NEUROQUANT_VERSION_PATCH 0
#define NEUROQUANT_VERSION_STRING "1.1.0-PROD"
#define NEUROQUANT_AUTHOR "Arunjyoti Sarma"
#define NEUROQUANT_INSTITUTION "IIT (BHU), Varanasi"

#include "lif_avx2.hpp"
#include "almgren_simd.hpp"
#include "risk_gate.hpp"
#include "itch_parser.hpp"

namespace neuroquant {

inline const char* get_version() noexcept {
    return NEUROQUANT_VERSION_STRING;
}

inline const char* get_author() noexcept {
    return NEUROQUANT_AUTHOR;
}

} // namespace neuroquant
