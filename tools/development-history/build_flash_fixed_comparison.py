from pathlib import Path
from datetime import datetime
import os
import shutil
import struct
import subprocess

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
ide = Path("/opt/st/stm32cubeide_2.2.0")

previous = Path(
    (root / "output/finder_voice_current.txt").read_text().strip()
)

if "#define FINDER_KWS_COMPARE_ENABLED 1" not in (
    fw / "Inc/finder_kws_compare.h"
).read_text():
    raise SystemExit("請先加入並啟用比對程式。")

for rel in ("Src/finder_kws.c", "Src/app.c"):
    if "FINDER_KWS_COMPARE_V1" not in (fw / rel).read_text():
        raise SystemExit(f"比對程式尚未完整接入：{rel}")

def one(pattern):
    paths = [
        p for p in ide.glob(pattern)
        if p.is_file() and os.access(p, os.X_OK)
    ]
    if len(paths) != 1:
        raise SystemExit("工具數量不是 1：" + pattern)
    return paths[0]

gcc = one(
    "plugins/com.st.stm32cube.ide.mcu.externaltools."
    "gnu-tools-for-stm32.*/tools/bin/arm-none-eabi-gcc"
)
cli = one(
    "plugins/com.st.stm32cube.ide.mcu.externaltools."
    "cubeprogrammer.linux64_*/tools/bin/STM32_Programmer_CLI"
)
signer = cli.with_name("STM32_SigningTool_CLI")
loader = cli.parent / "ExternalLoader/MX66UW1G45G_STM32N6570-DK.stldr"

for path in (
    signer, loader,
    previous / "vision_commands.bin",
    previous / "kws_weights.bin",
):
    if not path.is_file():
        raise SystemExit(f"缺少檔案：{path}")

out = root / "output" / datetime.now().strftime(
    "finder_compare_%Y%m%d_%H%M%S_%f"
)
out.mkdir(parents=True, exist_ok=False)
(out / "previous_output.txt").write_text(str(previous) + "\n")
print("本次輸出：", out, flush=True)

env = dict(
    os.environ,
    PATH=str(gcc.parent) + os.pathsep + os.environ.get("PATH", "")
)

with (out / "build.log").open("w") as log:
    result = subprocess.run([
        "make", "-C", str(fw),
        "-j" + str(min(os.cpu_count() or 4, 16)),
        "GCC_PATH=" + str(gcc.parent),
        "BUILD_DIR=build_kws_compare",
        "build_kws_compare/Project.elf",
    ], stdout=log, stderr=subprocess.STDOUT, env=env)

lines = (out / "build.log").read_text(errors="replace").splitlines()
print(
    "\n".join(lines[-20 if result.returncode == 0 else -80:]),
    flush=True
)

if result.returncode:
    raise SystemExit("編譯失敗，請貼上末尾錯誤，尚未燒錄。")

def run(args):
    subprocess.run([str(x) for x in args], check=True)

elf = fw / "build_kws_compare/Project.elf"
objcopy = gcc.with_name("arm-none-eabi-objcopy")

run([
    objcopy, "-O", "binary", "--remove-section=.flash_section",
    elf, out / "finder.bin",
])
run([
    objcopy, "-O", "binary", "--only-section=.flash_section",
    elf, out / "vision_commands.bin",
])

shutil.copy2(
    fw / "Model/kws/kws_weights.bin",
    out / "kws_weights.bin"
)

for name in ("vision_commands.bin", "kws_weights.bin"):
    if (out / name).read_bytes() != (previous / name).read_bytes():
        raise SystemExit(f"{name} 與上一版不同，尚未燒錄。")

shutil.copy2(elf, out / "Project.elf")
shutil.copy2(elf.with_suffix(".map"), out / "Project.map")

raw = (out / "finder.bin").read_bytes()
if not 8 <= len(raw) <= 1023 * 1024:
    raise SystemExit("主程式大小超出預期，尚未燒錄。")

sp, entry = struct.unpack_from("<II", raw)
if (
    sp != 0x34100000
    or not entry & 1
    or not 0x34000400 <= (entry & ~1) < 0x34100000
):
    raise SystemExit("向量表與預期不同，尚未燒錄。")

run([
    signer, "-bin", out / "finder.bin",
    "-nk", "-of", "0x80000000",
    "-t", "ssbl", "-hv", "2.3", "-align",
    "-o", out / "finder_signed.bin",
])

signed = (out / "finder_signed.bin").read_bytes()
if (
    signed.find(raw[:64]) != 0x400
    or signed[0x400:0x400+len(raw)] != raw
):
    raise SystemExit("簽章映像沒有正確對齊 0x400，尚未燒錄。")

print("映像檢查通過，開始更新 0x70100000 的主程式。", flush=True)

command = [
    str(cli), "-c", "port=SWD", "mode=HOTPLUG",
    "ap=1", "freq=1000", "sn=" + os.environ["N6_PROBE_SERIAL"],
    "-el", str(loader), "-hardRst",
    "-w", str(out / "finder_signed.bin"), "0x70100000", "-v",
]

with (out / "flash.log").open("w") as log:
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True
    )
    for line in proc.stdout:
        print(line, end="", flush=True)
        log.write(line)
    if proc.wait() != 0:
        raise SystemExit("燒錄未完成，請貼上末尾訊息。")

(root / "output/finder_compare_current.txt").write_text(
    str(out) + "\n"
)
print("比對版已燒錄。斷電後 BOOT0、BOOT1 切回 L，再上電。")
