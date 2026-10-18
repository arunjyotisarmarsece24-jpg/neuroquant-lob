@echo off
set "PATH=C:\msys64\ucrt64\bin;%PATH%"
echo Starting C++20 AVX2 Vectorized Neuromorphic Core and NASDAQ ITCH 5.0 Compilation...
g++ -std=c++20 -O3 -mavx2 -mfma -shared -static -static-libgcc -static-libstdc++ -fPIC -DLIF_EXPORTS -o csrc\lif_core.dll csrc\lif_core.cpp csrc\itch_parser.cpp -Wl,--out-implib,csrc\liblif_core.a
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] csrc\lif_core.dll built successfully!
) else (
    echo [FAILED] Compilation failed with error code %ERRORLEVEL%
)
