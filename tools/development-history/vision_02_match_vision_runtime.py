from pathlib import Path
from datetime import datetime
import shutil

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
repo = root / "vision"
runtime = Path.home() / "ST/STEdgeAI/4.0/Middlewares/ST/AI"
target = repo / "Middlewares/stedgeai-lib"
makefile = repo / "Application/STM32N6570-DK/Makefile"
library = "NetworkRuntime1201_CM55_GCC.a"

for name in ("Inc", "Lib", "Npu"):
    if not (runtime / name).is_dir():
        raise SystemExit(f"找不到執行期目錄：{runtime / name}")

if not (runtime / "Lib/GCC/ARMCortexM55" / library).is_file():
    raise SystemExit(f"找不到執行期函式庫：{library}")

text = makefile.read_text(encoding="utf-8")
if "NetworkRuntime1200_CM55_GCC.a" not in text and library not in text:
    raise SystemExit("Makefile 的執行期設定與預期不同。")

text = text.replace("NetworkRuntime1200_CM55_GCC.a", library)

marker = "# FINDER_MEMORY_PLACEMENT"
block = '''# FINDER_MEMORY_PLACEMENT
C_DEFS += '-DECBLOB_CONST_SECTION=__attribute__((section(".flash_blob")))'
C_DEFS += '-DPOSTPROCESS_WRAPPER_SECTION=__attribute__((section(".psram_bss")))'
'''

if marker not in text:
    anchor = "# C defines\n"
    if text.count(anchor) != 1:
        raise SystemExit("找不到 Makefile 的設定位置。")
    text = text.replace(anchor, anchor + block, 1)

backup = root / "backups" / datetime.now().strftime("runtime_%Y%m%d_%H%M%S_%f")
backup.mkdir(parents=True)
shutil.copy2(makefile, backup / "Makefile")

for name in ("Inc", "Lib", "Npu"):
    shutil.move(str(target / name), str(backup / name))
    shutil.copytree(runtime / name, target / name)

makefile.write_text(text, encoding="utf-8")

print("執行期已配對：", library)
print("已設定：NPU 命令存放 Flash，後處理緩衝區存放 PSRAM。")
print("修改前備份：", backup)
