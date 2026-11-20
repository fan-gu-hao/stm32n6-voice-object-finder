(
set -euo pipefail

N6_ROOT="$HOME/STM32N6ai/course17_voice_object_finder"
N6_VISION="$N6_ROOT/vision"
N6_APP_REV="42f7d645f1ed61967a922defa4aa97b95d390b16"
N6_MODEL_REV="176ecaa749b79a3f53ce077d2b14412fa45e81a0"
N6_MODEL_NAME="yolov8n_256_quant_pc_ii_seg_coco-st.tflite"

if [ -e "$N6_ROOT" ]; then
    printf '目錄已存在，停止以免混入舊檔案：%s\n' "$N6_ROOT"
    exit 1
fi

mkdir -p "$N6_ROOT"

# 下載固定版本的官方完整原始碼。
git init -q "$N6_VISION"
git -C "$N6_VISION" remote add origin \
    https://github.com/STMicroelectronics/STM32N6-GettingStarted-InstanceSegmentation.git
git -C "$N6_VISION" fetch --depth 1 origin "$N6_APP_REV"
git -C "$N6_VISION" checkout -b object-finder FETCH_HEAD

# 另外下載官方提供的 YOLOv8n-seg 量化模型。
N6_MODEL="$N6_VISION/Model/$N6_MODEL_NAME"
N6_URL="https://raw.githubusercontent.com/stm32-hotspot/ultralytics/$N6_MODEL_REV/examples/YOLOv8-STEdgeAI/stedgeai_models/segmentation/$N6_MODEL_NAME"

curl --fail --location --retry 3 --connect-timeout 20 \
    "$N6_URL" --output "$N6_MODEL.part"

# 比對官方 Git 檔案雜湊，確認模型下載完整。
if [ "$(git hash-object "$N6_MODEL.part")" != "3e79bd242b1a4a3829839f66e55994a200c94e16" ]; then
    printf '模型下載內容不符，停止。\n'
    exit 1
fi
mv "$N6_MODEL.part" "$N6_MODEL"

printf 'application_commit=%s\nmodel_commit=%s\nmodel_url=%s\n' \
    "$N6_APP_REV" "$N6_MODEL_REV" "$N6_URL" > "$N6_ROOT/sources.txt"
sha256sum "$N6_MODEL" >> "$N6_ROOT/sources.txt"

printf '\n第 1 階段完成：官方原始碼與模型已下載。\n'
printf '專案根目錄：%s\n' "$N6_ROOT"
printf '主程式：%s\n' "$N6_VISION/Application/STM32N6570-DK/Src/main.c"
printf '模型：%s\n' "$N6_MODEL"
printf '模型大小：%s 位元組\n' "$(stat -c %s "$N6_MODEL")"
printf '\n目前 ST Edge AI 版本：\n'
if [ -x "$HOME/ST/STEdgeAI/4.0/Utilities/linux/stedgeai" ]; then
    "$HOME/ST/STEdgeAI/4.0/Utilities/linux/stedgeai" --version
else
    printf '預期位置找不到 ST Edge AI，下一步需指定安裝路徑。\n'
fi
)