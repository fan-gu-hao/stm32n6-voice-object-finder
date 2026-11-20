from pathlib import Path
from datetime import datetime
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
path = root / "firmware/Makefile"
text = path.read_text(encoding="utf-8")

old = """C_SOURCES += Model/palm_detector.c
C_SOURCES += Model/hand_landmark.c
C_SOURCES += Model/stai_palm_detector.c
C_SOURCES += Model/stai_hand_landmark.c
"""

new = """C_SOURCES += Model/network.c
C_SOURCES += Model/stai_network.c
"""

helper = "C_SOURCES += Src/ld.c\n"

if text.count(old) == 1 and new not in text and text.count(helper) == 1:
    backup = root / "backups" / datetime.now().strftime(
        "model_sources_%Y%m%d_%H%M%S_%f"
    )
    backup.mkdir(parents=True)
    shutil.copy2(path, backup / "Makefile")

    text = text.replace(old, new, 1)
    text = text.replace(helper, "", 1)
    path.write_text(text, encoding="utf-8")

    print("已修改：", path)
    print("修改前備份：", backup / "Makefile")

elif text.count(new) == 1 and old not in text and helper not in text:
    print("模型編譯清單已更新，保留現有設定。")

else:
    raise SystemExit("Makefile 內容與預期不同，尚未修改。")

print("\n目前列入編譯的模型程式：")
for line in text.splitlines():
    if line.startswith("C_SOURCES += Model/"):
        print(line)
