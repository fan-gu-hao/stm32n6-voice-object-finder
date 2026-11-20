from pathlib import Path
from datetime import datetime
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
path = root / "firmware/Src/main.c"
header = root / "firmware/Model/stai_network.h"

if not header.is_file():
    raise SystemExit(f"找不到 YOLO 模型標頭：{header}")

if "STAI_NETWORK_ORIGIN_MODEL_NAME" not in header.read_text(encoding="utf-8"):
    raise SystemExit("模型標頭缺少預期的名稱定義，尚未修改。")

original = path.read_text(encoding="utf-8")
updated = original

changes = [
    (
        '#include "stai_palm_detector.h"\n'
        '#include "stai_hand_landmark.h"',
        '#include "stai_network.h"',
    ),
    (
        r'''  printf("Palm detection model: %s\n", STAI_PALM_DETECTOR_ORIGIN_MODEL_NAME);
  printf("Hand landmarks model: %s\n", STAI_HAND_LANDMARK_ORIGIN_MODEL_NAME);''',
        r'''  printf("Vision model: %s\n", STAI_NETWORK_ORIGIN_MODEL_NAME);''',
    ),
]

# 先確認所有修改位置，再寫入檔案。
for old, new in changes:
    if updated.count(old) == 1 and new not in updated:
        updated = updated.replace(old, new, 1)
    elif old not in updated and updated.count(new) == 1:
        continue
    else:
        raise SystemExit(
            "main.c 的內容與預期不同，尚未寫入修改。\n"
            f"請檢查這個位置：\n{old}"
        )

if updated == original:
    print("main.c 已完成相同修改，不需重複寫入。")
else:
    backup = root / "backups" / datetime.now().strftime(
        "main_model_%Y%m%d_%H%M%S_%f"
    )
    backup.mkdir(parents=True)
    shutil.copy2(path, backup / path.name)
    path.write_text(updated, encoding="utf-8")
    print("已修改：", path)
    print("修改前備份：", backup)

print("\n目前模型引用與開機訊息：")
for line in updated.splitlines():
    if '#include "stai_' in line or 'printf("Vision model:' in line:
        print(line)

print("\n完成：main.c 已改用 YOLO 模型標頭與名稱。")
