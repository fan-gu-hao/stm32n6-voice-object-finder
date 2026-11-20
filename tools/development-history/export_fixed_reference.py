from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import re
import wave

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import numpy as np
from scipy.fft import rfft
import tensorflow as tf

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
model = fw / "Model/kws/kws_int8.tflite"
config = json.loads((fw / "Model/kws/config.json").read_text())
dataset = Path(config["dataset"])
manifest = json.loads((dataset / "manifest.json").read_text())
labels = ["cup", "bottle", "phone", "unknown", "silence"]

if config["labels"] != labels or manifest["labels"] != labels:
    raise SystemExit("類別順序與預期不同，先停止。")

# 使用目前韌體內的前處理表格。
table_text = (fw / "Inc/finder_kws_tables.h").read_text()

def table(name, shape):
    match = re.search(
        rf"static\s+const\s+float\s+kws_{name}\s*\[\d+\]\s*=\s*\{{(.*?)\}};",
        table_text, re.S
    )
    if not match:
        raise SystemExit(f"找不到前處理表格：{name}")

    values = [
        float(x.strip().rstrip("fF"))
        for x in match[1].split(",") if x.strip()
    ]
    return np.array(values, dtype=np.float32).reshape(shape)

window = table("window", (480,))
mel = table("mel", (40, 257))
dct = table("dct", (13, 40))
mean = table("mean", (13,))
std = table("std", (13,))

interpreter = tf.lite.Interpreter(
    model_path=str(model), num_threads=1
)
interpreter.allocate_tensors()
inp = interpreter.get_input_details()[0]
output = interpreter.get_output_details()[0]

if (
    list(inp["shape"]) != [1, 49, 13, 1]
    or inp["dtype"] != np.int8
    or output["dtype"] != np.int8
    or int(np.prod(output["shape"])) != 5
):
    raise SystemExit("模型輸入或輸出介面與預期不同。")

input_scale, input_zero = inp["quantization"]
output_scale, output_zero = output["quantization"]

def features(pcm):
    clip_mean = (
        np.float32(pcm.astype(np.int64).sum())
        / np.float32(32768 * 16000)
    )
    audio = pcm.astype(np.float32) / np.float32(32768) - clip_mean

    frames = np.stack([
        audio[t * 320:t * 320 + 480] for t in range(49)
    ])
    spectrum = rfft(frames * window, n=512, axis=1)
    power = spectrum.real ** 2 + spectrum.imag ** 2

    log_mel = np.log(
        np.maximum(power @ mel.T, np.float32(1e-10))
    )
    normalized = np.clip(
        (log_mel @ dct.T - mean) / std, -6, 6
    )
    quantized = (
        np.rint(normalized / np.float32(input_scale))
        + input_zero
    )
    return (
        np.clip(quantized, -128, 127)
        .astype(np.int8)
        .reshape(1, 49, 13, 1)
    )

pcm_rows = []
input_rows = []
output_rows = []
records = []

for label in labels:
    # 每類固定取檔名排序後的第一段驗證錄音。
    rows = sorted(
        [
            r for r in manifest["clips"]
            if r["split"] == "validation" and r["label"] == label
        ],
        key=lambda r: r["file"]
    )
    if not rows:
        raise SystemExit(f"找不到驗證音檔：{label}")

    path = dataset / rows[0]["file"]

    with wave.open(str(path), "rb") as wav:
        fmt = (
            wav.getnchannels(), wav.getsampwidth(),
            wav.getframerate(), wav.getnframes()
        )
        if fmt != (1, 2, 16000, 16000):
            raise SystemExit(f"音檔格式與預期不同：{path}")
        pcm = np.frombuffer(
            wav.readframes(16000), dtype="<i2"
        ).copy()

    q = features(pcm)
    interpreter.set_tensor(inp["index"], q)
    interpreter.invoke()

    result = interpreter.get_tensor(
        output["index"]
    ).reshape(-1).copy()

    scores = (
        result.astype(np.int32) - output_zero
    ) * output_scale
    best = int(np.argmax(scores))

    pcm_rows.append(pcm)
    input_rows.append(q.reshape(-1))
    output_rows.append(result)
    records.append({
        "label": label,
        "file": str(path),
        "prediction": labels[best],
        "scores": scores.tolist(),
    })

    print(
        f"原始類別={label:7s}  "
        f"電腦預測={labels[best]:7s}  "
        f"分數={scores[best]:.4f}",
        flush=True
    )

out = root / "kws/comparison" / datetime.now().strftime(
    "%Y%m%d_%H%M%S_%f"
)
out.mkdir(parents=True, exist_ok=False)

np.savez(
    out / "reference.npz",
    pcm=np.stack(pcm_rows),
    inputs=np.stack(input_rows),
    outputs=np.stack(output_rows),
)

report = {
    "labels": labels,
    "records": records,
    "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
    "tables_sha256": hashlib.sha256(table_text.encode()).hexdigest(),
    "input_quantization": [input_scale, input_zero],
    "output_quantization": [output_scale, output_zero],
}
(out / "reference.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
(root / "kws/comparison_current.txt").write_text(str(out) + "\n")

print("\n對照資料：", out)
print("已保存五段原始音訊、量化輸入與電腦輸出。")
print("本次尚未修改或燒錄韌體。")
