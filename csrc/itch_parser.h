#pragma once

#include <cstdint>
#include <cstddef>
#include <cstring>
#include <immintrin.h>
#include "lif_core.h"

#if defined(_WIN32) || defined(__CYGWIN__)
  #ifdef LIF_EXPORTS
    #define ITCH_API __declspec(dllexport)
  #else
    #define ITCH_API __declspec(dllimport)
  #endif
#else
  #define ITCH_API __attribute__((visibility("default")))
#endif

namespace neuroquant::itch {

// Big-Endian byte swap helpers for x86_64 single-cycle execution
[[nodiscard]] static inline uint16_t be16(uint16_t val) noexcept {
#if defined(_MSC_VER)
    return _byteswap_ushort(val);
#else
    return __builtin_bswap16(val);
#endif
}

[[nodiscard]] static inline uint32_t be32(uint32_t val) noexcept {
#if defined(_MSC_VER)
    return _byteswap_ulong(val);
#else
    return __builtin_bswap32(val);
#endif
}

[[nodiscard]] static inline uint64_t be64(uint64_t val) noexcept {
#if defined(_MSC_VER)
    return _byteswap_uint64(val);
#else
    return __builtin_bswap64(val);
#endif
}

[[nodiscard]] static inline uint64_t be48(const uint8_t ts[6]) noexcept {
    return (static_cast<uint64_t>(ts[0]) << 40) |
           (static_cast<uint64_t>(ts[1]) << 32) |
           (static_cast<uint64_t>(ts[2]) << 24) |
           (static_cast<uint64_t>(ts[3]) << 16) |
           (static_cast<uint64_t>(ts[4]) << 8)  |
           (static_cast<uint64_t>(ts[5]));
}

#pragma pack(push, 1)

// Message Type 'S': System Event Message (11 bytes payload)
struct SystemEventMsg {
    char type;                 // 'S'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    char event_code;           // 'O', 'S', 'Q', 'M', 'E', 'C'
};

// Message Type 'R': Stock Directory Message (38 bytes payload)
struct StockDirectoryMsg {
    char type;                 // 'R'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    char stock[8];
    char market_category;
    char financial_status;
    uint32_t round_lot_size;
    char round_lots_only;
    char issue_classification;
    char issue_sub_type[2];
    char authenticity;
    char short_sale_threshold;
    char ipo_flag;
    char luld_tier;
    char etp_flag;
    uint32_t etp_leverage_factor;
    char inverse_indicator;
};

// Message Type 'A': Add Order - No MPID Attribution (35 bytes payload)
struct AddOrderMsg {
    char type;                 // 'A'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t order_reference;
    char buy_sell_indicator;   // 'B' or 'S'
    uint32_t shares;
    char stock[8];
    uint32_t price;            // 4 decimal places
};

// Message Type 'F': Add Order with MPID Attribution (39 bytes payload)
struct AddOrderMPIDMsg {
    char type;                 // 'F'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t order_reference;
    char buy_sell_indicator;   // 'B' or 'S'
    uint32_t shares;
    char stock[8];
    uint32_t price;
    char attribution[4];
};

// Message Type 'E': Order Executed Message (30 bytes payload)
struct OrderExecutedMsg {
    char type;                 // 'E'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t order_reference;
    uint32_t executed_shares;
    uint64_t match_number;
};

// Message Type 'C': Order Executed With Price Message (35 bytes payload)
struct OrderExecutedPriceMsg {
    char type;                 // 'C'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t order_reference;
    uint32_t executed_shares;
    uint64_t match_number;
    char printable;            // 'Y' or 'N'
    uint32_t execution_price;
};

// Message Type 'X': Order Cancel Message (22 bytes payload)
struct OrderCancelMsg {
    char type;                 // 'X'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t order_reference;
    uint32_t canceled_shares;
};

// Message Type 'D': Order Delete Message (18 bytes payload)
struct OrderDeleteMsg {
    char type;                 // 'D'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t order_reference;
};

// Message Type 'U': Order Replace Message (34 bytes payload)
struct OrderReplaceMsg {
    char type;                 // 'U'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t orig_order_reference;
    uint64_t new_order_reference;
    uint32_t shares;
    uint32_t price;
};

// Message Type 'P': Non-Cross Trade Message (43 bytes payload)
struct TradeMsg {
    char type;                 // 'P'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t order_reference;
    char buy_sell_indicator;   // 'B' or 'S'
    uint32_t shares;
    char stock[8];
    uint32_t price;
    uint64_t match_number;
};

// Message Type 'Q': Cross Trade Message (39 bytes payload)
struct CrossTradeMsg {
    char type;                 // 'Q'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t shares;
    char stock[8];
    uint32_t cross_price;
    uint64_t match_number;
    char cross_type;
};

// Message Type 'B': Broken Trade Message (18 bytes payload)
struct BrokenTradeMsg {
    char type;                 // 'B'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t match_number;
};

// Message Type 'I': NOII Net Order Imbalance Message (49 bytes payload)
struct NOIIMsg {
    char type;                 // 'I'
    uint16_t stock_locate;
    uint16_t tracking_number;
    uint8_t timestamp[6];
    uint64_t paired_shares;
    uint64_t imbalance_shares;
    char imbalance_direction;
    char stock[8];
    uint32_t far_price;
    uint32_t near_price;
    uint32_t current_ref_price;
    char cross_type;
    char price_variation_indicator;
};

#pragma pack(pop)

#pragma pack(push, 8)
struct ITCHParserStats {
    uint64_t total_messages;
    uint64_t add_orders;
    uint64_t executed_orders;
    uint64_t cancel_orders;
    uint64_t delete_orders;
    uint64_t replace_orders;
    uint64_t trade_messages;
    uint64_t other_messages;
    uint64_t total_bytes_parsed;
    uint64_t parse_time_nanos;
    double msgs_per_second;
    double mb_per_second;
};

struct ParsedOrderEvent {
    char msg_type;
    uint8_t _pad0[7];
    uint64_t timestamp_ns;
    uint64_t order_ref;
    uint64_t new_order_ref; // for 'U' replace
    char side;              // 'B' or 'S'
    uint8_t _pad1[3];
    uint32_t shares;
    double price;           // floating point price, e.g. 185.25
    char stock[9];          // null-terminated stock ticker
    uint8_t _pad2[7];
    uint64_t match_number;
};
#pragma pack(pop)

// Maximum active orders tracked in high-speed pool
constexpr size_t MAX_ITCH_ORDERS = 262144; // 256K active orders
constexpr size_t MAX_LADDER_LEVELS = 16;   // Top 16 contiguous price levels (fits in 2 cache lines)

struct alignas(64) OrderNode {
    uint64_t order_ref{0};
    uint32_t price{0};
    uint32_t shares{0};
    uint16_t stock_locate{0};
    char side{0};
    bool active{false};
};

struct PriceLevel {
    uint32_t price{0};
    uint32_t shares{0};
    uint32_t order_count{0};
};

#pragma pack(push, 8)
struct L2Depth10 {
    double bid_prices[10];
    uint32_t bid_shares[10];
    double ask_prices[10];
    uint32_t ask_shares[10];
    uint32_t bid_levels;
    uint32_t ask_levels;
    double micro_price;
    double spread;
    double depth_imbalance; // (total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol)
    double vwap_bid;
    double vwap_ask;
};

struct HotpathDecision {
    int32_t action;             // +1 = Strong Buy, -1 = Strong Sell, 0 = Hold
    float confidence;           // Confidence score [0.0f, 1.0f]
    uint64_t latency_cycles;    // RDTSCP cycles from wire packet to decision
    double latency_ns;          // Latency in nanoseconds (~0.33 ns/cycle)
    double micro_price;         // Instantaneous fair micro-price
    double depth_imbalance;     // 10-level order book imbalance
    uint8_t sensory_spikes[32]; // Spikes emitted by ITCH event
    uint8_t motor_spikes[4];    // Motor neurons fired by RSNN
};

struct HotpathBenchmarkStats {
    uint64_t total_packets;
    uint64_t total_cycles;
    double avg_nanos;
    double packets_per_sec;
    uint64_t buy_signals;
    uint64_t sell_signals;
    uint64_t hold_signals;
    double avg_confidence;
};
#pragma pack(pop)

class ITCHOrderBookCore {
public:
    uint32_t best_bid_price{0};
    uint32_t best_ask_price{0};
    uint32_t best_bid_shares{0};
    uint32_t best_ask_shares{0};
    uint64_t total_bid_volume{0};
    uint64_t total_ask_volume{0};

