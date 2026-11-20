(
set -euo pipefail
shopt -s nullglob

N6_IDE="/opt/st/stm32cubeide_2.2.0"
N6_OUT="$HOME/STM32N6ai/course17_voice_object_finder/output/finder_voice_20261006_232124_054291"
N6_FIXED="$N6_OUT/finder_signed_aligned_20261006_234316_108456445.bin"

N6_CLIS=(
  "$N6_IDE"/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.linux64_*/tools/bin/STM32_Programmer_CLI
)

if [ "${#N6_CLIS[@]}" -ne 1 ]; then
    printf 'CubeProgrammer 工具數量不是 1。\n'
    exit 1
fi

N6_CLI="${N6_CLIS[0]}"
N6_LOADER="$(dirname "$N6_CLI")/ExternalLoader/MX66UW1G45G_STM32N6570-DK.stldr"
test -s "$N6_LOADER"

# 如果上次已經完成移動，就檢查正式檔案。
if [ ! -s "$N6_FIXED" ]; then
    N6_FIXED="$N6_OUT/finder_signed.bin"
fi

python3 - "$N6_OUT/finder.bin" "$N6_FIXED" <<'PY'
from pathlib import Path
import sys

raw = Path(sys.argv[1]).read_bytes()
image = Path(sys.argv[2]).read_bytes()

if not raw or image.find(raw[:64]) != 0x400:
    raise SystemExit("程式偏移不是 0x400，停止燒錄。")

if image[0x400:0x400 + len(raw)] != raw:
    raise SystemExit("程式內容不一致，停止燒錄。")

print("確認通過：偏移 0x400，程式內容一致。")
PY

# 上一段已備份舊映像；明確取代唯讀的正式檔案。
if [ "$N6_FIXED" != "$N6_OUT/finder_signed.bin" ]; then
    command mv -f -- "$N6_FIXED" "$N6_OUT/finder_signed.bin"
fi

"$N6_CLI" \
    -c port=SWD mode=HOTPLUG ap=1 freq=1000 \
    "sn=${N6_PROBE_SERIAL}" \
    -el "$N6_LOADER" \
    -hardRst \
    -w "$N6_OUT/finder_signed.bin" 0x70100000 \
    -v \
    2>&1 | tee "$N6_OUT/flash_align_retry_$(date +%Y%m%d_%H%M%S).log"

printf '\n燒錄完成。請斷電，BOOT0、BOOT1 都切到 L，再重新上電。\n'
)