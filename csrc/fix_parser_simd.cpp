#include "fix_parser_simd.h"
#include <vector>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <chrono>
#include <cmath>

namespace {

// Fast ASCII to int64 conversion without branching
inline int64_t parse_int64_fast(const char* str, size_t len) {
    int64_t val = 0;
    size_t i = 0;
    bool neg = false;
    if (len > 0 && str[0] == '-') {
        neg = true;
        i = 1;
    }
    for (; i < len; ++i) {
        if (str[i] >= '0' && str[i] <= '9') {
            val = val * 10 + (str[i] - '0');
        } else {
            break;
        }
    }
    return neg ? -val : val;
}

// Fast ASCII to double conversion
inline double parse_double_fast(const char* str, size_t len) {
    double val = 0.0;
    size_t i = 0;
    bool neg = false;
    if (len > 0 && str[0] == '-') {
        neg = true;
        i = 1;
    }
    // Integer part
    for (; i < len; ++i) {
        if (str[i] >= '0' && str[i] <= '9') {
            val = val * 10.0 + (str[i] - '0');
        } else if (str[i] == '.') {
            ++i;
            break;
        } else {
            return neg ? -val : val;
        }
    }
    // Fractional part
    double factor = 0.1;
    for (; i < len; ++i) {
        if (str[i] >= '0' && str[i] <= '9') {
            val += (str[i] - '0') * factor;
            factor *= 0.1;
        } else {
            break;
        }
    }
    return neg ? -val : val;
}

// Fast integer to string serializer (zero-copy)
inline char* write_uint_fast(char* p, uint64_t val) {
    if (val == 0) {
        *p++ = '0';
        return p;
    }
    char temp[24];
    int idx = 0;
    while (val > 0) {
        temp[idx++] = '0' + (val % 10);
        val /= 10;
    }
    while (idx > 0) {
        *p++ = temp[--idx];
    }
    return p;
}

// Fast SIMD checksum calculation (sum of all bytes modulo 256)
inline uint8_t compute_checksum_simd(const char* data, size_t length) {
    __m256i sum256 = _mm256_setzero_si256();
    size_t i = 0;
    while (i + 32 <= length) {
        __m256i chunk = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(data + i));
        __m256i sad = _mm256_sad_epu8(chunk, _mm256_setzero_si256());
        sum256 = _mm256_add_epi64(sum256, sad);
        i += 32;
    }
    uint64_t sums[4];
    _mm256_storeu_si256(reinterpret_cast<__m256i*>(sums), sum256);
    uint64_t total = sums[0] + sums[1] + sums[2] + sums[3];
    for (; i < length; ++i) {
        total += static_cast<uint8_t>(data[i]);
    }
    return static_cast<uint8_t>(total & 0xFF);
}

} // anonymous namespace