    // Cache-aligned contiguous price ladders (sorted descending for bids, ascending for asks)
    PriceLevel bid_ladder[MAX_LADDER_LEVELS];
    size_t bid_ladder_depth{0};
    PriceLevel ask_ladder[MAX_LADDER_LEVELS];
    size_t ask_ladder_depth{0};

    // Fast direct index / flat open-addressing table for active orders
    OrderNode order_pool[MAX_ITCH_ORDERS];

    ITCHOrderBookCore() noexcept {
        reset();
    }

    void reset() noexcept {
        best_bid_price = 0;
        best_ask_price = 0xFFFFFFFF;
        best_bid_shares = 0;
        best_ask_shares = 0;
        total_bid_volume = 0;
        total_ask_volume = 0;
        bid_ladder_depth = 0;
        ask_ladder_depth = 0;
        for (size_t i = 0; i < MAX_LADDER_LEVELS; ++i) {
            bid_ladder[i] = PriceLevel{};
            ask_ladder[i] = PriceLevel{};
        }
        for (size_t i = 0; i < MAX_ITCH_ORDERS; ++i) {
            order_pool[i].active = false;
        }
    }

    // Hash lookup for order_ref
    [[nodiscard]] inline size_t get_hash_index(uint64_t order_ref) const noexcept {
        return static_cast<size_t>(order_ref & (MAX_ITCH_ORDERS - 1));
    }

