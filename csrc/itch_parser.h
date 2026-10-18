#pragma once

#include <cstdint>
#include <cstddef>
#include <cstring>
#include <immintrin.h>

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

struct alignas(64) OrderNode {
    uint64_t order_ref{0};
    uint32_t price{0};
    uint32_t shares{0};
    uint16_t stock_locate{0};
    char side{0};
    bool active{false};
};

class ITCHOrderBookCore {
public:
    uint32_t best_bid_price{0};
    uint32_t best_ask_price{0};
    uint32_t best_bid_shares{0};
    uint32_t best_ask_shares{0};
    uint64_t total_bid_volume{0};
    uint64_t total_ask_volume{0};

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
        // Linear probing if occupied
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
            if (price > best_bid_price) {
                best_bid_price = price;
                best_bid_shares = shares;
            } else if (price == best_bid_price) {
                best_bid_shares += shares;
            }
        } else if (side == 'S') {
            total_ask_volume += shares;
            if (price < best_ask_price) {
                best_ask_price = price;
                best_ask_shares = shares;
            } else if (price == best_ask_price) {
                best_ask_shares += shares;
            }
        }
    }

    inline void on_cancel_order(uint64_t order_ref, uint32_t cancel_shares) noexcept {
        size_t idx = get_hash_index(order_ref);
        size_t attempts = 0;
        while (attempts < 16) {
            if (order_pool[idx].active && order_pool[idx].order_ref == order_ref) {
                uint32_t actual_sub = (cancel_shares > order_pool[idx].shares) ? order_pool[idx].shares : cancel_shares;
                order_pool[idx].shares -= actual_sub;
                if (order_pool[idx].side == 'B') {
                    total_bid_volume = (total_bid_volume > actual_sub) ? (total_bid_volume - actual_sub) : 0;
                    if (order_pool[idx].price == best_bid_price) {
                        best_bid_shares = (best_bid_shares > actual_sub) ? (best_bid_shares - actual_sub) : 0;
                    }
                } else if (order_pool[idx].side == 'S') {
                    total_ask_volume = (total_ask_volume > actual_sub) ? (total_ask_volume - actual_sub) : 0;
                    if (order_pool[idx].price == best_ask_price) {
                        best_ask_shares = (best_ask_shares > actual_sub) ? (best_ask_shares - actual_sub) : 0;
                    }
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
                uint32_t rem_shares = order_pool[idx].shares;
                if (order_pool[idx].side == 'B') {
                    total_bid_volume = (total_bid_volume > rem_shares) ? (total_bid_volume - rem_shares) : 0;
                    if (order_pool[idx].price == best_bid_price) {
                        best_bid_shares = (best_bid_shares > rem_shares) ? (best_bid_shares - rem_shares) : 0;
                    }
                } else if (order_pool[idx].side == 'S') {
                    total_ask_volume = (total_ask_volume > rem_shares) ? (total_ask_volume - rem_shares) : 0;
                    if (order_pool[idx].price == best_ask_price) {
                        best_ask_shares = (best_ask_shares > rem_shares) ? (best_ask_shares - rem_shares) : 0;
                    }
                }
                order_pool[idx].active = false;
                return;
            }
            idx = (idx + 1) & (MAX_ITCH_ORDERS - 1);
            attempts++;
        }
    }
};

} // namespace neuroquant::itch

// Clean C ABI for Zero-Overhead Python ctypes Integration
extern "C" {
    ITCH_API void* itch_parser_create();
    ITCH_API void itch_parser_destroy(void* handle);
    ITCH_API void itch_parser_reset(void* handle);

    // Parses a single raw ITCH 5.0 message from a byte buffer
    ITCH_API int itch_parse_message(const uint8_t* msg_buffer,
                                   size_t length,
                                   neuroquant::itch::ParsedOrderEvent* out_event);

    // Stream parser over contiguous byte buffer (SoupBinTCP 2-byte length framed or raw ITCH stream)
    ITCH_API size_t itch_parse_stream(void* book_handle,
                                      const uint8_t* buffer,
                                      size_t total_bytes,
                                      bool has_2byte_length_prefix,
                                      neuroquant::itch::ITCHParserStats* out_stats);

    // Get current top-of-book prices and volumes
    ITCH_API void itch_get_top_of_book(void* book_handle,
                                       double* out_best_bid,
                                       double* out_best_ask,
                                       uint32_t* out_bid_shares,
                                       uint32_t* out_ask_shares,
                                       uint64_t* out_total_bid_vol,
                                       uint64_t* out_total_ask_vol);

    // Synthetic high-speed ITCH message generator for ultra-realistic benchmarking
    ITCH_API size_t itch_generate_synthetic_stream(uint8_t* out_buffer,
                                                   size_t max_bytes,
                                                   size_t num_messages,
                                                   bool add_2byte_length_prefix);

    // Hardware micro-benchmark harness
    ITCH_API void run_itch_benchmark(size_t num_messages, neuroquant::itch::ITCHParserStats* out_stats);
}
