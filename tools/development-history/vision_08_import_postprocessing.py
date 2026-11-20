from pathlib import Path
from datetime import datetime
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
vision = root / "vision"
firmware = root / "firmware"
makefile = firmware / "mks/ai.mk"

directories = [
    (
        vision / "Middlewares/stm32-vision-models-postprocessing",
        firmware / "Lib/lib_vision_models_pp",
    ),
    (
        vision / "Middlewares/ai-postprocessing-wrapper",
        firmware / "Lib/ai-postprocessing-wrapper",
    ),
]

for source, target in directories:
    if not source.is_dir():
        raise SystemExit(f"找不到來源目錄：{source}")
    if not target.is_dir():
        raise SystemExit(f"找不到主工程目錄：{target}")

# 更新後處理的編譯清單，保留其他設定。
text = makefile.read_text(encoding="utf-8")

changes = {
    "C_SOURCES_AI += $(PP_REL_DIR)/Src/pd_pp_model.c":
    "C_SOURCES_AI += $(wildcard $(PP_REL_DIR)/Src/*.c)",

    "C_SOURCES_AI += $(wildcard $(PPW_REL_DIR)/*.c)":
    "C_SOURCES_AI += $(PPW_REL_DIR)/app_postprocess_iseg_yolo_v8_ui.c",
}

for old, new in changes.items():
    if text.count(old) == 1:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit(f"找不到預期的編譯設定：{old}")

# 備份設定與舊函式庫。
backup = root / "backups" / datetime.now().strftime(
    "postprocess_%Y%m%d_%H%M%S_%f"
)
backup.mkdir(parents=True)
shutil.copy2(makefile, backup / "ai.mk")

for source, target in directories:
    shutil.move(str(target), str(backup / target.name))
    shutil.copytree(source, target)
    print("已更新：", target.relative_to(firmware), flush=True)

makefile.write_text(text, encoding="utf-8")

print("\n目前後處理的編譯清單：")
for line in text.splitlines():
    if line.startswith("C_SOURCES_AI") and (
        "$(PP_REL_DIR)" in line or "$(PPW_REL_DIR)" in line
    ):
        print(line)

print("\n修改前備份：", backup)
print("完成：官方分割後處理程式已準備好。")