    inline void on_add_order(uint64_t order_ref, char side, uint32_t shares, uint32_t price, uint16_t locate) noexcept {
        size_t idx = get_hash_index(order_ref);
        size_t attempts = 0;
        while (order_pool[idx].active && order_pool[idx].order_ref != order_ref && attempts < 16) {
            idx = (idx + 1) & (MAX_ITCH_ORDERS - 1);
            attempts++;
        }
        order_pool[idx].order_ref = order_ref;
        order_pool[idx].side = side;
        order_pool[idx].shares = shares;
        order_pool[idx].price = price;
        order_pool[idx].stock_locate = locate;
        order_pool[idx].active = true;

        if (side == 'B') {
            total_bid_volume += shares;
            // 1. Fast path: Direct hit on current Best Bid
            if (bid_ladder_depth > 0 && price == bid_ladder[0].price) {
                bid_ladder[0].shares += shares;
                bid_ladder[0].order_count++;
                best_bid_shares += shares;
                return;
            }
            // 2. Fast path: New Best Bid (price > best_bid)
            if (bid_ladder_depth > 0 && price > bid_ladder[0].price) {
                size_t shift_len = (bid_ladder_depth < MAX_LADDER_LEVELS) ? bid_ladder_depth : (MAX_LADDER_LEVELS - 1);
                for (size_t k = shift_len; k > 0; --k) {
                    bid_ladder[k] = bid_ladder[k - 1];
                }
                bid_ladder[0] = PriceLevel{price, shares, 1};
                if (bid_ladder_depth < MAX_LADDER_LEVELS) bid_ladder_depth++;
                best_bid_price = price;
                best_bid_shares = shares;
                return;
            }
            // 3. Fast path: Outside top 16 levels -> skip ladder search
            if (bid_ladder_depth >= MAX_LADDER_LEVELS && price <= bid_ladder[MAX_LADDER_LEVELS - 1].price) {
                return;
            }
            // 4. Within top 16 levels
            bool found = false;
            for (size_t i = 1; i < bid_ladder_depth; ++i) {
                if (bid_ladder[i].price == price) {
                    bid_ladder[i].shares += shares;
                    bid_ladder[i].order_count++;
                    found = true;
                    break;
                }
            }
            if (!found && bid_ladder_depth < MAX_LADDER_LEVELS) {
                size_t insert_pos = bid_ladder_depth;
                for (size_t i = 1; i < bid_ladder_depth; ++i) {
                    if (price > bid_ladder[i].price) {
                        insert_pos = i;
                        break;
                    }
                }
                for (size_t k = bid_ladder_depth; k > insert_pos; --k) {
                    bid_ladder[k] = bid_ladder[k - 1];
                }
                bid_ladder[insert_pos] = PriceLevel{price, shares, 1};
                bid_ladder_depth++;
            }
            best_bid_price = (bid_ladder_depth > 0) ? bid_ladder[0].price : 0;
            best_bid_shares = (bid_ladder_depth > 0) ? bid_ladder[0].shares : 0;
        } else if (side == 'S') {
            total_ask_volume += shares;
            // 1. Fast path: Direct hit on current Best Ask
            if (ask_ladder_depth > 0 && price == ask_ladder[0].price) {
                ask_ladder[0].shares += shares;
                ask_ladder[0].order_count++;
                best_ask_shares += shares;
                return;
            }
            // 2. Fast path: New Best Ask (price < best_ask)
            if (ask_ladder_depth > 0 && price < ask_ladder[0].price) {
                size_t shift_len = (ask_ladder_depth < MAX_LADDER_LEVELS) ? ask_ladder_depth : (MAX_LADDER_LEVELS - 1);
                for (size_t k = shift_len; k > 0; --k) {
                    ask_ladder[k] = ask_ladder[k - 1];
                }
                ask_ladder[0] = PriceLevel{price, shares, 1};
                if (ask_ladder_depth < MAX_LADDER_LEVELS) ask_ladder_depth++;
                best_ask_price = price;
                best_ask_shares = shares;
                return;
            }
            // 3. Fast path: Outside top 16 levels -> skip ladder search
            if (ask_ladder_depth >= MAX_LADDER_LEVELS && price >= ask_ladder[MAX_LADDER_LEVELS - 1].price) {
                return;
            }
            // 4. Within top 16 levels
            bool found = false;
            for (size_t i = 1; i < ask_ladder_depth; ++i) {
                if (ask_ladder[i].price == price) {
                    ask_ladder[i].shares += shares;
                    ask_ladder[i].order_count++;
                    found = true;
                    break;
                }
            }
            if (!found && ask_ladder_depth < MAX_LADDER_LEVELS) {
                size_t insert_pos = ask_ladder_depth;
                for (size_t i = 1; i < ask_ladder_depth; ++i) {
                    if (price < ask_ladder[i].price) {
                        insert_pos = i;
                        break;
                    }
                }
                for (size_t k = ask_ladder_depth; k > insert_pos; --k) {
                    ask_ladder[k] = ask_ladder[k - 1];
                }
                ask_ladder[insert_pos] = PriceLevel{price, shares, 1};
                ask_ladder_depth++;
            }
            best_ask_price = (ask_ladder_depth > 0) ? ask_ladder[0].price : 0xFFFFFFFF;
            best_ask_shares = (ask_ladder_depth > 0) ? ask_ladder[0].shares : 0;
        }
    }

