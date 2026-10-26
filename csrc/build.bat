@echo off
set "PATH=C:\msys64\ucrt64\bin;%PATH%"
g++ -std=c++20 -O3 -mavx2 -mfma -shared -static -static-libgcc -static-libstdc++ -fPIC -DLIF_EXPORTS -o csrc\lif_core.dll csrc\lif_core.cpp csrc\itch_parser.cpp csrc\almgren_chriss_simd.cpp csrc\ofi_calibrator_simd.cpp csrc\fix_parser_simd.cpp -Wl,--out-implib,csrc\liblif_core.a
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] csrc\lif_core.dll built successfully!
) else (
    echo [FAILED] Compilation failed with error code %ERRORLEVEL%
)
