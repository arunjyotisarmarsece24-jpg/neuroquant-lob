#include "itch_parser.h"
#include "lif_core.h"
#include <chrono>
#include <random>
#include <vector>
#include <string>

namespace neuroquant::itch {

// Lookup table for raw ITCH 5.0 message lengths by message type character
[[nodiscard]] static inline size_t get_itch_message_length(char type) noexcept {
    switch (type) {
        case 'S': return sizeof(SystemEventMsg);           // 11
        case 'R': return sizeof(StockDirectoryMsg);         // 38
        case 'H': return 24; // StockTradingAction Msg
        case 'Y': return 19;
        case 'L': return 25;
        case 'V': return 34;
        case 'W': return 11;
        case 'K': return 27;
        case 'J': return 34;
        case 'h': return 20;
        case 'A': return sizeof(AddOrderMsg);              // 35
        case 'F': return sizeof(AddOrderMPIDMsg);          // 39
        case 'E': return sizeof(OrderExecutedMsg);         // 30
        case 'C': return sizeof(OrderExecutedPriceMsg);    // 35
        case 'X': return sizeof(OrderCancelMsg);           // 22
        case 'D': return sizeof(OrderDeleteMsg);           // 18
        case 'U': return sizeof(OrderReplaceMsg);          // 34
        case 'P': return sizeof(TradeMsg);                 // 43
        case 'Q': return sizeof(CrossTradeMsg);            // 39
        case 'B': return sizeof(BrokenTradeMsg);           // 18
        case 'I': return sizeof(NOIIMsg);                  // 49
        case 'N': return 19;
        default:  return 0;
    }
}

} // namespace neuroquant::itch

