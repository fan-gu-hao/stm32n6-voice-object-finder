(
set -euo pipefail
shopt -s nullglob

N6_ROOT="$HOME/STM32N6ai/course17_voice_object_finder"
N6_VISION="$N6_ROOT/vision"
N6_APP="$N6_VISION/Application/STM32N6570-DK"
N6_IDE="/opt/st/stm32cubeide_2.2.0"
N6_AI="$HOME/ST/STEdgeAI/4.0/Utilities/linux/stedgeai"

N6_GCCS=(
  "$N6_IDE"/plugins/com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.*/tools/bin/arm-none-eabi-gcc
)
N6_SIGNERS=(
  "$N6_IDE"/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.linux64_*/tools/bin/STM32_SigningTool_CLI
)

if [ "${#N6_GCCS[@]}" -ne 1 ] || [ "${#N6_SIGNERS[@]}" -ne 1 ]; then
    printf '編譯器或簽章工具數量不是 1，請貼上結果：\n'
    printf '%s\n' "${N6_GCCS[@]}" "${N6_SIGNERS[@]}"
    exit 1
fi

test -x "$N6_AI"
N6_GCC_DIR="$(dirname "${N6_GCCS[0]}")"
export PATH="$(dirname "$N6_AI"):$N6_GCC_DIR:$PATH"

N6_STAMP="$(date +%Y%m%d_%H%M%S)"
N6_OUT="$N6_ROOT/output/vision_$N6_STAMP"
mkdir -p "$N6_OUT"
printf '本次產物與日誌：%s\n' "$N6_OUT"

# 用官方腳本產生模型程式碼。
cd "$N6_VISION/Model"
if ! bash generate-n6-model_STM32N6570-DK.sh > "$N6_OUT/generate.log" 2>&1; then
    tail -n 80 "$N6_OUT/generate.log"
    exit 1
fi

if [ -f st_ai_output/network.h ]; then
    cp st_ai_output/network.h STM32N6570-DK/
fi
printf '模型程式碼產生完成。\n'

# 建置 ELF，接著分別匯出主程式與 NPU 命令區段。
N6_REL="build_finder/Application/STM32N6570-DK/Project"

if ! make -C "$N6_APP" -j"$(nproc)" \
    "GCC_PATH=$N6_GCC_DIR" BUILD_TOP=build_finder \
    "$N6_REL.elf" > "$N6_OUT/build.log" 2>&1; then
    tail -n 80 "$N6_OUT/build.log"
    exit 1
fi
tail -n 15 "$N6_OUT/build.log"

N6_ELF="$N6_APP/$N6_REL.elf"

"$N6_GCC_DIR/arm-none-eabi-objcopy" -O binary \
    --remove-section=.flash_section \
    "$N6_ELF" "$N6_OUT/vision.bin"

"$N6_GCC_DIR/arm-none-eabi-objcopy" -O binary \
    --only-section=.flash_section \
    "$N6_ELF" "$N6_OUT/vision_commands.bin"

cp "$N6_VISION/Model/STM32N6570-DK/network_data.xSPI2.bin" \
    "$N6_OUT/vision_weights.bin"
cp "$N6_VISION/FSBL/ai_fsbl.hex" "$N6_OUT/ai_fsbl.hex"
cp "$N6_ELF" "$N6_OUT/Project.elf"
cp "$N6_APP/$N6_REL.map" "$N6_OUT/Project.map"

# 加上開機所需的映像標頭，並套用新版工具的對齊選項。
"${N6_SIGNERS[0]}" -bin "$N6_OUT/vision.bin" \
    -nk -of 0x80000000 -t ssbl -hv 2.3 --align \
    -o "$N6_OUT/vision_signed.bin"

test -s "$N6_OUT/vision_signed.bin"
test -s "$N6_OUT/vision_commands.bin"
test -s "$N6_OUT/vision_weights.bin"

printf '\n產碼、編譯與開機映像準備完成：%s\n' "$N6_OUT"
ls -lh "$N6_OUT/vision_signed.bin" "$N6_OUT/vision_commands.bin" \
    "$N6_OUT/vision_weights.bin" "$N6_OUT/ai_fsbl.hex"
)