    inline void on_cancel_order(uint64_t order_ref, uint32_t cancel_shares) noexcept {
        size_t idx = get_hash_index(order_ref);
        size_t attempts = 0;
        while (attempts < 16) {
            if (order_pool[idx].active && order_pool[idx].order_ref == order_ref) {
                uint32_t actual_sub = (cancel_shares > order_pool[idx].shares) ? order_pool[idx].shares : cancel_shares;
                order_pool[idx].shares -= actual_sub;
                uint32_t price = order_pool[idx].price;
                char side = order_pool[idx].side;

                if (side == 'B') {
                    total_bid_volume = (total_bid_volume > actual_sub) ? (total_bid_volume - actual_sub) : 0;
                    for (size_t i = 0; i < bid_ladder_depth; ++i) {
                        if (bid_ladder[i].price == price) {
                            bid_ladder[i].shares = (bid_ladder[i].shares > actual_sub) ? (bid_ladder[i].shares - actual_sub) : 0;
                            if (order_pool[idx].shares == 0) {
                                bid_ladder[i].order_count = (bid_ladder[i].order_count > 0) ? bid_ladder[i].order_count - 1 : 0;
                            }
                            if (bid_ladder[i].shares == 0) {
                                for (size_t k = i; k + 1 < bid_ladder_depth; ++k) {
                                    bid_ladder[k] = bid_ladder[k + 1];
                                }
                                bid_ladder_depth--;
                            }
                            break;
                        }
                    }
                    best_bid_price = (bid_ladder_depth > 0) ? bid_ladder[0].price : 0;
                    best_bid_shares = (bid_ladder_depth > 0) ? bid_ladder[0].shares : 0;
                } else if (side == 'S') {
                    total_ask_volume = (total_ask_volume > actual_sub) ? (total_ask_volume - actual_sub) : 0;
                    for (size_t i = 0; i < ask_ladder_depth; ++i) {
                        if (ask_ladder[i].price == price) {
                            ask_ladder[i].shares = (ask_ladder[i].shares > actual_sub) ? (ask_ladder[i].shares - actual_sub) : 0;
                            if (order_pool[idx].shares == 0) {
                                ask_ladder[i].order_count = (ask_ladder[i].order_count > 0) ? ask_ladder[i].order_count - 1 : 0;
                            }
                            if (ask_ladder[i].shares == 0) {
                                for (size_t k = i; k + 1 < ask_ladder_depth; ++k) {
                                    ask_ladder[k] = ask_ladder[k + 1];
                                }
                                ask_ladder_depth--;
                            }
                            break;
                        }
                    }
                    best_ask_price = (ask_ladder_depth > 0) ? ask_ladder[0].price : 0xFFFFFFFF;
                    best_ask_shares = (ask_ladder_depth > 0) ? ask_ladder[0].shares : 0;
                }

                if (order_pool[idx].shares == 0) {
                    order_pool[idx].active = false;
                }
                return;
            }
            idx = (idx + 1) & (MAX_ITCH_ORDERS - 1);
            attempts++;
        }
    }

