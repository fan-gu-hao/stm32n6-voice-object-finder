from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import re
import select
import shutil
import subprocess
import termios
import time
import wave
import zlib

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import numpy as np
from scipy.fft import rfft
import tensorflow as tf

root = Path.home() / "STM32N6ai/course17_voice_object_finder"
fw = root / "firmware"
port = os.environ["N6_SERIAL_PORT"]
labels = ["cup", "bottle", "phone", "unknown", "silence"]
stages = ["silence", "cup", "bottle", "phone"]

config = json.loads((fw / "Model/kws/config.json").read_text())
if config["labels"] != labels:
    raise SystemExit("模型類別順序不同，停止。")

table_text = (fw / "Inc/finder_kws_tables.h").read_text()

def table(name, shape):
    match = re.search(
        rf"static\s+const\s+float\s+kws_{name}\s*\[\d+\]\s*=\s*\{{(.*?)\}};",
        table_text, re.S,
    )
    if not match:
        raise SystemExit("找不到前處理表格：" + name)
    values = [
        float(x.strip().rstrip("fF"))
        for x in match[1].split(",") if x.strip()
    ]
    return np.array(values, dtype=np.float32).reshape(shape)

window, mel, dct, mean, std = [
    table(name, shape) for name, shape in (
        ("window", (480,)),
        ("mel", (40, 257)),
        ("dct", (13, 40)),
        ("mean", (13,)),
        ("std", (13,)),
    )
]

model = fw / "Model/kws/kws_int8.tflite"
runner = tf.lite.Interpreter(model_path=str(model), num_threads=1)
runner.allocate_tensors()
inp = runner.get_input_details()[0]
output = runner.get_output_details()[0]

if (
    list(inp["shape"]) != [1, 49, 13, 1]
    or inp["dtype"] != np.int8
    or output["dtype"] != np.int8
    or np.prod(output["shape"]) != 5
):
    raise SystemExit("模型介面與預期不同。")

scale, zero = inp["quantization"]

def features(pcm):
    dc = np.float32(pcm.astype(np.int64).sum()) / np.float32(32768 * 16000)
    x = pcm.astype(np.float32) / np.float32(32768) - dc
    frames = np.stack([x[t*320:t*320+480] for t in range(49)])
    spec = rfft(frames * window, n=512, axis=1)
    power = spec.real**2 + spec.imag**2
    log_mel = np.log(np.maximum(power @ mel.T, np.float32(1e-10)))
    value = np.clip((log_mel @ dct.T - mean) / std, -6, 6)
    q = np.rint(value / np.float32(scale)) + zero
    return np.clip(q, -128, 127).astype(np.int8).reshape(1, 49, 13, 1)

def infer(q):
    runner.set_tensor(inp["index"], q)
    runner.invoke()
    return runner.get_tensor(output["index"]).reshape(5).copy()

out = root / "kws/live_comparison" / datetime.now().strftime(
    "%Y%m%d_%H%M%S_%f"
)
out.mkdir(parents=True, exist_ok=False)

subprocess.run([
    "stty", "-F", port, "115200", "raw", "-echo", "cs8",
    "-cstopb", "-parenb", "-crtscts", "-ixon", "-ixoff", "clocal",
], check=True)

