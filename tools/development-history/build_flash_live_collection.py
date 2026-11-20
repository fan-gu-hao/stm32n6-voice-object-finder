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

if "FINDER_KWS_COLLECT_V1" not in (fw / "Src/app.c").read_text():
    raise SystemExit("請先加入收集模式。")

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
loader = (
    cli.parent / "ExternalLoader/MX66UW1G45G_STM32N6570-DK.stldr"
)

for p in (
    signer, loader,
    previous / "vision_commands.bin",
    previous / "kws_weights.bin",
):
    if not p.is_file():
        raise SystemExit("缺少檔案：" + str(p))

out = root / "output" / datetime.now().strftime(
    "finder_collect_%Y%m%d_%H%M%S_%f"
)
out.mkdir(parents=True)

env = dict(
    os.environ,
    PATH=str(gcc.parent) + os.pathsep + os.environ.get("PATH", ""),
)
build = "build_kws_collect"
log = out / "build.log"

print("編譯日誌：", log, flush=True)
with log.open("w") as f:
    result = subprocess.run([
        "make", "-C", str(fw), "-j8",
        "GCC_PATH=" + str(gcc.parent),
        "BUILD_DIR=" + build,
        build + "/Project.elf",
    ], stdout=f, stderr=subprocess.STDOUT, env=env)

lines = log.read_text(errors="replace").splitlines()
print("\n".join(lines[-20 if result.returncode == 0 else -80:]))

if result.returncode:
    raise SystemExit("編譯失敗，請貼上末尾錯誤。")

def run(args):
    subprocess.run([str(a) for a in args], check=True)

elf = fw / build / "Project.elf"
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
    fw / "Model/kws/kws_weights.bin", out / "kws_weights.bin"
)

for name in ("vision_commands.bin", "kws_weights.bin"):
    if (out / name).read_bytes() != (previous / name).read_bytes():
        raise SystemExit(
            name + " 與上一版不同，尚未燒錄，請貼上訊息。"
        )

shutil.copy2(elf, out / "Project.elf")
shutil.copy2(elf.with_suffix(".map"), out / "Project.map")

raw = (out / "finder.bin").read_bytes()
if not 8 <= len(raw) <= 1023 * 1024:
    raise SystemExit("主程式大小異常。")

sp, entry = struct.unpack_from("<II", raw)
if (
    sp != 0x34100000 or not entry & 1
    or not 0x34000400 <= (entry & ~1) < 0x34100000
):
    raise SystemExit("向量表不符。")

run([
    signer, "-bin", out / "finder.bin",
    "-nk", "-of", "0x80000000",
    "-t", "ssbl", "-hv", "2.3", "-align",
    "-o", out / "finder_signed.bin",
])

signed = (out / "finder_signed.bin").read_bytes()
if (
    signed.find(raw[:64]) != 0x400
    or signed[0x400:0x400 + len(raw)] != raw
):
    raise SystemExit("映像對齊檢查失敗。")

shutil.copy2(
    root / "kws/live_collection_plan.json",
    out / "collection_plan.json",
)
(out / "previous_output.txt").write_text(str(previous) + "\n")

print("开始更新主程式 0x70100000。", flush=True)
run([
    cli, "-c", "port=SWD", "mode=HOTPLUG", "ap=1", "freq=1000",
    "sn=" + os.environ["N6_PROBE_SERIAL"],
    "-el", loader, "-hardRst",
    "-w", out / "finder_signed.bin", "0x70100000", "-v",
])

(root / "output/finder_collection_current.txt").write_text(
    str(out) + "\n"
)
print("收集版已燒錄。斷電後 BOOT0、BOOT1 切回 L，再上電。")
