(
set -euo pipefail

N6_ROOT="$HOME/STM32N6ai/course17_voice_object_finder"
N6_APP="$N6_ROOT/firmware"
N6_REV="6c313001f69d3ddb1ffa7bd700aba74f9c11037b"
N6_MODEL="yolov8n_256_quant_pc_ii_seg_coco-st.tflite"

test -s "$N6_ROOT/vision/Model/$N6_MODEL"

if [ -e "$N6_APP" ]; then
    printf '主工程目錄已存在，停止以免覆蓋：%s\n' "$N6_APP"
    exit 1
fi

git init -q "$N6_APP"
git -C "$N6_APP" remote add origin \
    https://github.com/STMicroelectronics/x-cube-n6-ai-hand-landmarks.git
git -C "$N6_APP" fetch --depth 1 origin "$N6_REV"
git -C "$N6_APP" checkout -b voice-object-finder FETCH_HEAD

# 將剛下載的 YOLO 模型放進正式主工程，供後續產碼使用。
cp "$N6_ROOT/vision/Model/$N6_MODEL" "$N6_APP/Model/$N6_MODEL"

printf '\n正式主工程：%s\n' "$N6_APP"
printf '官方基準版本：\n'
git -C "$N6_APP" log -1 --format='%h %s'

printf '\n主程式與應用流程：\n'
ls -lh "$N6_APP/Src/main.c" "$N6_APP/Src/app.c"

printf '\nYOLO 模型已放入：%s\n' "$N6_APP/Model/$N6_MODEL"
)