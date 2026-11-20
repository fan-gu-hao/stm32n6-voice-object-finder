from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import numpy as np

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
deployed = fw / "Model/kws"

candidate = (
    root / "kws/runs/kws_groupcv_20261008_015013_527709/final"
)
ai = Path.home() / "ST/STEdgeAI/4.0/Utilities/linux/stedgeai"

required = [
    candidate / "kws_int8.tflite",
    candidate / "frontend.npz",
    candidate / "config.json",
    deployed / "config.json",
    deployed / "kws.mpool",
    deployed / "kws_neuralart.json",
    fw / "Inc/finder_kws_tables.h",
    fw / "Inc/finder_kws_compare.h",
]

for path in required:
    if not path.is_file():
        raise SystemExit("缺少檔案：" + str(path))

if not ai.is_file() or not os.access(ai, os.X_OK):
    raise SystemExit("找不到可執行的產碼工具：" + str(ai))

config = json.loads((candidate / "config.json").read_text())
previous = json.loads((deployed / "config.json").read_text())

# 確認新模型仍使用目前韌體的特徵定義與輸入介面。
keys = [
    "labels", "sample_rate", "samples",
    "frame_length", "frame_step", "fft_length",
    "mel_bins", "mfcc_count", "input_shape",
    "mel_scale", "fmin", "fmax", "window",
    "center", "power", "log", "floor",
    "remove_clip_mean", "dct_norm", "normalization_clip",
]
for key in keys:
    if key not in config or key not in previous:
        raise SystemExit("設定缺少欄位：" + key)
    if config[key] != previous[key]:
        raise SystemExit(
            f"模型介面不同：{key}\n"
            f"目前韌體：{previous[key]}\n"
            f"新模型：{config[key]}"
        )

shapes = {
    "window": (480,),
    "mel": (40, 257),
    "dct": (13, 40),
    "mean": (13,),
    "std": (13,),
}
with np.load(candidate / "frontend.npz") as frontend:
    for name, shape in shapes.items():
        if name not in frontend:
            raise SystemExit("前處理參數缺少：" + name)
        value = frontend[name]
        if value.shape != shape or not np.isfinite(value).all():
            raise SystemExit("前處理參數形狀或數值異常：" + name)
    if np.any(frontend["std"] <= 0):
        raise SystemExit("標準差參數必須大於零。")

out = root / "output" / datetime.now().strftime(
    "finder_groupcv_codegen_%Y%m%d_%H%M%S_%f"
)
stage = out / "codegen"
stage.mkdir(parents=True, exist_ok=False)

for name in ("kws_int8.tflite", "frontend.npz", "config.json"):
    shutil.copy2(candidate / name, stage / name)

for name in ("kws.mpool", "kws_neuralart.json"):
    shutil.copy2(deployed / name, stage / name)

(out / "source_model.txt").write_text(str(candidate) + "\n")
(out / "model_sha256.txt").write_text(
    hashlib.sha256(
        (stage / "kws_int8.tflite").read_bytes()
    ).hexdigest() + "\n"
)

command = [
    str(ai), "generate",
    "--model", "kws_int8.tflite",
    "--target", "stm32n6",
    "--name", "kws_network",
    "--st-neural-art", "kws@kws_neuralart.json",
    "--input-data-type", "int8",
    "--output-data-type", "int8",
]
(out / "command.json").write_text(
    json.dumps(command, indent=2) + "\n"
)

log = out / "codegen.log"
print("來源模型：", candidate, flush=True)
print("產碼日誌：", log, flush=True)

with log.open("w") as f:
    result = subprocess.run(
        command,
        cwd=stage,
        stdout=f,
        stderr=subprocess.STDOUT,
    )

lines = log.read_text(errors="replace").splitlines()
print("\n".join(lines[-60:]))

if result.returncode:
    raise SystemExit("產碼失敗，請貼回以上錯誤。")

print("\n【必要產碼檔案】")
for name in (
    "kws_network.c",
    "stai_kws_network.c",
    "stai_kws_network.h",
):
    matches = list(stage.rglob(name))
    if len(matches) != 1:
        raise SystemExit(
            f"{name} 數量不是 1："
            + ", ".join(str(p) for p in matches)
        )
    path = matches[0]
    print(path.relative_to(stage), path.stat().st_size, "位元組")

print("\n【記憶體初始化檔案】")
for path in sorted(stage.rglob("*.raw")):
    print(path.relative_to(stage), path.stat().st_size, "位元組")

print("\n【新模型量化參數】")
for key in ("input_quantization", "output_quantization"):
    print(key, config[key])

print("\n【目前前處理表頭的巨集與陣列名稱】")
header = (fw / "Inc/finder_kws_tables.h").read_text()
for line in header.splitlines():
    if line.lstrip().startswith("#define"):
        print(line)

for declaration in re.findall(
    r"(?:static\s+)?const\s+float\s+\w+\s*"
    r"(?:\[[^\]]*\]\s*)*",
    header,
):
    print(declaration.strip() + ";")

print("\n【目前收集／比對模式】")
control = (fw / "Inc/finder_kws_compare.h").read_text()
for line in control.splitlines():
    if line.lstrip().startswith("#define FINDER_KWS_"):
        print(line)

print("\n【目前編譯設定】")
print((deployed / "kws_neuralart.json").read_text())

print("\n【目前記憶體池】")
print((deployed / "kws.mpool").read_text())

(root / "output/kws_codegen_current.txt").write_text(
    str(out) + "\n"
)
print("\n產碼完成：", out)