    inline void on_delete_order(uint64_t order_ref) noexcept {
        size_t idx = get_hash_index(order_ref);
        size_t attempts = 0;
        while (attempts < 16) {
            if (order_pool[idx].active && order_pool[idx].order_ref == order_ref) {
                on_cancel_order(order_ref, order_pool[idx].shares);
                return;
            }
            idx = (idx + 1) & (MAX_ITCH_ORDERS - 1);
            attempts++;
        }
    }

    inline void get_depth_10(L2Depth10* out_depth) const noexcept {
        if (!out_depth) return;
        std::memset(out_depth, 0, sizeof(L2Depth10));

        uint32_t b_levels = static_cast<uint32_t>((bid_ladder_depth < 10) ? bid_ladder_depth : 10);
        uint32_t a_levels = static_cast<uint32_t>((ask_ladder_depth < 10) ? ask_ladder_depth : 10);

        out_depth->bid_levels = b_levels;
        out_depth->ask_levels = a_levels;

        double sum_bid_val = 0.0;
        uint64_t sum_bid_vol = 0;
        for (uint32_t i = 0; i < b_levels; ++i) {
            out_depth->bid_prices[i] = static_cast<double>(bid_ladder[i].price) / 10000.0;
            out_depth->bid_shares[i] = bid_ladder[i].shares;
            sum_bid_val += out_depth->bid_prices[i] * static_cast<double>(bid_ladder[i].shares);
            sum_bid_vol += bid_ladder[i].shares;
        }

        double sum_ask_val = 0.0;
        uint64_t sum_ask_vol = 0;
        for (uint32_t i = 0; i < a_levels; ++i) {
            out_depth->ask_prices[i] = static_cast<double>(ask_ladder[i].price) / 10000.0;
            out_depth->ask_shares[i] = ask_ladder[i].shares;
            sum_ask_val += out_depth->ask_prices[i] * static_cast<double>(ask_ladder[i].shares);
            sum_ask_vol += ask_ladder[i].shares;
        }

        out_depth->vwap_bid = (sum_bid_vol > 0) ? (sum_bid_val / static_cast<double>(sum_bid_vol)) : 0.0;
        out_depth->vwap_ask = (sum_ask_vol > 0) ? (sum_ask_val / static_cast<double>(sum_ask_vol)) : 0.0;

        double b0 = (b_levels > 0) ? out_depth->bid_prices[0] : 0.0;
        double a0 = (a_levels > 0) ? out_depth->ask_prices[0] : 0.0;
        uint32_t bs0 = (b_levels > 0) ? out_depth->bid_shares[0] : 0;
        uint32_t as0 = (a_levels > 0) ? out_depth->ask_shares[0] : 0;

        if (b0 > 0.0 && a0 > 0.0 && a0 >= b0) {
            out_depth->spread = a0 - b0;
            if (bs0 + as0 > 0) {
                out_depth->micro_price = (static_cast<double>(bs0) * a0 + static_cast<double>(as0) * b0) / static_cast<double>(bs0 + as0);
            } else {
                out_depth->micro_price = (b0 + a0) * 0.5;
            }
        } else {
            out_depth->spread = 0.0;
            out_depth->micro_price = (b0 > 0.0) ? b0 : a0;
        }

        if (sum_bid_vol + sum_ask_vol > 0) {
            out_depth->depth_imbalance = static_cast<double>(static_cast<int64_t>(sum_bid_vol) - static_cast<int64_t>(sum_ask_vol)) /
                                         static_cast<double>(sum_bid_vol + sum_ask_vol);
        } else {
            out_depth->depth_imbalance = 0.0;
        }
    }
};

// Institutional Unified Neuromorphic LOB Hot-Path Pipeline
class NeuromorphicLOBPipeline {
public:
    ITCHOrderBookCore book;
    neuroquant::RSNNCoreSIMD rsnn;

