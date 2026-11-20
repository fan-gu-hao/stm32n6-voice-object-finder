(
set -euo pipefail
shopt -s nullglob

N6_ROOT="$HOME/STM32N6ai/course17_voice_object_finder"
N6_IDE="/opt/st/stm32cubeide_2.2.0"

test -s "$N6_ROOT/output/finder_voice_current.txt"
N6_OUT="$(cat "$N6_ROOT/output/finder_voice_current.txt")"

N6_CLIS=(
  "$N6_IDE"/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.linux64_*/tools/bin/STM32_Programmer_CLI
)

if [ "${#N6_CLIS[@]}" -ne 1 ]; then
    printf 'CubeProgrammer 工具數量不是 1。\n'
    exit 1
fi

N6_CLI="${N6_CLIS[0]}"
N6_TOOL_DIR="$(dirname "$N6_CLI")"
N6_SIGNER="$N6_TOOL_DIR/STM32_SigningTool_CLI"
N6_LOADER="$N6_TOOL_DIR/ExternalLoader/MX66UW1G45G_STM32N6570-DK.stldr"

test -x "$N6_SIGNER"
test -s "$N6_LOADER"
test -s "$N6_OUT/finder.bin"
test -s "$N6_OUT/finder_signed.bin"

N6_STAMP="$(date +%Y%m%d_%H%M%S_%N)"
N6_FIXED="$N6_OUT/finder_signed_aligned_$N6_STAMP.bin"

# 加上必要的對齊參數，重新產生開機映像。
"$N6_SIGNER" \
    -bin "$N6_OUT/finder.bin" \
    -nk -of 0x80000000 \
    -t ssbl -hv 2.3 -align \
    -o "$N6_FIXED"

# 確認程式確實從 0x400 開始，且內容完全一致。
python3 - "$N6_OUT/finder.bin" "$N6_FIXED" <<'PY'
from pathlib import Path
import sys

raw = Path(sys.argv[1]).read_bytes()
image = Path(sys.argv[2]).read_bytes()
offset = image.find(raw[:64])

if offset != 0x400:
    raise SystemExit(f"對齊檢查失敗：偏移為 {offset:#x}，尚未燒錄。")

if image[0x400:0x400 + len(raw)] != raw:
    raise SystemExit("程式內容檢查失敗，尚未燒錄。")

print("檢查通過：程式起始偏移為 0x400。")
print("檢查通過：程式內容與原始編譯結果完全一致。")
PY

# 保留舊映像，再替換成修正版。
cp -p "$N6_OUT/finder_signed.bin" \
    "$N6_OUT/finder_signed_before_align_$N6_STAMP.bin"

mv "$N6_FIXED" "$N6_OUT/finder_signed.bin"

# 本次只更新主程式區域。
"$N6_CLI" \
    -c port=SWD mode=HOTPLUG ap=1 freq=1000 \
    "sn=${N6_PROBE_SERIAL}" \
    -el "$N6_LOADER" \
    -hardRst \
    -w "$N6_OUT/finder_signed.bin" 0x70100000 \
    -v \
    2>&1 | tee "$N6_OUT/flash_align_fix_$N6_STAMP.log"

printf '\n修正版燒錄完成。請斷電，將 BOOT0、BOOT1 都切到 L，再上電。\n'
)