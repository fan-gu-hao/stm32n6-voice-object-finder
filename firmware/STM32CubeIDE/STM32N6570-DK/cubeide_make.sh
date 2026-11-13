#!/usr/bin/env bash
set -euo pipefail

ide_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
fw_dir="$(cd -- "$ide_dir/../.." && pwd)"

if [[ -z "${GCC_PATH:-}" ]] && ! {
    command -v arm-none-eabi-gcc >/dev/null &&
    [[ "$(arm-none-eabi-gcc -dumpfullversion)" == "14.3.1" ]]
}; then
    for n6_dir in /opt/st/stm32cubeide_*/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin; do
        [[ -x "$n6_dir/arm-none-eabi-gcc" ]] || continue
        [[ "$("$n6_dir/arm-none-eabi-gcc" -dumpfullversion)" == "14.3.1" ]] || continue
        export GCC_PATH="$n6_dir"
        break
    done
fi

if [[ -n "${GCC_PATH:-}" ]]; then
    [[ -x "$GCC_PATH/arm-none-eabi-gcc" ]] || {
        echo "GCC_PATH 不是有效的編譯器目錄。" >&2
        exit 2
    }
    export PATH="$GCC_PATH:$PATH"
fi

command -v arm-none-eabi-gcc >/dev/null || {
    echo "請用 GCC_PATH 指定 GCC 14.3.1 的 bin 目錄。" >&2
    exit 2
}

[[ "$(arm-none-eabi-gcc -dumpfullversion)" == "14.3.1" ]] || {
    echo "此版本使用 GCC 14.3.1，請調整 GCC_PATH。" >&2
    exit 2
}

exec /usr/bin/make -C "$fw_dir" \
    -j"${N6_BUILD_JOBS:-8}" \
    BUILD_DIR=build_finder_ide V=1 "$@"