fd = os.open(port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
records, packet, pending = {}, None, b""
armed = False
deadline = time.monotonic() + 150

try:
    termios.tcflush(fd, termios.TCIFLUSH)
    print("接收已就緒：現在按一下板上的 RESET。", flush=True)
    print("跟著提示說話；傳輸期間保持安靜。輸出：", out, flush=True)

    with (out / "serial.log").open("w") as log:
        done = False
        while not done:
            if time.monotonic() > deadline:
                raise RuntimeError("接收逾時，請保留 serial.log。")

            if not select.select([fd], [], [], 0.3)[0]:
                continue

            chunk = os.read(fd, 8192)
            if not chunk:
                raise RuntimeError("串列連線中斷。")
            pending += chunk

            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                line = raw.decode("ascii", errors="replace").strip()
                log.write(line + "\n")

                if line == "LIVE,CUE,0,silence":
                    armed = True
                    records, packet = {}, None

                if not armed or not line.startswith("LIVE,"):
                    continue

                parts = line.split(",")

                if parts[1] == "CUE":
                    label = parts[3]
                    if label == "silence":
                        print("\n請保持安靜約四秒。", flush=True)
                    else:
                        print(
                            f"\n現在說一次 {label}，說完保持安靜。",
                            flush=True,
                        )

                elif parts[1] == "B":
                    index = int(parts[2])
                    if index != len(records) or parts[3] != stages[index]:
                        raise RuntimeError("接收順序不符，請重新執行並按 RESET。")

                    packet = {
                        "index": index,
                        "label": parts[3],
                        "time_ms": int(parts[4]),
                        "peak": int(parts[5]),
                        "data": bytearray(),
                    }
                    print("正在傳回音訊，約六秒，請保持安靜。", flush=True)

                elif parts[1] == "D":
                    if packet is None or int(parts[2]) != len(packet["data"]):
                        raise RuntimeError("資料片段缺漏，請保留 serial.log。")
                    packet["data"].extend(bytes.fromhex(parts[3]))

                elif parts[1] == "E":
                    if (
                        packet is None
                        or len(packet["data"]) != 32642
                        or zlib.crc32(packet["data"]) != int(parts[2], 16)
                    ):
                        raise RuntimeError("傳輸校驗失敗，請保留 serial.log。")

                    records[packet["index"]] = packet
                    (out / (packet["label"] + ".bin")).write_bytes(packet["data"])
                    print("已收到：", packet["label"], flush=True)
                    packet = None

                elif parts[1] == "ERROR":
                    raise RuntimeError(line)

                elif parts[1] == "DONE":
                    if len(records) != 4:
                        raise RuntimeError("四段資料尚未收齊。")
                    done = True
                    break
finally:
    os.close(fd)

report = {
    "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
    "tables_sha256": hashlib.sha256(table_text.encode()).hexdigest(),
    "records": [],
}

for index in range(4):
    rec = records[index]
    data = bytes(rec["data"])
    pcm = np.frombuffer(data[:32000], dtype="<i2").copy()
    board_input = np.frombuffer(
        data[32000:32637], dtype=np.int8
    ).copy().reshape(1, 49, 13, 1)
    board_q = np.frombuffer(data[32637:], dtype=np.int8).copy()

    pc_input = features(pcm)
    pc_q = infer(board_input)
    pcm_q = infer(pc_input)

    in_diff = np.abs(
        pc_input.astype(np.int16) - board_input.astype(np.int16)
    )
    out_diff = np.abs(
        pc_q.astype(np.int16) - board_q.astype(np.int16)
    )

    wav = out / (rec["label"] + ".wav")
    with wave.open(str(wav), "wb") as w:
        w.setparams((1, 2, 16000, 16000, "NONE", "not compressed"))
        w.writeframes(data[:32000])

    names = [
        labels[int(np.argmax(q))]
        for q in (board_q, pc_q, pcm_q)
    ]

    print(
        f"\n提示={rec['label']}；峰值={rec['peak']}；"
        f"擷取時間={rec['time_ms']} ms"
    )
    print(
        f"板子={names[0]}；電腦直接特徵={names[1]}；"
        f"電腦重算音訊={names[2]}"
    )
    print(
        f"input_diff={np.count_nonzero(in_diff)}，"
        f"input_max={in_diff.max()}，output_max={out_diff.max()}"
    )
    print("板子原始輸出：", board_q.tolist())
    print("電腦原始輸出：", pc_q.tolist())

    report["records"].append({
        "label": rec["label"],
        "time_ms": rec["time_ms"],
        "peak": rec["peak"],
        "n6": names[0],
        "pc_input": names[1],
        "pc_pcm": names[2],
        "input_diff": int(np.count_nonzero(in_diff)),
        "input_max": int(in_diff.max()),
        "output_max": int(out_diff.max()),
        "n6_q": board_q.tolist(),
        "pc_q": pc_q.tolist(),
        "pc_pcm_q": pcm_q.tolist(),
        "wav": str(wav),
    })

(out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
(root / "kws/live_comparison_current.txt").write_text(str(out) + "\n")
print("\n音檔及比對結果：", out, flush=True)

player = next(
    (shutil.which(x) for x in ("pw-play", "paplay", "aplay")
     if shutil.which(x)),
    None,
)
if player:
    for label in stages:
        print("播放：", label, flush=True)
        subprocess.run([player, str(out / (label + ".wav"))], check=True)
