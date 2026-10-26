#pragma once

#include <cstdint>
#include <cstddef>
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

#pragma pack(push, 8)
struct FIXParsedOrder {
    char msg_type;          // Tag 35 (e.g. 'D')
    char cl_ord_id[32];     // Tag 11
    char symbol[16];        // Tag 55 (e.g. "AAPL")
    int32_t side;           // Tag 54 (1 = Buy, 2 = Sell)
    int64_t order_qty;      // Tag 38
    double price;           // Tag 44
    int32_t checksum;       // Tag 10
    int32_t is_valid;       // 1 if checksum & required tags valid, 0 otherwise
    uint64_t parse_cycles;  // RDTSCP parsing clock cycles
    double parse_nanoseconds; // RDTSCP / clock freq
};

struct FIXLatencyBenchmarkResult {
    double min_ns;
    double p50_ns;
    double p90_ns;
    double p99_ns;
    double p999_ns;
    double max_ns;
    double mean_ns;
    double std_ns;
    double throughput_orders_per_sec;
    int64_t total_orders_processed;
};
#pragma pack(pop)

extern "C" {

LIF_API int fix_simd_parse_order(
    const char* fix_raw_bytes,
    size_t length,
    FIXParsedOrder* out_order
);

LIF_API int fix_simd_benchmark_loopback(
    int num_orders,
    FIXLatencyBenchmarkResult* out_result
);

LIF_API uint32_t fix_simd_compute_checksum(
    const char* data,
    size_t length
);

LIF_API int fix_simd_format_execution_report(
    const FIXParsedOrder* in_order,
    int64_t order_id,
    int64_t exec_id,
    char exec_type,      // '0' = New, '1' = Partial, '2' = Fill, '8' = Rejected
    char ord_status,
    double fill_price,
    int64_t fill_qty,
    char* out_buffer,
    size_t max_buffer_len,
    size_t* out_written_len
);

}
