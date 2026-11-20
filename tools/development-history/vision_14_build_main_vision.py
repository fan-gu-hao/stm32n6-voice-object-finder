from pathlib import Path
from datetime import datetime
import os
import re
import shutil
import subprocess

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
ide = Path("/opt/st/stm32cubeide_2.2.0")

def one(pattern):
    matches = [
        p for p in ide.glob(pattern)
        if p.is_file() and os.access(p, os.X_OK)
    ]
    if len(matches) != 1:
        raise SystemExit(
            f"工具數量不是 1：{pattern}\n"
            + "\n".join(map(str, matches))
        )
    return matches[0]

gcc = one(
    "plugins/com.st.stm32cube.ide.mcu.externaltools."
    "gnu-tools-for-stm32.*/tools/bin/arm-none-eabi-gcc"
)
signer = one(
    "plugins/com.st.stm32cube.ide.mcu.externaltools."
    "cubeprogrammer.linux64_*/tools/bin/STM32_SigningTool_CLI"
)
objcopy = gcc.with_name("arm-none-eabi-objcopy")
objdump = gcc.with_name("arm-none-eabi-objdump")

for relative, marker in (
    ("Src/app.c", "FINDER_VISION_APP_V2"),
    ("Src/app_cam.c", "FINDER_SQUARE_CAMERA_V1"),
    ("Gcc/STM32N657xx.ld", "FINDER_MEMORY_LAYOUT_V1"),
    ("Makefile", "FINDER_MEMORY_PLACEMENT_V1"),
):
    if marker not in (fw / relative).read_text(encoding="utf-8"):
        raise SystemExit(f"前面的修改尚未完成：{relative}")

for relative in ("Model/network_data.xSPI2.bin", "FSBL/ai_fsbl.hex"):
    path = fw / relative
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"找不到必要檔案：{path}")

out = root / "output" / datetime.now().strftime(
    "finder_vision_%Y%m%d_%H%M%S_%f"
)
out.mkdir(parents=True)
log = out / "build.log"

env = os.environ.copy()
env["PATH"] = str(gcc.parent) + os.pathsep + env.get("PATH", "")

command = [
    "make", "-C", str(fw),
    "-j" + str(min(os.cpu_count() or 4, 16)),
    "GCC_PATH=" + str(gcc.parent),
    "BUILD_DIR=build_finder",
    "build_finder/Project.elf",
]

print("正在編譯官方手部工程底座上的 YOLO 視覺版。", flush=True)
print("編譯日誌：", log, flush=True)

with log.open("w") as output:
    result = subprocess.run(
        command, stdout=output, stderr=subprocess.STDOUT, env=env
    )

lines = log.read_text(errors="replace").splitlines()
print("\n".join(lines[-80:] if result.returncode else lines[-25:]))

if result.returncode:
    raise SystemExit("編譯失敗，請貼上上述錯誤。")

elf = fw / "build_finder/Project.elf"
sections = subprocess.check_output(
    [str(objdump), "-h", str(elf)], text=True
)
(out / "sections.txt").write_text(sections)

match = re.search(
    r"^\s*\d+\s+\.flash_section\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)",
    sections, re.M,
)
if (
    not match
    or int(match[2], 16) != 0x71380000
    or not 0 < int(match[1], 16) <= 2 * 1024 * 1024
):
    raise SystemExit("神經處理器命令區段配置不符，請貼上 sections.txt。")

def run(args):
    subprocess.run([str(a) for a in args], check=True)

run([
    objcopy, "-O", "binary", "--remove-section=.flash_section",
    elf, out / "finder.bin",
])
run([
    objcopy, "-O", "binary", "--only-section=.flash_section",
    elf, out / "vision_commands.bin",
])

if not 0 < (out / "finder.bin").stat().st_size < 1023 * 1024:
    raise SystemExit("主程式映像大小超出配置，請貼上編譯結果。")

shutil.copy2(elf, out / "Project.elf")
shutil.copy2(fw / "build_finder/Project.map", out / "Project.map")
shutil.copy2(fw / "Model/network_data.xSPI2.bin", out / "vision_weights.bin")
shutil.copy2(fw / "FSBL/ai_fsbl.hex", out / "ai_fsbl.hex")

run([
    signer,
    "-bin", out / "finder.bin",
    "-nk", "-of", "0x80000000",
    "-t", "ssbl", "-hv", "2.3", "--align",
    "-o", out / "finder_signed.bin",
])

print("\n視覺版編譯與開機映像完成：", out)
for name, address in (
    ("ai_fsbl.hex", "HEX 檔案內含位址"),
    ("finder_signed.bin", "0x70100000"),
    ("vision_weights.bin", "0x70380000"),
    ("vision_commands.bin", "0x71380000"),
):
    path = out / name
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"產物缺失：{path}")
    print(f"{name}：{path.stat().st_size} 位元組；位址 {address}")

print("\n本輪完成編譯與映像準備；下一步是燒錄這個視覺版。")
