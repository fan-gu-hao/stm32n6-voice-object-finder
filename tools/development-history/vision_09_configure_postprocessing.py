from pathlib import Path
from datetime import datetime
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
path = root / "firmware/Inc/postprocess_conf.h"

text = path.read_text(encoding="utf-8")
anchor = "#ifndef __POSTPROCESS_CONF_H__"

if text.count(anchor) != 1:
    raise SystemExit("檔案結構與預期不同，尚未修改。")

if not any(name in text for name in (
    "POSTPROCESS_MPE_PD_UF",
    "POSTPROCESS_ISEG_YOLO_V8_UI",
)):
    raise SystemExit("找不到預期的後處理設定，尚未修改。")

# 保留檔案開頭的官方版權聲明。
prefix = text.split(anchor, 1)[0]

config = """#ifndef __POSTPROCESS_CONF_H__
#define __POSTPROCESS_CONF_H__

#include "arm_math.h"

/* 使用官方 YOLOv8 實例分割後處理。 */
#define POSTPROCESS_TYPE POSTPROCESS_ISEG_YOLO_V8_UI

/* 配合目前的 256x256、COCO 80 類模型。 */
#define NB_CLASSES                          (80)
#define AI_YOLOV8_SEG_PP_TOTAL_BOXES         (1344)
#define AI_YOLOV8_SEG_PP_NB_CLASSES          (NB_CLASSES)
#define AI_YOLOV8_SEG_PP_MASK_NB              (32)
#define AI_YOLOV8_SEG_PP_MASK_SIZE            (64)

/* 結果篩選設定。 */
#define AI_YOLOV8_SEG_PP_CONF_THRESHOLD       (0.50f)
#define AI_YOLOV8_SEG_PP_IOU_THRESHOLD        (0.40f)
#define AI_YOLOV8_SEG_PP_MAX_BOXES_LIMIT      (10)

#endif /* __POSTPROCESS_CONF_H__ */
"""

updated = prefix + config

if text == updated:
    print("設定已相同，不需重複修改。")
else:
    backup = root / "backups" / datetime.now().strftime(
        "postprocess_config_%Y%m%d_%H%M%S_%f"
    )
    backup.mkdir(parents=True)
    shutil.copy2(path, backup / path.name)
    path.write_text(updated, encoding="utf-8")
    print("已修改：", path)
    print("修改前備份：", backup)

print("\n目前後處理設定：")
for line in updated.splitlines():
    if line.startswith((
        "#define POSTPROCESS_TYPE",
        "#define NB_CLASSES",
        "#define AI_YOLOV8_SEG_PP_",
    )):
        print(line)

print("\n完成：YOLO 後處理參數已設定。")