    NeuromorphicLOBPipeline();
    void reset() noexcept;
    void process_packet(const uint8_t* packet_data, size_t length, HotpathDecision* out_decision) noexcept;
    void run_stream_benchmark(const uint8_t* buffer, size_t total_bytes, HotpathBenchmarkStats* out_stats) noexcept;
};

} // namespace neuroquant::itch

// Clean C ABI for Zero-Overhead Python ctypes Integration
extern "C" {
    ITCH_API void* itch_parser_create();
    ITCH_API void itch_parser_destroy(void* handle);
    ITCH_API void itch_parser_reset(void* handle);

    ITCH_API int itch_parse_message(const uint8_t* msg_buffer,
                                   size_t length,
                                   neuroquant::itch::ParsedOrderEvent* out_event);

    ITCH_API size_t itch_parse_stream(void* book_handle,
                                      const uint8_t* buffer,
                                      size_t total_bytes,
                                      bool has_2byte_length_prefix,
                                      neuroquant::itch::ITCHParserStats* out_stats);

    ITCH_API void itch_get_top_of_book(void* book_handle,
                                       double* out_best_bid,
                                       double* out_best_ask,
                                       uint32_t* out_bid_shares,
                                       uint32_t* out_ask_shares,
                                       uint64_t* out_total_bid_vol,
                                       uint64_t* out_total_ask_vol);

    ITCH_API void itch_get_depth_10(void* book_handle,
                                    neuroquant::itch::L2Depth10* out_depth);

    ITCH_API size_t itch_generate_synthetic_stream(uint8_t* out_buffer,
                                                   size_t max_bytes,
                                                   size_t num_messages,
                                                   bool add_2byte_length_prefix);

    ITCH_API void run_itch_benchmark(size_t num_messages, neuroquant::itch::ITCHParserStats* out_stats);

    // Unified Hot-Path Pipeline (Packet -> Book -> Spikes -> RSNN SIMD -> Signal in < 150 ns)
    ITCH_API void* itch_pipeline_create();
    ITCH_API void itch_pipeline_destroy(void* handle);
    ITCH_API void itch_pipeline_reset(void* handle);
    ITCH_API void itch_pipeline_process_packet(void* handle,
                                              const uint8_t* packet_bytes,
                                              size_t length,
                                              neuroquant::itch::HotpathDecision* out_decision);
    ITCH_API void itch_pipeline_run_benchmark(void* handle,
                                              size_t num_packets,
                                              neuroquant::itch::HotpathBenchmarkStats* out_stats);
}
