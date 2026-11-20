(
set -euo pipefail

N6_ROOT="$HOME/STM32N6ai/course17_voice_object_finder"
N6_SOURCE="$N6_ROOT/vision/Model/STM32N6570-DK"
N6_DEST="$N6_ROOT/firmware/Model"

N6_FILES=(
    network.c
    network.h
    network_ecblobs.h
    stai_network.c
    stai_network.h
    network_data.xSPI2.bin
)

# 先確認來源完整，以及目的地沒有同名檔案。
for N6_FILE in "${N6_FILES[@]}"; do
    if [ ! -s "$N6_SOURCE/$N6_FILE" ]; then
        printf '找不到來源檔案：%s\n' "$N6_SOURCE/$N6_FILE"
        exit 1
    fi

    if [ -e "$N6_DEST/$N6_FILE" ]; then
        printf '目的地已有檔案，先停止以免覆蓋：%s\n' "$N6_DEST/$N6_FILE"
        exit 1
    fi
done

# 將六個檔案複製進官方主工程。
for N6_FILE in "${N6_FILES[@]}"; do
    cp -v "$N6_SOURCE/$N6_FILE" "$N6_DEST/"
done

printf '\n完成：YOLO 程式碼與權重已放進官方主工程。\n'
)