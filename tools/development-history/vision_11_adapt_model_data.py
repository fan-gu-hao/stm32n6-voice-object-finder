from pathlib import Path
from datetime import datetime
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
path = root / "firmware/Src/app.c"
text = path.read_text(encoding="utf-8")
marker = "FINDER_YOLO_MODEL_DATA_V1"

if marker in text:
    print("這一步已完成，不需重複修改。")
    raise SystemExit(0)

old_headers = (
    '#include "stai_palm_detector.h"\n'
    '#include "stai_hand_landmark.h"'
)

type_start = "typedef struct {\n  uint32_t nn_in_len;"
type_end = "} hl_model_info_t;"
model_start = "/* model */"
model_end = " /* rtos */"

# 先確認官方原始碼的修改位置。
for anchor in (
    old_headers, type_start, type_end, model_start, model_end,
):
    if text.count(anchor) != 1:
        raise SystemExit(
            f"找不到唯一的修改位置，尚未寫入檔案：\n{anchor}"
        )

text = text.replace(
    old_headers,
    '#include "stai_network.h"\n'
    '#include "ll_aton_osal.h"\n'
    '#include <string.h>',
    1,
)

# 將原本兩種手部模型資料結構換成 YOLO 資料結構。
start = text.index(type_start)
end = text.index(type_end, start) + len(type_end)

model_type = """/* FINDER_YOLO_MODEL_DATA_V1 */
typedef struct {
  stai_network_info network_info;
  stai_ptr nn_in;
  stai_ptr nn_out[STAI_NETWORK_OUT_NUM];
  iseg_yolov8_pp_static_param_t static_param;
  iseg_pp_out_t output;
} yolo_model_info_t;"""

text = text[:start] + model_type + text[end:]

# 配置 YOLO 執行環境與兩個攝影機輸入緩衝區。
start = text.index(model_start)
end = text.index(model_end, start)

model_buffers = """/* model */
_Static_assert(STAI_NETWORK_IN_NUM == 1,
               "Expected one YOLO input");
_Static_assert(STAI_NETWORK_IN_1_WIDTH == 256 &&
               STAI_NETWORK_IN_1_HEIGHT == 256 &&
               STAI_NETWORK_IN_1_CHANNEL == 3 &&
               STAI_NETWORK_IN_1_FORMAT == STAI_FORMAT_U8,
               "Expected 256x256 RGB uint8 input");

static uint8_t network_ctx[STAI_NETWORK_CONTEXT_SIZE] ALIGN_32;
static yolo_model_info_t yolo_info;

static uint32_t frame_event_nb;
static volatile uint32_t frame_event_nb_for_resize;

/* 攝影機寫入影像，推論工作從佇列取得完成的影像。 */
static uint8_t nn_input_buffers[2][STAI_NETWORK_IN_1_SIZE_BYTES]
    ALIGN_32 IN_PSRAM;
static bqueue_t nn_input_queue;

"""

text = text[:start] + model_buffers + text[end:]

# 所有替換完成後才備份並寫入。
backup = root / "backups" / datetime.now().strftime(
    "app_model_data_%Y%m%d_%H%M%S_%f"
)
backup.mkdir(parents=True)
shutil.copy2(path, backup / path.name)
path.write_text(text, encoding="utf-8")

print("已修改：", path)
print("修改前備份：", backup)
print("\n完成項目：")
print("1. 引用 YOLO 模型標頭。")
print("2. 建立 YOLO 輸入、輸出與後處理資料結構。")
print("3. 建立 YOLO 執行環境。")
print("4. 將雙影像緩衝區大小對應到 YOLO 輸入。")
