from pathlib import Path
from datetime import datetime
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
source = root / "vision/Middlewares/stedgeai-lib"
target = root / "firmware/Lib/AI_Runtime"
makefile = root / "firmware/mks/ai.mk"

old_library = "NetworkRuntime1100_CM55_GCC.a"
new_library = "NetworkRuntime1201_CM55_GCC.a"

# 先確認要複製的執行期與函式庫存在。
for name in ("Inc", "Lib", "Npu"):
    if not (source / name).is_dir():
        raise SystemExit(f"找不到來源目錄：{source / name}")
    if not (target / name).is_dir():
        raise SystemExit(f"找不到官方工程目錄：{target / name}")

library = source / "Lib/GCC/ARMCortexM55" / new_library
if not library.is_file():
    raise SystemExit(f"找不到函式庫：{library}")

text = makefile.read_text(encoding="utf-8")
if old_library not in text and new_library not in text:
    raise SystemExit("ai.mk 的函式庫設定與預期不同，尚未修改。")

# 保留原始編譯設定及三個舊目錄。
backup = root / "backups" / datetime.now().strftime(
    "firmware_runtime_%Y%m%d_%H%M%S_%f"
)
backup.mkdir(parents=True)
shutil.copy2(makefile, backup / "ai.mk")

for name in ("Inc", "Lib", "Npu"):
    shutil.move(str(target / name), str(backup / name))
    shutil.copytree(source / name, target / name)
    print(f"已更新：firmware/Lib/AI_Runtime/{name}", flush=True)

# 配對 GCC 使用的執行期函式庫。
makefile.write_text(
    text.replace(old_library, new_library),
    encoding="utf-8",
)

print(f"連結函式庫：{new_library}")
print(f"原始檔案備份：{backup}")
print("完成：主工程的 AI 執行期已配對。")