extern "C" {

ITCH_API void* itch_parser_create() {
    return new neuroquant::itch::ITCHOrderBookCore();
}

ITCH_API void itch_parser_destroy(void* handle) {
    if (handle) {
        delete static_cast<neuroquant::itch::ITCHOrderBookCore*>(handle);
    }
}

ITCH_API void itch_parser_reset(void* handle) {
    if (handle) {
        static_cast<neuroquant::itch::ITCHOrderBookCore*>(handle)->reset();
    }
}

ITCH_API int itch_parse_message(const uint8_t* msg_buffer,
                               size_t length,
                               neuroquant::itch::ParsedOrderEvent* out_event) {
    if (!msg_buffer || length < 1 || !out_event) return -1;

    char msg_type = static_cast<char>(msg_buffer[0]);
    out_event->msg_type = msg_type;
    out_event->new_order_ref = 0;
    out_event->match_number = 0;
    out_event->price = 0.0;
    out_event->shares = 0;
    out_event->side = ' ';
    out_event->stock[0] = '\0';

    using namespace neuroquant::itch;

    switch (msg_type) {
        case 'A': {
            if (length < sizeof(AddOrderMsg)) return -2;
            const auto* msg = reinterpret_cast<const AddOrderMsg*>(msg_buffer);
            out_event->timestamp_ns = be48(msg->timestamp);
            out_event->order_ref = be64(msg->order_reference);
            out_event->side = msg->buy_sell_indicator;
            out_event->shares = be32(msg->shares);
            out_event->price = static_cast<double>(be32(msg->price)) / 10000.0;
            std::memcpy(out_event->stock, msg->stock, 8);
            out_event->stock[8] = '\0';
            return 0;
        }
        case 'F': {
            if (length < sizeof(AddOrderMPIDMsg)) return -2;
            const auto* msg = reinterpret_cast<const AddOrderMPIDMsg*>(msg_buffer);
            out_event->timestamp_ns = be48(msg->timestamp);
            out_event->order_ref = be64(msg->order_reference);
            out_event->side = msg->buy_sell_indicator;
            out_event->shares = be32(msg->shares);
            out_event->price = static_cast<double>(be32(msg->price)) / 10000.0;
            std::memcpy(out_event->stock, msg->stock, 8);
            out_event->stock[8] = '\0';
            return 0;
        }
        case 'E': {
            if (length < sizeof(OrderExecutedMsg)) return -2;
            const auto* msg = reinterpret_cast<const OrderExecutedMsg*>(msg_buffer);
            out_event->timestamp_ns = be48(msg->timestamp);
            out_event->order_ref = be64(msg->order_reference);
            out_event->shares = be32(msg->executed_shares);
            out_event->match_number = be64(msg->match_number);
            return 0;
        }
        case 'C': {
            if (length < sizeof(OrderExecutedPriceMsg)) return -2;
            const auto* msg = reinterpret_cast<const OrderExecutedPriceMsg*>(msg_buffer);
            out_event->timestamp_ns = be48(msg->timestamp);
            out_event->order_ref = be64(msg->order_reference);
            out_event->shares = be32(msg->executed_shares);
            out_event->match_number = be64(msg->match_number);
            out_event->price = static_cast<double>(be32(msg->execution_price)) / 10000.0;
            return 0;
        }
        case 'X': {
            if (length < sizeof(OrderCancelMsg)) return -2;
            const auto* msg = reinterpret_cast<const OrderCancelMsg*>(msg_buffer);
            out_event->timestamp_ns = be48(msg->timestamp);
            out_event->order_ref = be64(msg->order_reference);
            out_event->shares = be32(msg->canceled_shares);
            return 0;
        }
        case 'D': {
            if (length < sizeof(OrderDeleteMsg)) return -2;
            const auto* msg = reinterpret_cast<const OrderDeleteMsg*>(msg_buffer);
            out_event->timestamp_ns = be48(msg->timestamp);
            out_event->order_ref = be64(msg->order_reference);
            return 0;
        }
        case 'U': {
            if (length < sizeof(OrderReplaceMsg)) return -2;
            const auto* msg = reinterpret_cast<const OrderReplaceMsg*>(msg_buffer);
            out_event->timestamp_ns = be48(msg->timestamp);
            out_event->order_ref = be64(msg->orig_order_reference);
            out_event->new_order_ref = be64(msg->new_order_reference);
            out_event->shares = be32(msg->shares);
            out_event->price = static_cast<double>(be32(msg->price)) / 10000.0;
            return 0;
        }
        case 'P': {
            if (length < sizeof(TradeMsg)) return -2;
            const auto* msg = reinterpret_cast<const TradeMsg*>(msg_buffer);
            out_event->timestamp_ns = be48(msg->timestamp);
            out_event->order_ref = be64(msg->order_reference);
            out_event->side = msg->buy_sell_indicator;
            out_event->shares = be32(msg->shares);
            out_event->price = static_cast<double>(be32(msg->price)) / 10000.0;
            out_event->match_number = be64(msg->match_number);
            std::memcpy(out_event->stock, msg->stock, 8);
            out_event->stock[8] = '\0';
            return 0;
        }
        default: {
            return 0;
        }
    }
}

ITCH_API size_t itch_parse_stream(void* book_handle,
                                  const uint8_t* buffer,
                                  size_t total_bytes,
                                  bool has_2byte_length_prefix,
                                  neuroquant::itch::ITCHParserStats* out_stats) {
    if (!buffer || total_bytes == 0) return 0;

    auto* book = static_cast<neuroquant::itch::ITCHOrderBookCore*>(book_handle);
    using namespace neuroquant::itch;

    size_t offset = 0;
    uint64_t msg_count = 0;
    uint64_t add_count = 0;
    uint64_t exec_count = 0;
    uint64_t cancel_count = 0;
    uint64_t del_count = 0;
    uint64_t rep_count = 0;
    uint64_t trade_count = 0;
    uint64_t other_count = 0;

    auto t0 = std::chrono::high_resolution_clock::now();

    while (offset < total_bytes) {
        size_t msg_len = 0;
        const uint8_t* msg_ptr = nullptr;

        if (has_2byte_length_prefix) {
            if (offset + 2 > total_bytes) break;
            uint16_t raw_len = *reinterpret_cast<const uint16_t*>(&buffer[offset]);
            msg_len = be16(raw_len);
            offset += 2;
            if (offset + msg_len > total_bytes) break;
            msg_ptr = &buffer[offset];
            offset += msg_len;
        } else {
            char type = static_cast<char>(buffer[offset]);
            msg_len = get_itch_message_length(type);
            if (msg_len == 0 || offset + msg_len > total_bytes) break;
            msg_ptr = &buffer[offset];
            offset += msg_len;
        }

        if (msg_len == 0) break;
        char type = static_cast<char>(msg_ptr[0]);
        msg_count++;

        switch (type) {
            case 'A': {
                add_count++;
                if (book && msg_len >= sizeof(AddOrderMsg)) {
                    const auto* m = reinterpret_cast<const AddOrderMsg*>(msg_ptr);
                    book->on_add_order(be64(m->order_reference),
                                       m->buy_sell_indicator,
                                       be32(m->shares),
                                       be32(m->price),
                                       be16(m->stock_locate));
                }
                break;
            }
            case 'F': {
                add_count++;
                if (book && msg_len >= sizeof(AddOrderMPIDMsg)) {
                    const auto* m = reinterpret_cast<const AddOrderMPIDMsg*>(msg_ptr);
                    book->on_add_order(be64(m->order_reference),
                                       m->buy_sell_indicator,
                                       be32(m->shares),
                                       be32(m->price),
                                       be16(m->stock_locate));
                }
                break;
            }
            case 'E': {
                exec_count++;
                if (book && msg_len >= sizeof(OrderExecutedMsg)) {
                    const auto* m = reinterpret_cast<const OrderExecutedMsg*>(msg_ptr);
                    book->on_cancel_order(be64(m->order_reference), be32(m->executed_shares));
                }
                break;
            }
            case 'C': {
                exec_count++;
                if (book && msg_len >= sizeof(OrderExecutedPriceMsg)) {
                    const auto* m = reinterpret_cast<const OrderExecutedPriceMsg*>(msg_ptr);
                    book->on_cancel_order(be64(m->order_reference), be32(m->executed_shares));
                }
                break;
            }
            case 'X': {
                cancel_count++;
                if (book && msg_len >= sizeof(OrderCancelMsg)) {
                    const auto* m = reinterpret_cast<const OrderCancelMsg*>(msg_ptr);
                    book->on_cancel_order(be64(m->order_reference), be32(m->canceled_shares));
                }
                break;
            }
            case 'D': {
                del_count++;
                if (book && msg_len >= sizeof(OrderDeleteMsg)) {
                    const auto* m = reinterpret_cast<const OrderDeleteMsg*>(msg_ptr);
                    book->on_delete_order(be64(m->order_reference));
                }
                break;
            }
            case 'U': {
                rep_count++;
                if (book && msg_len >= sizeof(OrderReplaceMsg)) {
                    const auto* m = reinterpret_cast<const OrderReplaceMsg*>(msg_ptr);
                    book->on_delete_order(be64(m->orig_order_reference));
                    // Re-insert at new order ref (assumes same locate, side inferred from book or default)
                    book->on_add_order(be64(m->new_order_reference), 'B', be32(m->shares), be32(m->price), be16(m->stock_locate));
                }
                break;
            }
            case 'P': {
                trade_count++;
                break;
            }
            default: {
                other_count++;
                break;
            }
        }
    }

    auto t1 = std::chrono::high_resolution_clock::now();
    uint64_t elapsed_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(t1 - t0).count();

    if (out_stats) {
        out_stats->total_messages = msg_count;
        out_stats->add_orders = add_count;
        out_stats->executed_orders = exec_count;
        out_stats->cancel_orders = cancel_count;
        out_stats->delete_orders = del_count;
        out_stats->replace_orders = rep_count;
        out_stats->trade_messages = trade_count;
        out_stats->other_messages = other_count;
        out_stats->total_bytes_parsed = offset;
        out_stats->parse_time_nanos = elapsed_ns;
        double sec = static_cast<double>(elapsed_ns) / 1e9;
        out_stats->msgs_per_second = (sec > 0.0) ? (static_cast<double>(msg_count) / sec) : 0.0;
        out_stats->mb_per_second = (sec > 0.0) ? (static_cast<double>(offset) / (1024.0 * 1024.0 * sec)) : 0.0;
    }

    return msg_count;
}

ITCH_API void itch_get_top_of_book(void* book_handle,
                                   double* out_best_bid,
                                   double* out_best_ask,
                                   uint32_t* out_bid_shares,
                                   uint32_t* out_ask_shares,
                                   uint64_t* out_total_bid_vol,
                                   uint64_t* out_total_ask_vol) {
    if (!book_handle) return;
    auto* book = static_cast<neuroquant::itch::ITCHOrderBookCore*>(book_handle);
    if (out_best_bid) *out_best_bid = static_cast<double>(book->best_bid_price) / 10000.0;
    if (out_best_ask) *out_best_ask = (book->best_ask_price == 0xFFFFFFFF) ? 0.0 : static_cast<double>(book->best_ask_price) / 10000.0;
    if (out_bid_shares) *out_bid_shares = book->best_bid_shares;
    if (out_ask_shares) *out_ask_shares = book->best_ask_shares;
    if (out_total_bid_vol) *out_total_bid_vol = book->total_bid_volume;
    if (out_total_ask_vol) *out_total_ask_vol = book->total_ask_volume;
}

ITCH_API size_t itch_generate_synthetic_stream(uint8_t* out_buffer,
                                               size_t max_bytes,
                                               size_t num_messages,
                                               bool add_2byte_length_prefix) {
    if (!out_buffer || max_bytes < 100) return 0;

    using namespace neuroquant::itch;
    size_t offset = 0;
    std::mt19937 rng(42);
    std::uniform_int_distribution<uint32_t> side_dist(0, 1);
    std::uniform_int_distribution<uint32_t> shares_dist(1, 100);
    std::uniform_int_distribution<uint32_t> price_dist(1800000, 1860000); // $180.0000 to $186.0000

    uint64_t order_counter = 100000;
    uint64_t ts_sim = 34200000000000ULL; // 09:30:00.000 in ns past midnight

    for (size_t i = 0; i < num_messages; ++i) {
        ts_sim += 250; // +250ns between events
        uint8_t ts_bytes[6];
        ts_bytes[0] = static_cast<uint8_t>((ts_sim >> 40) & 0xFF);
        ts_bytes[1] = static_cast<uint8_t>((ts_sim >> 32) & 0xFF);
        ts_bytes[2] = static_cast<uint8_t>((ts_sim >> 24) & 0xFF);
        ts_bytes[3] = static_cast<uint8_t>((ts_sim >> 16) & 0xFF);
        ts_bytes[4] = static_cast<uint8_t>((ts_sim >> 8) & 0xFF);
        ts_bytes[5] = static_cast<uint8_t>(ts_sim & 0xFF);

        // Mix: 60% Add ('A'), 15% Executed ('E'), 15% Cancel ('X'), 5% Delete ('D'), 5% Trade ('P')
        int roll = static_cast<int>(i % 20);

        if (roll < 12) {
            // Add Order ('A')
            size_t msg_len = sizeof(AddOrderMsg);
            size_t required = add_2byte_length_prefix ? (msg_len + 2) : msg_len;
            if (offset + required > max_bytes) break;

            if (add_2byte_length_prefix) {
                *reinterpret_cast<uint16_t*>(&out_buffer[offset]) = be16(static_cast<uint16_t>(msg_len));
                offset += 2;
            }

            auto* m = reinterpret_cast<AddOrderMsg*>(&out_buffer[offset]);
            m->type = 'A';
            m->stock_locate = be16(1);
            m->tracking_number = be16(static_cast<uint16_t>(i));
            std::memcpy(m->timestamp, ts_bytes, 6);
            m->order_reference = be64(order_counter++);
            m->buy_sell_indicator = (side_dist(rng) == 0) ? 'B' : 'S';
            m->shares = be32(shares_dist(rng) * 10);
            std::memcpy(m->stock, "NVDA    ", 8);
            m->price = be32(price_dist(rng));
            offset += msg_len;
        } else if (roll < 15) {
            // Execute Order ('E')
            size_t msg_len = sizeof(OrderExecutedMsg);
            size_t required = add_2byte_length_prefix ? (msg_len + 2) : msg_len;
            if (offset + required > max_bytes) break;

            if (add_2byte_length_prefix) {
                *reinterpret_cast<uint16_t*>(&out_buffer[offset]) = be16(static_cast<uint16_t>(msg_len));
                offset += 2;
            }

            auto* m = reinterpret_cast<OrderExecutedMsg*>(&out_buffer[offset]);
            m->type = 'E';
            m->stock_locate = be16(1);
            m->tracking_number = be16(static_cast<uint16_t>(i));
            std::memcpy(m->timestamp, ts_bytes, 6);
            m->order_reference = be64(order_counter - 5);
            m->executed_shares = be32(50);
            m->match_number = be64(9999000 + i);
            offset += msg_len;
        } else if (roll < 18) {
            // Cancel Order ('X')
            size_t msg_len = sizeof(OrderCancelMsg);
            size_t required = add_2byte_length_prefix ? (msg_len + 2) : msg_len;
            if (offset + required > max_bytes) break;

            if (add_2byte_length_prefix) {
                *reinterpret_cast<uint16_t*>(&out_buffer[offset]) = be16(static_cast<uint16_t>(msg_len));
                offset += 2;
            }

            auto* m = reinterpret_cast<OrderCancelMsg*>(&out_buffer[offset]);
            m->type = 'X';
            m->stock_locate = be16(1);
            m->tracking_number = be16(static_cast<uint16_t>(i));
            std::memcpy(m->timestamp, ts_bytes, 6);
            m->order_reference = be64(order_counter - 3);
            m->canceled_shares = be32(20);
            offset += msg_len;
        } else if (roll == 18) {
            // Delete Order ('D')
            size_t msg_len = sizeof(OrderDeleteMsg);
            size_t required = add_2byte_length_prefix ? (msg_len + 2) : msg_len;
            if (offset + required > max_bytes) break;

            if (add_2byte_length_prefix) {
                *reinterpret_cast<uint16_t*>(&out_buffer[offset]) = be16(static_cast<uint16_t>(msg_len));
                offset += 2;
            }

            auto* m = reinterpret_cast<OrderDeleteMsg*>(&out_buffer[offset]);
            m->type = 'D';
            m->stock_locate = be16(1);
            m->tracking_number = be16(static_cast<uint16_t>(i));
            std::memcpy(m->timestamp, ts_bytes, 6);
            m->order_reference = be64(order_counter - 8);
            offset += msg_len;
        } else {
            // Non-cross Trade ('P')
            size_t msg_len = sizeof(TradeMsg);
            size_t required = add_2byte_length_prefix ? (msg_len + 2) : msg_len;
            if (offset + required > max_bytes) break;

            if (add_2byte_length_prefix) {
                *reinterpret_cast<uint16_t*>(&out_buffer[offset]) = be16(static_cast<uint16_t>(msg_len));
                offset += 2;
            }

            auto* m = reinterpret_cast<TradeMsg*>(&out_buffer[offset]);
            m->type = 'P';
            m->stock_locate = be16(1);
            m->tracking_number = be16(static_cast<uint16_t>(i));
            std::memcpy(m->timestamp, ts_bytes, 6);
            m->order_reference = be64(order_counter++);
            m->buy_sell_indicator = 'B';
            m->shares = be32(100);
            std::memcpy(m->stock, "NVDA    ", 8);
            m->price = be32(price_dist(rng));
            m->match_number = be64(8888000 + i);
            offset += msg_len;
        }
    }

    return offset;
}

ITCH_API void run_itch_benchmark(size_t num_messages, neuroquant::itch::ITCHParserStats* out_stats) {
    if (num_messages == 0 || !out_stats) return;

    // Allocate synthetic buffer: ~40 bytes per msg average
    size_t est_bytes = (num_messages * 45) + 4096;
    auto buffer = std::make_unique<uint8_t[]>(est_bytes);

    size_t actual_bytes = itch_generate_synthetic_stream(buffer.get(), est_bytes, num_messages, true);
    if (actual_bytes == 0) return;

    auto book = std::make_unique<neuroquant::itch::ITCHOrderBookCore>();

    // Warm-up cache lines on first 10,000 bytes
    itch_parse_stream(book.get(), buffer.get(), std::min(actual_bytes, size_t(50000)), true, nullptr);
    book->reset();

    // High-performance benchmark run
    itch_parse_stream(book.get(), buffer.get(), actual_bytes, true, out_stats);
}

} // extern "C"
