from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import numpy as np

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
model = fw / "Model/kws"
package = root / "output/finder_groupcv_codegen_20261008_022527_741465"
stage = package / "codegen"
generated = stage / "st_ai_output"
header_path = fw / "Inc/finder_kws_tables.h"
control_path = fw / "Inc/finder_kws_compare.h"
ide = Path("/opt/st/stm32cubeide_2.2.0")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

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
objcopy = gcc.with_name("arm-none-eabi-objcopy")
signer = cli.with_name("STM32_SigningTool_CLI")
loader = cli.parent / "ExternalLoader/MX66UW1G45G_STM32N6570-DK.stldr"
previous = Path(
    (root / "output/finder_voice_current.txt").read_text().strip()
)
candidate = Path((package / "source_model.txt").read_text().strip())

required = [
    objcopy, signer, loader, header_path, control_path,
    previous / "vision_commands.bin",
    generated / "kws_network_atonbuf.xSPI2.raw",
]
required += [generated / name for name in (
    "kws_network.c", "kws_network.h",
    "stai_kws_network.c", "stai_kws_network.h",
)]
required += [stage / name for name in (
    "kws_int8.tflite", "frontend.npz", "config.json",
    "kws.mpool", "kws_neuralart.json",
)]
for path in required:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit("缺少檔案或檔案為空：" + str(path))

recorded_hash = (package / "model_sha256.txt").read_text().strip()
if digest(stage / "kws_int8.tflite") != recorded_hash:
    raise SystemExit("產碼來源模型雜湊不符。")
for name in ("kws_int8.tflite", "frontend.npz", "config.json"):
    if digest(stage / name) != digest(candidate / name):
        raise SystemExit("候選模型與產碼來源不一致：" + name)

pool = json.loads((stage / "kws.mpool").read_text())
units = {"BYTES": 1, "KBYTES": 1024, "MBYTES": 1024 * 1024}

def amount(value):
    return int(str(value["value"]), 0) * units[value["magnitude"]]

layout = {
    p["name"]: (amount(p["offset"]), amount(p["size"]))
    for p in pool["memory"]["mempools"]
}
if layout != {
    "kwsRAM": (0x91FC0000, 256 * 1024),
    "kwsFlash": (0x70700000, 64 * 1024),
}:
    raise SystemExit("記憶體配置與本次確認結果不同。")

raw_weights = generated / "kws_network_atonbuf.xSPI2.raw"
if not 0 < raw_weights.stat().st_size <= 64 * 1024:
    raise SystemExit("語音權重超出保留的快閃記憶體區域。")

config = json.loads((stage / "config.json").read_text())
if config["labels"] != ["cup", "bottle", "phone", "unknown", "silence"]:
    raise SystemExit("模型類別順序不符。")

arrays = {}
shapes = {
    "window": (480,), "mel": (40, 257), "dct": (13, 40),
    "mean": (13,), "std": (13,),
}
with np.load(stage / "frontend.npz") as data:
    for name, shape in shapes.items():
        value = np.asarray(data[name], dtype=np.float32)
        if value.shape != shape or not np.isfinite(value).all():
            raise SystemExit("前處理參數異常：" + name)
        arrays[name] = value.reshape(-1).copy()
if np.any(arrays["std"] <= 0):
    raise SystemExit("標準差參數必須大於零。")

# 確認固定係數及展平順序與目前韌體一致。
old_header = header_path.read_text()
for name in ("window", "mel", "dct"):
    matches = list(re.finditer(
        rf"\bkws_{name}\s*\[\s*{arrays[name].size}\s*\]"
        rf"\s*=\s*\{{(.*?)\}}\s*;",
        old_header, re.S,
    ))
    if len(matches) != 1:
        raise SystemExit("找不到唯一的既有係數陣列：kws_" + name)
    body = re.sub(
        r"/\*.*?\*/|//[^\n]*", "", matches[0][1], flags=re.S
    )
    old_values = np.array([
        float(s.strip().rstrip("fF"))
        for s in body.split(",") if s.strip()
    ], dtype=np.float32)
    if old_values.shape != arrays[name].shape or not np.allclose(
        old_values, arrays[name], rtol=5e-7, atol=1e-9
    ):
        raise SystemExit("固定係數或排列方式不同，尚未修改：" + name)

def cf(value):
    return f"{float(np.float32(value)):.9e}f"

lines = [
    "#ifndef FINDER_KWS_TABLES_H",
    "#define FINDER_KWS_TABLES_H", "",
]
for prefix, key in (
    ("INPUT", "input_quantization"),
    ("OUTPUT", "output_quantization"),
):
    q = config[key]
    if (
        not np.isfinite(q["scale"]) or q["scale"] <= 0
        or not -128 <= q["zero_point"] <= 127
    ):
        raise SystemExit("量化參數異常：" + key)
    lines += [
        f"#define KWS_{prefix}_SCALE ({cf(q['scale'])})",
        f"#define KWS_{prefix}_ZERO ({int(q['zero_point'])})",
    ]

for name, values in arrays.items():
    lines += ["", f"static const float kws_{name}[{values.size}] = {{"]
    for i in range(0, values.size, 8):
        lines.append(
            "  " + ", ".join(cf(v) for v in values[i:i+8]) + ","
        )
    lines.append("};")