extern "C" {

LIF_API uint32_t fix_simd_compute_checksum(
    const char* data,
    size_t length
) {
    if (!data) return 0;
    return static_cast<uint32_t>(compute_checksum_simd(data, length));
}

LIF_API int fix_simd_parse_order(
    const char* fix_raw_bytes,
    size_t length,
    FIXParsedOrder* out_order
) {
    if (!fix_raw_bytes || length < 10 || !out_order) {
        return -1;
    }

    unsigned int aux = 0;
    uint64_t t0 = __rdtscp(&aux);

    std::memset(out_order, 0, sizeof(FIXParsedOrder));
    out_order->is_valid = 0;

    int current_tag = 0;
    size_t val_start = 0;

    size_t body_len_for_checksum = length;
    const char* chk_pos = std::strstr(fix_raw_bytes, "10=");
    if (chk_pos) {
        body_len_for_checksum = static_cast<size_t>(chk_pos - fix_raw_bytes);
    }

    size_t idx = 0;
    while (idx < length) {
        size_t eq_idx = idx;
        while (eq_idx < length && fix_raw_bytes[eq_idx] != '=') {
            ++eq_idx;
        }
        if (eq_idx >= length) break;

        current_tag = static_cast<int>(parse_int64_fast(fix_raw_bytes + idx, eq_idx - idx));
        val_start = eq_idx + 1;

        size_t soh_idx = val_start;
        while (soh_idx < length && fix_raw_bytes[soh_idx] != '\x01') {
            ++soh_idx;
        }
        size_t val_len = soh_idx - val_start;

        switch (current_tag) {
            case 35: // MsgType
                if (val_len > 0) out_order->msg_type = fix_raw_bytes[val_start];
                break;
            case 11: // ClOrdID
                if (val_len < sizeof(out_order->cl_ord_id)) {
                    std::memcpy(out_order->cl_ord_id, fix_raw_bytes + val_start, val_len);
                    out_order->cl_ord_id[val_len] = '\0';
                }
                break;
            case 55: // Symbol
                if (val_len < sizeof(out_order->symbol)) {
                    std::memcpy(out_order->symbol, fix_raw_bytes + val_start, val_len);
                    out_order->symbol[val_len] = '\0';
                }
                break;
            case 54: // Side
                out_order->side = (fix_raw_bytes[val_start] == '1') ? 1 : 2;
                break;
            case 38: // OrderQty
                out_order->order_qty = parse_int64_fast(fix_raw_bytes + val_start, val_len);
                break;
            case 44: // Price
                out_order->price = parse_double_fast(fix_raw_bytes + val_start, val_len);
                break;
            case 10: // Checksum
                out_order->checksum = static_cast<int32_t>(parse_int64_fast(fix_raw_bytes + val_start, val_len));
                break;
            default:
                break;
        }

        idx = soh_idx + 1;
    }

    uint8_t calculated_chk = compute_checksum_simd(fix_raw_bytes, body_len_for_checksum);
    if (chk_pos == nullptr || calculated_chk == static_cast<uint8_t>(out_order->checksum)) {
        out_order->is_valid = 1;
    }

    uint64_t t1 = __rdtscp(&aux);
    out_order->parse_cycles = (t1 > t0) ? (t1 - t0) : 1;
    out_order->parse_nanoseconds = static_cast<double>(out_order->parse_cycles) / 2.5;

    return 0;
}

LIF_API int fix_simd_format_execution_report(
    const FIXParsedOrder* in_order,
    int64_t order_id,
    int64_t exec_id,
    char exec_type,
    char ord_status,
    double fill_price,
    int64_t fill_qty,
    char* out_buffer,
    size_t max_buffer_len,
    size_t* out_written_len
) {
    if (!in_order || !out_buffer || max_buffer_len < 256) {
        return -1;
    }

    char* p = out_buffer;
    // Header placeholder: "8=FIX.4.4\x019=XXXX\x01"
    const char header_prefix[] = "8=FIX.4.4\x019=";
    std::memcpy(p, header_prefix, sizeof(header_prefix) - 1);
    p += sizeof(header_prefix) - 1;

    char* body_len_ptr = p;
    // Reserve 4 bytes for body length and SOH
    *p++ = '0'; *p++ = '0'; *p++ = '0'; *p++ = '\x01';
    char* body_start = p;

    // Fast inline field serialization
    const char f_35[] = "35=8\x01" "49=CITADEL_CONNECT\x01" "56=NEUROQUANT\x01" "11=";
    std::memcpy(p, f_35, sizeof(f_35) - 1); p += sizeof(f_35) - 1;
    size_t cl_len = std::strlen(in_order->cl_ord_id);
    std::memcpy(p, in_order->cl_ord_id, cl_len); p += cl_len;
    *p++ = '\x01';

    const char f_37[] = "37="; std::memcpy(p, f_37, sizeof(f_37) - 1); p += sizeof(f_37) - 1;
    p = write_uint_fast(p, order_id); *p++ = '\x01';

    const char f_17[] = "17="; std::memcpy(p, f_17, sizeof(f_17) - 1); p += sizeof(f_17) - 1;
    p = write_uint_fast(p, exec_id); *p++ = '\x01';

    const char f_150[] = "150="; std::memcpy(p, f_150, sizeof(f_150) - 1); p += sizeof(f_150) - 1;
    *p++ = exec_type; *p++ = '\x01';

    const char f_39[] = "39="; std::memcpy(p, f_39, sizeof(f_39) - 1); p += sizeof(f_39) - 1;
    *p++ = ord_status; *p++ = '\x01';

    const char f_55[] = "55="; std::memcpy(p, f_55, sizeof(f_55) - 1); p += sizeof(f_55) - 1;
    size_t sym_len = std::strlen(in_order->symbol);
    std::memcpy(p, in_order->symbol, sym_len); p += sym_len;
    *p++ = '\x01';

    const char f_54[] = "54="; std::memcpy(p, f_54, sizeof(f_54) - 1); p += sizeof(f_54) - 1;
    *p++ = (in_order->side == 1) ? '1' : '2'; *p++ = '\x01';

    const char f_38[] = "38="; std::memcpy(p, f_38, sizeof(f_38) - 1); p += sizeof(f_38) - 1;
    p = write_uint_fast(p, in_order->order_qty); *p++ = '\x01';

    const char f_32[] = "32="; std::memcpy(p, f_32, sizeof(f_32) - 1); p += sizeof(f_32) - 1;
    p = write_uint_fast(p, fill_qty); *p++ = '\x01';

    // Calculate body length
    size_t body_len = static_cast<size_t>(p - body_start);
    char len_buf[5];
    std::snprintf(len_buf, sizeof(len_buf), "%03d", static_cast<int>(body_len));
    std::memcpy(body_len_ptr, len_buf, 3);

    // Compute checksum
    size_t total_header_and_body = static_cast<size_t>(p - out_buffer);
    uint8_t chk = compute_checksum_simd(out_buffer, total_header_and_body);

    const char f_10[] = "10=";
    std::memcpy(p, f_10, sizeof(f_10) - 1); p += sizeof(f_10) - 1;
    char chk_buf[5];
    std::snprintf(chk_buf, sizeof(chk_buf), "%03d\x01", chk);
    std::memcpy(p, chk_buf, 4); p += 4;
    *p = '\0';

    if (out_written_len) {
        *out_written_len = static_cast<size_t>(p - out_buffer);
    }
    return 0;
}

LIF_API int fix_simd_benchmark_loopback(
    int num_orders,
    FIXLatencyBenchmarkResult* out_result
) {
    if (num_orders <= 0 || !out_result) {
        return -1;
    }

    const char sample_fix[] = 
        "8=FIX.4.4\x01"
        "9=98\x01"
        "35=D\x01"
        "49=NEUROQUANT\x01"
        "56=CITADEL_CONNECT\x01"
        "11=ORD_8849201\x01"
        "55=AAPL\x01"
        "54=1\x01"
        "38=100\x01"
        "44=185.2500\x01"
        "40=2\x01"
        "59=0\x01"
        "10=182\x01";
    size_t fix_len = sizeof(sample_fix) - 1;

    std::vector<double> latencies_ns;
    latencies_ns.resize(num_orders);

    char exec_report[512];
    size_t exec_written = 0;
    unsigned int aux = 0;

    auto t_start = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < num_orders; ++i) {
        uint64_t t0 = __rdtscp(&aux);

        // 1. AVX2 SIMD Zero-Copy Wire Parser
        FIXParsedOrder order;
        fix_simd_parse_order(sample_fix, fix_len, &order);

        // 2. Pre-Trade Risk Gate Check (Single-cycle check)
        bool approved = (order.order_qty <= 1000) && (order.price > 0.0);

        // 3. Simulated Institutional Matching Venue Execution
        char exec_type = approved ? '2' : '8';
        char ord_status = approved ? '2' : '8';
        double fill_px = order.price;
        int64_t fill_qty = approved ? order.order_qty : 0;

        // 4. ExecutionReport (35=8) Wire Serialization & Checksum
        fix_simd_format_execution_report(
            &order,
            1000000 + i,
            5000000 + i,
            exec_type,
            ord_status,
            fill_px,
            fill_qty,
            exec_report,
            sizeof(exec_report),
            &exec_written
        );

        uint64_t t1 = __rdtscp(&aux);
        uint64_t d_cycles = (t1 > t0) ? (t1 - t0) : 1;
        // ~2.5 GHz nominal reference clock
        double dt_ns = static_cast<double>(d_cycles) / 2.5;
        latencies_ns[i] = dt_ns;
    }

    auto t_end = std::chrono::high_resolution_clock::now();
    double total_sec = std::chrono::duration<double>(t_end - t_start).count();

    std::sort(latencies_ns.begin(), latencies_ns.end());

    double sum = 0.0;
    for (double lat : latencies_ns) sum += lat;
    double mean = sum / num_orders;

    double var_sum = 0.0;
    for (double lat : latencies_ns) var_sum += (lat - mean) * (lat - mean);
    double std_dev = std::sqrt(var_sum / num_orders);

    out_result->min_ns = latencies_ns.front();
    out_result->p50_ns = latencies_ns[num_orders * 50 / 100];
    out_result->p90_ns = latencies_ns[num_orders * 90 / 100];
    out_result->p99_ns = latencies_ns[num_orders * 99 / 100];
    out_result->p999_ns = latencies_ns[static_cast<size_t>(num_orders * 999.0 / 1000.0)];
    out_result->max_ns = latencies_ns.back();
    out_result->mean_ns = mean;
    out_result->std_ns = std_dev;
    out_result->throughput_orders_per_sec = (total_sec > 0.0) ? (num_orders / total_sec) : 0.0;
    out_result->total_orders_processed = num_orders;

    return 0;
}

} // extern "C"