new_header = "\n".join(lines + ["", "#endif", ""])

control = control_path.read_text()
for name in (
    "FINDER_KWS_LIVE_CAPTURE",
    "FINDER_KWS_COMPARE_ENABLED",
):
    control, count = re.subn(
        rf"(?m)^([ \t]*#define[ \t]+{name})[ \t]+[01][ \t]*$",
        r"\g<1> 0", control,
    )
    if count != 1:
        raise SystemExit("找不到唯一模式設定：" + name)

if "FINDER_VOICE_TRACE_V1" not in (fw / "Src/app.c").read_text():
    raise SystemExit("目前主程式缺少詳細語音紀錄標記，尚未修改。")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
backup = root / "backups" / ("groupcv_install_" + stamp)
backup.mkdir(parents=True)
shutil.copytree(model, backup / "Model/kws")
for path in (header_path, control_path):
    target = backup / path.relative_to(fw)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)

shutil.copytree(generated, model / "st_ai_output", dirs_exist_ok=True)
for name in (
    "kws_int8.tflite", "frontend.npz", "config.json",
    "kws.mpool", "kws_neuralart.json",
):
    shutil.copy2(stage / name, model / name)
shutil.copy2(raw_weights, model / "kws_weights.bin")
header_path.write_text(new_header)
control_path.write_text(control)

print("韌體模型與係數已更新；收集與固定資料比對模式均已關閉。")
print("備份：", backup, flush=True)

# 使用新的建置目錄，完整重新編譯。
out = root / "output" / ("finder_groupcv_deploy_" + stamp)
out.mkdir(parents=True)
build = "build_kws_groupcv_" + stamp
env = dict(
    os.environ,
    PATH=str(gcc.parent) + os.pathsep + os.environ.get("PATH", ""),
)
log = out / "build.log"
print("編譯日誌：", log, flush=True)
with log.open("w") as f:
    result = subprocess.run([
        "make", "-C", str(fw), "-j8",
        "GCC_PATH=" + str(gcc.parent),
        "BUILD_DIR=" + build, build + "/Project.elf",
    ], stdout=f, stderr=subprocess.STDOUT, env=env)

tail = log.read_text(errors="replace").splitlines()
print("\n".join(tail[-25 if result.returncode == 0 else -80:]))
if result.returncode:
    raise SystemExit("編譯失敗，請貼回末尾錯誤，先不要執行燒錄。")

def run(args):
    subprocess.run([str(a) for a in args], check=True)

elf = fw / build / "Project.elf"
run([
    objcopy, "-O", "binary", "--remove-section=.flash_section",
    elf, out / "finder.bin",
])
run([
    objcopy, "-O", "binary", "--only-section=.flash_section",
    elf, out / "vision_commands.bin",
])
if digest(out / "vision_commands.bin") != digest(previous / "vision_commands.bin"):
    raise SystemExit("視覺命令區與上一版不同，請貼回訊息，尚未燒錄。")

shutil.copy2(model / "kws_weights.bin", out / "kws_weights.bin")
if digest(out / "kws_weights.bin") != digest(raw_weights):
    raise SystemExit("語音權重複製檢查失敗。")
shutil.copy2(elf, out / "Project.elf")
shutil.copy2(elf.with_suffix(".map"), out / "Project.map")
shutil.copy2(header_path, out / "finder_kws_tables.h")
shutil.copy2(control_path, out / "finder_kws_compare.h")

raw = (out / "finder.bin").read_bytes()
if not 8 <= len(raw) <= 1023 * 1024:
    raise SystemExit("主程式大小異常。")
sp, entry = struct.unpack_from("<II", raw)
if (
    sp != 0x34100000 or not entry & 1
    or not 0x34000400 <= (entry & ~1) < 0x34100000
):
    raise SystemExit("主程式向量表不符。")

run([
    signer, "-bin", out / "finder.bin", "-nk",
    "-of", "0x80000000", "-t", "ssbl", "-hv", "2.3",
    "-align", "-o", out / "finder_signed.bin",
])
signed = (out / "finder_signed.bin").read_bytes()
if (
    len(signed) > 1024 * 1024
    or signed[0x400:0x400+len(raw)] != raw
):
    raise SystemExit("簽章映像大小或 0x400 偏移檢查失敗。")

images = [
    {"file": "kws_weights.bin", "address": "0x70700000"},
    {"file": "finder_signed.bin", "address": "0x70100000"},
]
for item in images:
    item["sha256"] = digest(out / item["file"])

manifest = {
    "candidate": str(candidate), "codegen": str(package),
    "backup": str(backup), "previous": str(previous),
    "programmer": str(cli), "loader": str(loader),
    "images": images,
}
(out / "flash_manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n"
)
(root / "output/finder_groupcv_build_current.txt").write_text(
    str(out) + "\n"
)
print("\n編譯與簽章完成：", out)
print("新輸入量化：", config["input_quantization"])
for item in images:
    print(
        item["file"], (out / item["file"]).stat().st_size,
        "位元組 →", item["address"],
    )
print("接著依第二步設定開機開關並燒錄。")
